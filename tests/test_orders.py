"""Order/reservation contracts using synthetic reviewed observations, never inference."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4
import json
import os
import sqlite3
import tempfile
import unittest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api import create_app
from src.catalog import CatalogStore, CatalogProduct, ShopInventory, SHOP_ID
from src.alternatives import AlternativeStore
from src.storage import ScanStore
from src.orders import OrderStore, OrderRequest, OrderError, Order
from src.review import ReviewRequest
from src.inference.config import load_config
from src.data_lock import DataBusyError
from src.backup import BackupService, RestoreService, validate_backup
from ui_support import staged_review, FixtureDetector, local_server


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.store=ScanStore(self.root/'db.sqlite',self.root/'scans')
        self.store.initialize()
        self.addCleanup(self.store.close)
        self.catalog=CatalogStore(self.store)
        self.orders=OrderStore(self.catalog)
        self.config=load_config()
        self.red=self.config.product_ids[0]

    def app(self):
        return create_app(detector_factory=FixtureDetector,database_path=self.store.path,
            scan_storage_dir=self.store.evidence.root,output_dir=self.root/'annotations')

    def confirm(self, count=5, class_id=0):
        return self.store.confirm(ReviewRequest.model_validate(staged_review(self.store,[{
            'class_id':class_id,'class_name':self.config.names[class_id],
            'predicted_count':count,'confirmed_count':count}])))

    def body(self, quantity=2, **kwargs):
        return {'request_id':str(uuid4()),'shop_id':SHOP_ID,
            'items':[{'product_id':self.red,'quantity':quantity}],**kwargs}

    def create(self, quantity=2, **kwargs):
        return self.orders.create(OrderRequest.model_validate(self.body(quantity,**kwargs)))

    def available(self):
        return self.catalog.inventory(self.red)[0]['available_quantity']

    def stale(self):
        with Session(self.store.engine) as session, session.begin():
            session.get(ShopInventory,(SHOP_ID,self.red)).last_confirmed_at=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(hours=2)

    def test_pending_request_persists_and_preserves_observation(self):
        saved=self.confirm()
        result=self.create()
        self.assertEqual(result['status'],'PENDING')
        self.assertEqual(result['customer_name'],'Demo Customer')
        self.assertEqual(self.available(),5)
        self.store.close(); self.store.initialize()
        self.assertEqual(self.orders.get(result['order_id']),result)
        self.assertEqual(self.store.get(saved.scan_id),saved)

    def test_creation_idempotency_and_changed_request_conflict(self):
        self.confirm()
        request=OrderRequest.model_validate(self.body())
        first=self.orders.create(request)
        self.assertEqual(self.orders.create(request),first)
        request.items[0].quantity=3
        with self.assertRaises(OrderError): self.orders.create(request)
        self.assertEqual(len(self.orders.history()),1)

    def test_invalid_product_shop_quantities_and_duplicate_items(self):
        self.confirm()
        for overrides in ({'shop_id':'missing'},{'items':[{'product_id':'missing','quantity':1}]}):
            with self.assertRaises(OrderError): self.create(**overrides)
        for value in (0,-1,101,True,1.5,'2'):
            with self.assertRaises(ValidationError): OrderRequest.model_validate(self.body(value))
        with self.assertRaises(ValidationError):
            OrderRequest.model_validate(self.body(items=[{'product_id':self.red,'quantity':1}]*2))
        with self.assertRaises(ValidationError): OrderRequest.model_validate(self.body(items=[]))

    def test_missing_demo_zero_stale_and_future_inventory_cannot_create(self):
        with self.assertRaises(OrderError): self.create()
        self.catalog.seed_demo()
        with self.assertRaises(OrderError): self.create()
        self.confirm(0)
        with self.assertRaises(OrderError): self.create()
        self.confirm(5); self.stale()
        with self.assertRaises(OrderError): self.create()
        with Session(self.store.engine) as session, session.begin():
            session.get(ShopInventory,(SHOP_ID,self.red)).last_confirmed_at=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(hours=1)
        with self.assertRaises(OrderError): self.create()

    def test_accept_reserves_without_rewriting_scan_and_is_idempotent(self):
        saved=self.confirm()
        order=self.create()
        accepted=self.orders.transition(order['order_id'],'ACCEPTED',confirmed=True)
        self.assertEqual(accepted['status'],'ACCEPTED')
        self.assertIsNotNone(accepted['accepted_at'])
        self.assertEqual(self.orders.transition(order['order_id'],'ACCEPTED',confirmed=True),accepted)
        row=self.catalog.inventory(self.red)[0]
        self.assertEqual((row['quantity'],row['reserved_quantity'],row['available_quantity']),(5,2,3))
        self.assertEqual(self.store.get(saved.scan_id),saved)

    def test_accept_requires_confirmation_and_fresh_count(self):
        self.confirm()
        order=self.create()
        with self.assertRaises(OrderError): self.orders.transition(order['order_id'],'ACCEPTED')
        self.stale()
        with self.assertRaises(OrderError): self.orders.transition(order['order_id'],'ACCEPTED',confirmed=True)
        self.assertEqual(self.orders.get(order['order_id'])['status'],'PENDING')
        self.confirm(5)
        self.assertEqual(self.orders.transition(order['order_id'],'ACCEPTED',confirmed=True)['status'],'ACCEPTED')

    def test_reject_cancel_and_invalid_terminal_transitions(self):
        self.confirm()
        for final in ('REJECTED','CANCELLED','ACCEPTED'):
            order=self.create(1)
            reason='Unavailable today' if final=='REJECTED' else None
            result=self.orders.transition(order['order_id'],final,confirmed=True,reason=reason)
            self.assertEqual(result['rejection_reason'],reason)
            for other in {'REJECTED','CANCELLED','ACCEPTED'}-{final}:
                with self.assertRaises(OrderError): self.orders.transition(order['order_id'],other,confirmed=True)
        self.assertEqual(self.available(),4)
        self.assertIsNone(self.orders.get(uuid4()))
        with self.assertRaises(OrderError): self.orders.transition(uuid4(),'ACCEPTED',confirmed=True)
        with self.assertRaises(OrderError): self.orders.transition(order['order_id'],'PENDING')

    def test_insufficient_acceptance_keeps_pending_and_exact_quantity_works(self):
        self.confirm(2)
        too_many=self.create(3)
        with self.assertRaisesRegex(OrderError,'Insufficient inventory'):
            self.orders.transition(too_many['order_id'],'ACCEPTED',confirmed=True)
        self.assertEqual(self.orders.get(too_many['order_id'])['status'],'PENDING')
        self.assertEqual(self.available(),2)
        exact=self.create(2)
        self.orders.transition(exact['order_id'],'ACCEPTED',confirmed=True)
        self.assertEqual(self.available(),0)
        self.assertFalse(self.catalog.inventory(self.red)[0]['recently_confirmed_positive'])
        with self.assertRaises(OrderError): self.create(1)

    def test_multiple_items_all_or_nothing(self):
        self.confirm(5); self.confirm(1,1)
        order=self.create(items=[{'product_id':self.red,'quantity':2},{'product_id':self.config.product_ids[1],'quantity':2}])
        with self.assertRaises(OrderError): self.orders.transition(order['order_id'],'ACCEPTED',confirmed=True)
        self.assertEqual(self.available(),5)
        self.assertEqual(self.catalog.inventory(self.config.product_ids[1])[0]['reserved_quantity'],0)

    def test_failure_after_flush_rolls_back_reservation_and_status(self):
        self.confirm()
        order=self.create()
        with patch('src.orders.serialize',side_effect=RuntimeError('Injected failure after flush')):
            with self.assertRaises(RuntimeError): self.orders.transition(order['order_id'],'ACCEPTED',confirmed=True)
        self.assertEqual(self.orders.get(order['order_id'])['status'],'PENDING')
        self.assertEqual(self.available(),5)

    def test_concurrent_independent_stores_cannot_oversell(self):
        self.confirm(2)
        orders=[self.create(2),self.create(2)]
        barrier=Barrier(2)
        def accept(order):
            # Separate service, engine and connection, as with independent workers.
            store=ScanStore(self.store.path,self.store.evidence.root)
            service=OrderStore(CatalogStore(store))
            try:
                barrier.wait(timeout=10)
                try: return service.transition(order['order_id'],'ACCEPTED',confirmed=True)['status']
                except (OrderError,DataBusyError): return 'BLOCKED'
            finally: store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(accept,orders))
        self.assertEqual(sorted(outcomes),['ACCEPTED','BLOCKED'])
        self.assertEqual(self.available(),0)
        pending=next(o for o in self.orders.history() if o['status']=='PENDING')
        with self.assertRaisesRegex(OrderError,'Insufficient inventory'):
            self.orders.transition(pending['order_id'],'ACCEPTED',confirmed=True)

    def test_new_observations_do_not_erase_reservations_or_history(self):
        self.confirm(5)
        order=self.create(3)
        self.orders.transition(order['order_id'],'ACCEPTED',confirmed=True)
        self.confirm(2)
        row=self.catalog.inventory(self.red)[0]
        self.assertEqual((row['quantity'],row['reserved_quantity'],row['available_quantity']),(2,3,0))
        self.confirm(6)
        self.assertEqual(self.available(),3)
        with Session(self.store.engine) as session, session.begin():
            session.get(CatalogProduct,self.red).name='Renamed synthetic product'
        self.assertEqual(self.orders.get(order['order_id'])['items'][0]['product_name'],'Red Bull')

    def test_api_create_history_detail_actions_and_errors(self):
        self.confirm()
        with TestClient(self.app()) as client:
            first=client.post('/orders',json=self.body()).json()
            id=first['order_id']
            self.assertEqual(client.get('/orders/'+id).json(),first)
            self.assertEqual(client.post('/orders/'+id+'/accept',json={'availability_confirmed':False}).status_code,409)
            self.assertEqual(client.post('/orders/'+id+'/accept',json={'availability_confirmed':'yes'}).status_code,422)
            self.assertEqual(client.post('/orders/'+id+'/accept',json={'availability_confirmed':True}).json()['status'],'ACCEPTED')
            self.assertEqual(client.post('/orders/'+id+'/cancel').status_code,409)
            second=client.post('/orders',json=self.body(1)).json()['order_id']
            self.assertEqual(client.post('/orders/'+second+'/reject',json={'reason':'Unavailable'}).json()['rejection_reason'],'Unavailable')
            third=client.post('/orders',json=self.body(1)).json()['order_id']
            self.assertEqual(client.post('/orders/'+third+'/cancel').json()['status'],'CANCELLED')
            self.assertEqual([o['order_id'] for o in client.get('/orders').json()['orders']],[third,second,id])
            self.assertEqual(len(client.get('/orders?status=ACCEPTED').json()['orders']),1)
            self.assertEqual(client.get('/orders?shop_id=missing').json()['orders'],[])
            self.assertEqual(client.get('/orders?limit=1&offset=1').json()['orders'][0]['order_id'],second)
            for path in ('/orders?limit=0','/orders?status=INVALID','/orders?offset=-1','/orders/not-uuid'):
                self.assertEqual(client.get(path).status_code,422)
            self.assertEqual(client.get('/orders/'+str(uuid4())).status_code,404)
            self.assertEqual(client.get('/orders').headers['cache-control'],'no-store')
            self.assertEqual(client.post('/orders',json=self.body(0)).status_code,422)

    def test_backup_roundtrip_preserves_accepted_reservations_and_pending_history(self):
        scan=self.confirm()
        order=self.create()
        self.orders.transition(order['order_id'],'ACCEPTED',confirmed=True)
        self.create(1)
        before=self.orders.history()
        archive=self.root/'orders.zip'
        self.assertEqual(BackupService(self.store.path,self.store.evidence.root).create_backup(archive)['schema_version'],4)
        self.store.close()
        RestoreService(self.store.path,self.store.evidence.root).restore_backup(archive)
        self.store.initialize()
        self.assertEqual(self.orders.history(),before)
        self.assertEqual(self.available(),3)
        self.assertEqual(self.store.get(scan.scan_id),scan)

    def test_schema_three_backup_restores_and_migrates_without_orders(self):
        self.confirm()
        AlternativeStore(self.catalog).seed_demo()
        self.store.close()
        with closing(sqlite3.connect(self.store.path)) as connection:
            for name in ('order_items','orders','demo_customers'): connection.execute('DROP TABLE '+name)
            connection.execute('PRAGMA user_version=3'); connection.commit()
        archive=self.root/'v3.zip'
        BackupService(self.store.path,self.store.evidence.root).create_backup(archive)
        self.assertEqual(validate_backup(archive)['schema_version'],3)
        RestoreService(self.store.path,self.store.evidence.root).restore_backup(archive)
        self.store.initialize()
        self.assertEqual(self.orders.history(),[])
        self.assertEqual(self.available(),5)
        self.assertEqual(len(AlternativeStore(self.catalog).find(self.config.product_ids[2])['alternatives']),1)

    def test_browser_accept_reject_insufficient_and_cancel(self):
        from playwright.sync_api import sync_playwright, expect
        self.confirm(5)
        with local_server(self.app()) as url, sync_playwright() as playwright:
            browser=playwright.chromium.launch()
            try:
                customer=browser.new_page(viewport={'width':390,'height':844})
                shop=browser.new_page(viewport={'width':1280,'height':900})
                errors=[]
                for page in (customer,shop): page.on('pageerror',lambda error:errors.append(str(error)))
                customer.goto(url+'/customer')
                customer.get_by_label('Search by product or brand').fill('Red Bull')
                customer.get_by_role('button',name='Search',exact=True).click()
                customer.locator('.product-choice').click()
                customer.get_by_label('Requested quantity').fill('2')
                customer.get_by_role('button',name='Request order from Demo Shop').click()
                expect(customer.locator('#order-feedback')).to_contain_text('Pending shop confirmation')
                customer.get_by_role('link',name='View your order requests').click()
                expect(customer.locator('.order-card')).to_have_attribute('data-status','PENDING')
                shop.goto(url+'/shopkeeper/orders')
                expect(shop.get_by_label('Order status')).to_have_value('PENDING')
                shop.get_by_label('I checked current availability').check()
                shop.get_by_role('button',name='Accept request').click()
                expect(shop.locator('#orders-message')).to_contain_text('Accepted')
                expect(shop.locator('.order-card')).to_have_count(0)
                customer.get_by_role('button',name='Refresh orders').click()
                expect(customer.locator('.order-card')).to_have_attribute('data-status','ACCEPTED')
                customer.goto(url+'/customer')
                customer.locator('[data-product-id="'+self.red+'"]').click()
                expect(customer.locator('.available-count')).to_contain_text('3 unreserved units')
                customer.get_by_label('Requested quantity').fill('1')
                customer.get_by_role('button',name='Request order from Demo Shop').click()
                expect(customer.locator('#order-feedback')).to_contain_text('Pending shop confirmation')
                shop.get_by_role('button',name='Refresh orders').click()
                shop.get_by_label('Rejection reason (optional)').fill('Currently unavailable')
                shop.get_by_role('button',name='Reject request').click()
                expect(shop.locator('#orders-message')).to_contain_text('Rejected')
                customer.goto(url+'/customer/orders')
                expect(customer.locator('.rejection-reason')).to_contain_text('Currently unavailable')
                customer.goto(url+'/customer')
                customer.locator('[data-product-id="'+self.red+'"]').click()
                customer.get_by_label('Requested quantity').fill('4')
                customer.get_by_role('button',name='Request order from Demo Shop').click()
                expect(customer.locator('#order-feedback')).to_contain_text('Pending shop confirmation')
                shop.get_by_role('button',name='Refresh orders').click()
                shop.get_by_label('I checked current availability').check()
                shop.get_by_role('button',name='Accept request').click()
                expect(shop.locator('#orders-error')).to_contain_text('Insufficient inventory')
                self.assertEqual(self.available(),3)
                customer.goto(url+'/customer/orders')
                expect(customer.locator('[data-status="PENDING"]')).to_have_count(1)
                self.assertTrue(customer.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                if os.environ.get('STOREROOM_V10_SMOKE'):
                    Path('outputs/v10').mkdir(parents=True,exist_ok=True)
                    customer.screenshot(path='outputs/v10/customer-orders.png',full_page=True)
                    shop.screenshot(path='outputs/v10/shopkeeper-orders.png',full_page=True)
                customer.get_by_role('button',name='Cancel request').click()
                expect(customer.locator('[data-status="CANCELLED"]')).to_have_count(1)
                expect(customer.locator('[data-status="ACCEPTED"]')).to_have_count(1)
                expect(customer.locator('[data-status="REJECTED"]')).to_have_count(1)
                shop.get_by_label('Order status').select_option('')
                shop.get_by_role('button',name='Refresh orders').click()
                expect(shop.locator('.order-card')).to_have_count(3)
                self.assertEqual(errors,[])
                if os.environ.get('STOREROOM_V10_SMOKE'):
                    Path('reports/v1_0_smoke.json').write_text(json.dumps({'passed':True,'browser':'Chromium',
                        'data':'temporary synthetic reviewed inventory; shared Demo Customer',
                        'checks':['search','shop quantity request 2','pending','shopkeeper inbox','accept',
                        'customer accepted','available 5 to 3','reject with reason','insufficient request remains pending',
                        'no extra reservation','cancel pending','history','mobile no overflow','no JavaScript errors'],
                        'model_inference':False},indent=2)+'\n')
            finally: browser.close()
