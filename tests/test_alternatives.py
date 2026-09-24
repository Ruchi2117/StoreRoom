"""V0.9 uses synthetic catalog declarations and counts, never product-safety evidence."""
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import sqlite3
import tempfile
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.api import create_app
from src.storage import ScanStore
from src.catalog import CatalogStore, CatalogProduct, ProductAlternative, ProductMetadata, ShopInventory, SHOP_ID
from src.alternatives import AlternativeStore, Preferences
from src.review import ReviewRequest
from src.inference.config import load_config
from src.backup import BackupService, RestoreService, validate_backup
from ui_support import FixtureDetector, staged_review, local_server


class AlternativeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.store = ScanStore(self.root/'db.sqlite', self.root/'scans')
        self.store.initialize()
        self.addCleanup(self.store.close)
        self.catalog = CatalogStore(self.store)
        self.alts = AlternativeStore(self.catalog)
        self.ids = load_config().product_ids
        self.classic, self.still = self.ids[2:4]

    def app(self):
        return create_app(detector_factory=FixtureDetector, database_path=self.store.path,
            scan_storage_dir=self.store.evidence.root, output_dir=self.root/'annotations')

    def confirm(self, class_id, count):
        body = staged_review(self.store, [{'class_id':class_id, 'class_name':load_config().names[class_id],
            'predicted_count':count, 'confirmed_count':count}])
        return self.store.confirm(ReviewRequest.model_validate(body))

    def facts(self, product_id, facts, source='synthetic test declaration, not real product data'):
        with Session(self.store.engine) as session, session.begin():
            session.merge(ProductMetadata(product_id=product_id, facts=facts, source=source, updated_at=datetime.now()))

    def link(self, source, target, priority=1):
        with Session(self.store.engine) as session, session.begin():
            session.add(ProductAlternative(source_id=source,target_id=target,priority=priority,
                relationship_type='related_variant',is_demo=True,reason='Synthetic test relationship',created_at=datetime.now()))

    def test_no_fabrication_unknowns_and_opt_in_idempotent_demo(self):
        self.assertEqual(self.alts.find(self.classic)['alternatives'], [])
        self.alts.seed_demo()
        before = self.alts.find(self.classic)
        self.alts.seed_demo()
        self.assertEqual(before, self.alts.find(self.classic))
        item = before['alternatives'][0]
        self.assertEqual(item['product']['product_id'], self.still)
        self.assertTrue(item['is_demo'])
        self.assertEqual(item['preference_status'], 'not_assessed')
        self.assertTrue(all(value is None for value in item['metadata']['facts'].values()))
        for id in (self.ids[0], self.ids[1], self.ids[4]):
            self.assertEqual(self.alts.find(id)['alternatives'], [])

    def test_duplicate_self_unknown_target_invalid_priority_rejected(self):
        self.alts.seed_demo()
        for source, target, priority in [(self.classic,self.still,1), (self.classic,self.classic,1),
                (self.classic,'missing',1), (self.ids[0],self.still,-1), (self.ids[0],self.still,1.5)]:
            with self.subTest(target=target,priority=priority), self.assertRaises(IntegrityError):
                self.link(source,target,priority)

    def test_unknown_metadata_excludes_each_restrictive_preference(self):
        self.alts.seed_demo()
        for values in ({'diet':'vegan'}, {'avoid_allergens':['milk']}, {'avoid_ingredients':['caffeine']}, {'same_category':True}):
            result = self.alts.find(self.classic,Preferences(**values))
            self.assertEqual(result['alternatives'], [])
            self.assertEqual(result['excluded'][0]['checks'][0]['status'], 'unknown')
        self.assertEqual(self.alts.find(self.classic,Preferences(same_variant=True))['excluded'][0]['checks'][0]['status'], 'conflict')

    def test_explicit_declarations_match_presence_wins_and_absence_is_not_inferred(self):
        self.alts.seed_demo()
        self.facts(self.still, {'dietary_tags':['vegan'], 'ingredients':[], 'allergen_tags':[],
            'free_from_allergens':['milk'], 'free_from_ingredients':['caffeine']})
        prefs = Preferences(diet='vegan',avoid_allergens=[' MILK '],avoid_ingredients=['Caffeine'])
        self.assertEqual(len(self.alts.find(self.classic,prefs)['alternatives']),1)
        self.assertEqual(self.alts.find(self.classic,Preferences(avoid_allergens=['nuts']))['alternatives'],[])
        self.facts(self.still, {'allergen_tags':['milk'], 'free_from_allergens':['milk']})
        self.assertEqual(self.alts.find(self.classic,prefs)['excluded'][0]['checks'][1]['status'],'conflict')

    def test_unsourced_or_malformed_metadata_cannot_establish_match(self):
        self.alts.seed_demo()
        for facts,source in [({'dietary_tags':['vegan']},''), ({'dietary_tags':'vegan'},'fixture')]:
            self.facts(self.still,facts,source)
            self.assertEqual(self.alts.find(self.classic,Preferences(diet='vegan'))['alternatives'],[])

    def test_same_category_requires_known_equality_and_does_not_create_edges(self):
        with Session(self.store.engine) as session, session.begin():
            for product in session.scalars(select(CatalogProduct)):
                product.category='synthetic category'
        self.assertEqual(self.alts.find(self.classic)['alternatives'],[])
        self.alts.seed_demo()
        self.assertEqual(len(self.alts.find(self.classic,Preferences(same_category=True))['alternatives']),1)
        with Session(self.store.engine) as session, session.begin():
            session.get(CatalogProduct,self.still).category='different synthetic category'
        self.assertEqual(self.alts.find(self.classic,Preferences(same_category=True))['alternatives'],[])

    def test_inventory_unknown_demo_fresh_zero_and_stale(self):
        self.alts.seed_demo()
        def state(): return self.alts.find(self.classic)['alternatives'][0]['availability']
        self.assertEqual(state(),'UNKNOWN')
        self.catalog.seed_demo()
        self.assertEqual(state(),'DEMO')
        self.confirm(3,2)
        self.assertEqual(state(),'RECENT_POSITIVE')
        self.confirm(3,0)
        self.assertEqual(state(),'RECENT_ZERO')
        with Session(self.store.engine) as session, session.begin():
            session.get(ShopInventory,(SHOP_ID,self.still)).last_confirmed_at=datetime.now()-timedelta(hours=2)
        self.assertEqual(state(),'STALE')

    def test_ranking_fresh_first_priority_then_stable_id(self):
        # Artificial graph in a disposable fixture, never seeded into the application.
        for id,priority in [(self.ids[1],1),(self.classic,2),(self.still,2)]:
            self.link(self.ids[0],id,priority)
        def order(): return [c['product']['product_id'] for c in self.alts.find(self.ids[0])['alternatives']]
        self.assertEqual(order(),[self.ids[1],self.classic,self.still])
        self.confirm(3,1)
        self.assertEqual(order(),[self.still,self.ids[1],self.classic])
        self.assertEqual(order(),order())

    def test_api_contract_validation_search_and_no_persistence(self):
        self.alts.seed_demo()
        with TestClient(self.app()) as client:
            path='/products/'+self.classic+'/alternatives'
            self.assertEqual(len(client.get(path).json()['alternatives']),1)
            self.assertEqual(client.get('/products/missing/alternatives').status_code,404)
            response=client.post(path,json={'diet':'vegan'})
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertEqual(response.json()['alternatives'],[])
            self.assertEqual(len(client.get(path).json()['alternatives']),1)
            for bad in ({'diet':'medical'}, {'unknown':True}, {'same_category':'true'}, {'avoid_allergens':['!!!']}, {'avoid_ingredients':['a']*21}):
                self.assertEqual(client.post(path,json=bad).status_code,422)
            self.assertIsNone(client.get('/products/search?q=valser').json()['products'][0]['metadata']['facts']['ingredients'])

    def test_current_schema_backup_preserves_relationships_and_metadata(self):
        self.alts.seed_demo()
        self.facts(self.still,{'ingredients':['fixture only']})
        self.confirm(3,2)
        before=self.alts.find(self.classic)['alternatives'][0]
        archive=self.root/'snapshot.zip'
        self.assertEqual(BackupService(self.store.path,self.store.evidence.root).create_backup(archive)['schema_version'],4)
        self.store.close()
        RestoreService(self.store.path,self.store.evidence.root).restore_backup(archive)
        self.store.initialize()
        after=self.alts.find(self.classic)['alternatives'][0]
        self.assertEqual(before['metadata'],after['metadata'])
        self.assertEqual(before['match_reason'],after['match_reason'])
        self.assertEqual(before['inventory'][0]['source_scan_id'],after['inventory'][0]['source_scan_id'])

    def test_schema_two_backup_restores_then_additively_migrates(self):
        saved=self.confirm(3,2)
        before=self.catalog.search()
        self.store.close()
        with closing(sqlite3.connect(self.store.path)) as connection:
            for name in ('order_items','orders','demo_customers'):
                connection.execute('DROP TABLE '+name)
            connection.execute('DROP TABLE product_alternatives')
            connection.execute('DROP TABLE product_metadata')
            connection.execute('PRAGMA user_version=2')
            connection.commit()
        archive=self.root/'v2.zip'
        BackupService(self.store.path,self.store.evidence.root).create_backup(archive)
        self.assertEqual(validate_backup(archive)['schema_version'],2)
        RestoreService(self.store.path,self.store.evidence.root).restore_backup(archive)
        self.store.initialize()
        self.assertEqual(self.catalog.search(),before)
        self.assertEqual(self.store.get(saved.scan_id),saved)
        self.assertEqual(self.alts.find(self.classic)['alternatives'],[])

    def test_browser_discovery_preferences_freshness_and_no_alternatives(self):
        from playwright.sync_api import sync_playwright, expect
        self.alts.seed_demo()
        self.confirm(2,2)
        self.confirm(3,3)
        with local_server(self.app()) as url, sync_playwright() as playwright:
            browser=playwright.chromium.launch()
            try:
                page=browser.new_page(viewport={'width':390,'height':844})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(url+'/customer')
                page.get_by_label('Search by product or brand').fill('Valser')
                page.get_by_role('button',name='Search',exact=True).click()
                page.locator('[data-product-id="'+self.classic+'"]').click()
                expect(page.locator('#inventory-results .quantity')).to_contain_text('2')
                expect(page.locator('#alternatives-panel')).to_be_hidden()
                with Session(self.store.engine) as session, session.begin():
                    session.get(ShopInventory,(SHOP_ID,self.classic)).last_confirmed_at=datetime.now()-timedelta(hours=2)
                page.get_by_role('button',name='Refresh counts').click()
                expect(page.locator('#inventory-results .inventory-row')).to_have_attribute('data-freshness','STALE')
                expect(page.locator('.alternative-card')).to_have_count(1)
                expect(page.locator('.alternative-card')).to_contain_text('Demo catalog relationship')
                expect(page.locator('.alternative-card')).to_contain_text('different named variant')
                expect(page.locator('.alternative-inventory')).to_have_attribute('data-freshness','FRESH')
                expect(page.locator('.alternative-inventory time')).to_contain_text('Last confirmed:')
                page.get_by_label('Same named variant').check()
                page.get_by_role('button',name='Apply preferences').click()
                expect(page.locator('#alternatives-results')).to_contain_text('excluded')
                expect(page.locator('.alternative-card')).to_have_count(0)
                page.get_by_label('Same named variant').uncheck()
                page.get_by_label('Dietary preference').select_option('vegan')
                page.get_by_role('button',name='Apply preferences').click()
                expect(page.locator('#alternatives-results')).to_contain_text('No suitable alternatives')
                page.get_by_label('Dietary preference').select_option('')
                with Session(self.store.engine) as session, session.begin():
                    session.get(ShopInventory,(SHOP_ID,self.still)).last_confirmed_at=datetime.now()-timedelta(hours=2)
                page.get_by_role('button',name='Apply preferences').click()
                expect(page.locator('.alternative-inventory')).to_have_attribute('data-freshness','STALE')
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                if os.environ.get('STOREROOM_V09_SMOKE'):
                    Path('outputs/v09').mkdir(parents=True,exist_ok=True)
                    page.screenshot(path='outputs/v09/customer-mobile.png',full_page=True)
                    page.set_viewport_size({'width':1280,'height':1000})
                    page.screenshot(path='outputs/v09/customer-desktop.png',full_page=True)
                page.get_by_label('Search by product or brand').fill('Red Bull')
                page.get_by_role('button',name='Search',exact=True).click()
                page.locator('.product-choice').click()
                expect(page.locator('#alternatives-results')).to_contain_text('No suitable alternatives')
                self.assertEqual(errors,[])
                if os.environ.get('STOREROOM_V09_SMOKE'):
                    Path('reports/v0_9_smoke.json').write_text(json.dumps({'passed':True,
                        'browser':'Chromium', 'data':'temporary synthetic reviewed counts; demo Valser relationships',
                        'checks':['search','fresh count','stale requested product','related variant reason','demo label',
                        'fresh alternative timestamp','conflicting variant excluded','unknown vegan metadata excluded',
                        'stale alternative label','mobile overflow','no Red Bull alternatives','no JavaScript errors'],
                        'model_inference':False},indent=2)+'\n')
            finally:
                browser.close()
