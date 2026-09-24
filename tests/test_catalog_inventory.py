"""Catalog/inventory product contracts; synthetic observations, no real inference."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.api import create_app
from src.storage import ScanStore, Scan, ScanItem
from src.catalog import CatalogProduct, Shop, ShopInventory, CatalogStore, SHOP_ID, normalize
from src.review import ReviewRequest
from src.inference.config import load_config
from src.backup import BackupService, RestoreService, validate_backup
from ui_support import FixtureDetector, staged_review, local_server, photo_bytes


class CatalogInventoryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.store = ScanStore(self.root/'history.db',self.root/'scans')
        self.store.initialize()
        self.addCleanup(self.store.close)
        self.catalog = CatalogStore(self.store,3600)
        self.config = load_config()

    def body(self, predicted=7, confirmed=5, class_id=0):
        return staged_review(self.store,[{'class_id':class_id,'class_name':self.config.names[class_id],
            'predicted_count':predicted,'confirmed_count':confirmed}])

    def confirm(self, predicted=7, confirmed=5, class_id=0):
        return self.store.confirm(ReviewRequest.model_validate(self.body(predicted,confirmed,class_id)))

    def app(self):
        return create_app(detector_factory=FixtureDetector,database_path=self.store.path,
            scan_storage_dir=self.store.evidence.root,output_dir=self.root/'annotations')

    def test_stable_catalog_and_shop_seed_is_idempotent(self):
        before = self.catalog.search()
        self.store.initialize()
        self.assertEqual(self.catalog.search(),before)
        self.assertEqual({p['product_id'] for p in before},set(self.config.product_ids))
        self.assertEqual(len(before),5)
        for product in before:
            self.assertIsNone(product['package_size'])
            self.assertIsNone(product['image_reference'])
            self.assertIsNone(product['category'])
            self.assertFalse(product['catalog_sku_verified'])
        self.assertEqual(self.catalog.inventory(),[])
        with Session(self.store.engine) as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Shop)),1)
            self.assertEqual(session.get(Shop,SHOP_ID).name,'Demo Shop')

    def test_deterministic_normalized_partial_brand_search(self):
        red = self.config.product_ids[0]
        for query in ['RED BULL','redbull',' Red--Bull ','Ｒｅｄ Ｂｕｌｌ','Bull']:
            self.assertEqual(self.catalog.search(query)[0]['product_id'],red)
        self.assertEqual([p['name'] for p in self.catalog.search('Valser')],['Valser Classic','Valser Still'])
        self.assertEqual(self.catalog.search('Pepsi'),[])
        self.assertEqual(self.catalog.search('%'),self.catalog.search(''))
        self.assertEqual(normalize('Capri-Sun'),'capri sun')

    def test_duplicate_catalog_shop_and_inventory_constraints(self):
        self.confirm()
        with self.assertRaises(IntegrityError):
            with Session(self.store.engine) as session, session.begin():
                session.add(ShopInventory(shop_id=SHOP_ID,product_id=self.config.product_ids[0],quantity=1,is_demo=True,
                    updated_at=datetime.now()))
        with self.assertRaises(IntegrityError):
            with Session(self.store.engine) as session, session.begin():
                session.add(Shop(shop_id=SHOP_ID,name='duplicate',created_at=datetime.now(),updated_at=datetime.now()))
        with self.assertRaises(IntegrityError):
            with Session(self.store.engine) as session, session.begin():
                session.add(CatalogProduct(product_id='duplicate',class_id=0,name='Red Bull',normalized_name='red bull',
                    metadata_source='test',created_at=datetime.now(),updated_at=datetime.now()))

    def test_inventory_uses_confirmed_count_preserves_ai(self):
        scan = self.confirm(7,5)
        row = self.catalog.inventory()[0]
        self.assertEqual(row['quantity'],5)
        self.assertEqual(row['source_scan_id'],str(scan.scan_id))
        self.assertEqual(row['last_confirmed_at'],scan.created_at.isoformat())
        self.assertEqual(self.store.get(scan.scan_id).items[0].predicted_count,7)
        self.assertEqual(len(self.store.get(scan.scan_id).detections),7)
        self.assertEqual(row['freshness'],'FRESH')
        self.assertFalse(row['guaranteed_available'])

    def test_replace_not_add_and_old_retry_does_not_revert_inventory(self):
        body = self.body(7,5)
        old = self.store.confirm(ReviewRequest.model_validate(body))
        new = self.confirm(2,1)
        self.assertEqual(self.store.confirm(ReviewRequest.model_validate(body)),old)
        row = self.catalog.inventory()[0]
        self.assertEqual(row['quantity'],1)
        self.assertEqual(row['source_scan_id'],str(new.scan_id))
        self.assertEqual(len(self.catalog.inventory()),1)

    def test_omitted_classes_preserved_explicit_zero_applied(self):
        self.confirm(7,5)
        self.confirm(3,2,class_id=1)
        self.assertEqual(self.catalog.inventory(self.config.product_ids[0])[0]['quantity'],5)
        self.confirm(0,0)
        self.assertEqual(self.catalog.inventory(self.config.product_ids[0])[0]['quantity'],0)
        self.assertEqual(len(self.catalog.inventory(availability='unavailable')),1)

    def test_freshness_boundary_stale_future_and_configuration(self):
        saved = self.confirm()
        for seconds, expected in [(0,'FRESH'),(3600,'FRESH'),(3601,'STALE'),(-1,'STALE')]:
            row = self.catalog.inventory(now=saved.created_at+timedelta(seconds=seconds))[0]
            self.assertEqual(row['freshness'],expected)
        with patch.dict('os.environ',{'INVENTORY_FRESHNESS_SECONDS':'60'}):
            self.assertEqual(CatalogStore(self.store).fresh_seconds,60)
        for value in ('0','-1','abc'):
            with patch.dict('os.environ',{'INVENTORY_FRESHNESS_SECONDS':value}),self.assertRaises(ValueError):
                CatalogStore(self.store)

    def test_demo_is_opt_in_distinct_and_never_overwrites_confirmed(self):
        self.catalog.seed_demo()
        before = self.catalog.inventory()
        self.catalog.seed_demo()
        self.assertEqual(self.catalog.inventory(),before)
        self.assertEqual(len(before),5)
        self.assertEqual(self.catalog.inventory(availability='available'),[])
        for row in before:
            self.assertEqual(row['freshness'],'DEMO')
            self.assertIsNone(row['last_confirmed_at'])
            self.assertIsNone(row['source_scan_id'])
        self.confirm(7,1)
        self.catalog.seed_demo()
        row = self.catalog.inventory(self.config.product_ids[0])[0]
        self.assertFalse(row['is_demo'])
        self.assertEqual(row['quantity'],1)

    def test_negative_quantity_or_missing_source_scan_rejected(self):
        scan = self.confirm()
        for quantity, id in [(-1,str(scan.scan_id)),(1.5,str(scan.scan_id)),(1,str(uuid4())),(1,None)]:
            with self.subTest(quantity=quantity,id=id), self.assertRaises(IntegrityError):
                with Session(self.store.engine) as session, session.begin():
                    row = session.get(ShopInventory,(SHOP_ID,self.config.product_ids[0]))
                    row.quantity, row.source_scan_id = quantity,id

    def test_scan_deletion_restricted_and_evidence_remains(self):
        scan = self.confirm()
        with self.assertRaises(IntegrityError):
            with Session(self.store.engine) as session, session.begin():
                session.delete(session.get(Scan,str(scan.scan_id)))
        self.assertEqual(self.store.get(scan.scan_id),scan)
        self.assertTrue(self.store.image(scan.scan_id,'original').exists())

    def test_inventory_failure_rolls_back_scan_and_keeps_previous_quantity(self):
        previous = self.confirm()
        def fail(mapper,connection,row):
            row.quantity = -1
        event.listen(ShopInventory,'before_update',fail)
        try:
            with self.assertRaises(IntegrityError):
                self.confirm(2,1)
        finally:
            event.remove(ShopInventory,'before_update',fail)
        self.assertEqual(len(self.store.recent()),1)
        self.assertEqual(self.catalog.inventory()[0]['source_scan_id'],str(previous.scan_id))
        self.assertEqual(len([p for p in self.store.evidence.root.iterdir() if p.is_dir() and p.name!='.pending']),1)

    def test_api_search_filters_detail_unknowns_and_history_routes(self):
        saved = self.confirm()
        with TestClient(self.app()) as client:
            self.assertEqual(client.get('/products/search?q=redbull').json()['products'][0]['name'],'Red Bull')
            self.assertEqual(len(client.get('/inventory?availability=available').json()['inventory']),1)
            self.assertEqual(client.get('/inventory?shop_id=other').json()['inventory'],[])
            self.assertEqual(client.get('/inventory?product_id=missing').json()['inventory'],[])
            self.assertEqual(client.get('/inventory?availability=unknown').status_code,422)
            detail = client.get('/inventory/'+self.config.product_ids[0]).json()
            self.assertEqual(detail['inventory'][0]['quantity'],5)
            self.assertEqual(client.get('/inventory/'+self.config.product_ids[1]).json()['inventory'],[])
            self.assertEqual(client.get('/inventory/missing').status_code,404)
            self.assertEqual(client.get('/inventory/scans/'+str(saved.scan_id)).status_code,200)
            self.assertEqual(len(client.get('/inventory/scans').json()['scans']),1)

    def test_current_schema_backup_roundtrip_preserves_catalog_inventory_evidence(self):
        self.catalog.seed_demo()
        saved = self.confirm()
        before = self.catalog.inventory(now=saved.created_at)
        archive = self.root/'backup.zip'
        self.assertEqual(BackupService(self.store.path,self.store.evidence.root).create_backup(archive)['schema_version'],3)
        self.store.close()
        RestoreService(self.store.path,self.store.evidence.root).restore_backup(archive)
        self.store.initialize()
        self.assertEqual(self.catalog.inventory(now=saved.created_at),before)
        self.assertEqual(self.store.get(saved.scan_id),saved)

    def test_old_schema_one_backup_restores_and_migrates_without_fabricated_inventory(self):
        saved = self.confirm()
        self.store.close()
        # A temporary fixture representing the previous three-table schema.
        with closing(sqlite3.connect(self.store.path)) as connection:
            for name in ('product_alternatives','product_metadata','shop_inventory','products','shops'):
                connection.execute('DROP TABLE '+name)
            connection.execute('PRAGMA user_version=1')
            connection.commit()
        archive = self.root/'v1.zip'
        BackupService(self.store.path,self.store.evidence.root).create_backup(archive)
        self.assertEqual(validate_backup(archive)['schema_version'],1)
        new = ScanStore(self.root/'restored.db',self.root/'restored-scans')
        try:
            RestoreService(new.path,new.evidence.root).restore_backup(archive)
            new.initialize()
            self.assertEqual(new.get(saved.scan_id),saved)
            self.assertEqual(CatalogStore(new).inventory(),[])
            self.assertEqual(len(CatalogStore(new).search()),5)
        finally:
            new.close()

    def test_customer_browser_search_unknown_demo_fresh_and_stale(self):
        from playwright.sync_api import sync_playwright, expect
        self.catalog.seed_demo()
        with local_server(self.app()) as url, sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={'width':390,'height':844})
                page.goto(url+'/customer')
                expect(page.locator('.product-choice')).to_have_count(5)
                page.get_by_label('Search by product or brand').fill('redbull')
                page.get_by_role('button',name='Search',exact=True).click()
                expect(page.locator('.product-choice')).to_have_count(1)
                page.locator('.product-choice').click()
                expect(page.locator('.status-badge')).to_contain_text('Demo quantities')
                saved = self.confirm()
                page.get_by_role('button',name='Refresh counts').click()
                expect(page.locator('.inventory-row')).to_have_attribute('data-freshness','FRESH')
                expect(page.locator('.quantity')).to_contain_text('5')
                expect(page.locator('time')).to_contain_text('Last confirmed:')
                with Session(self.store.engine) as session, session.begin():
                    session.get(ShopInventory,(SHOP_ID,self.config.product_ids[0])).last_confirmed_at = datetime.now()-timedelta(hours=2)
                page.get_by_role('button',name='Refresh counts').click()
                expect(page.locator('.inventory-row')).to_have_attribute('data-freshness','STALE')
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.get_by_label('Search by product or brand').fill('unmatched')
                page.get_by_role('button',name='Search',exact=True).click()
                expect(page.locator('#search-status')).to_have_text('No matching supported products.')
            finally:
                browser.close()
