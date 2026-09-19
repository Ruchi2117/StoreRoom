"""Real browser + real HTTP, with deterministic inference instead of trained weights."""
from pathlib import Path
import tempfile
import unittest
from playwright.sync_api import sync_playwright, expect
from src.api import create_app
from ui_support import FixtureDetector, local_server, photo_bytes


class ShopkeeperBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.detector = FixtureDetector(output_dir=cls.temp.name)
        cls.server = local_server(create_app(detector_factory=lambda **_: cls.detector, output_dir=cls.temp.name, database_path=Path(cls.temp.name)/"test.db", scan_storage_dir=Path(cls.temp.name)/"scans"))
        cls.url = cls.server.__enter__()
        cls.addClassCleanup(cls.server.__exit__, None, None, None)
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch()
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.detector.empty = False
        self.page.goto(self.url)

    def upload(self):
        self.page.locator('#file').set_input_files({'name': 'shelf.png', 'mimeType': 'image/png', 'buffer': photo_bytes()})

    def review(self):
        self.upload()
        self.page.get_by_role('button', name='Analyse shelf photo').click()
        expect(self.page.locator('#review')).to_be_visible()

    def test_upload_preview_loading_and_prediction_render(self):
        self.upload()
        expect(self.page.locator('#preview')).to_be_visible()
        self.page.route('**/predict?annotate=true', lambda route: route.abort())
        self.page.get_by_role('button', name='Analyse shelf photo').click()
        expect(self.page.locator('#error')).to_contain_text('Couldn’t reach StoreRoom')
        self.page.unroute('**/predict?annotate=true')
        self.page.get_by_role('button', name='Analyse shelf photo').click()
        expect(self.page.locator('#review')).to_be_visible()
        expect(self.page.locator('#products .product-row')).to_have_count(2)
        expect(self.page.locator('#ai-total')).to_have_text('AI detected 3')
        expect(self.page.locator('#annotated')).to_be_visible()
        self.assertTrue(self.page.locator('#annotated').evaluate('(img) => img.complete && img.naturalWidth > 0'))

    def test_correction_confirmation_and_new_scan(self):
        self.review()
        self.page.get_by_role('button', name='Increase Red Bull', exact=True).click()
        expect(self.page.get_by_label('Red Bull confirmed count')).to_have_value('3')
        self.page.get_by_role('button', name='Decrease Red Bull', exact=True).click()
        self.page.get_by_role('button', name='Decrease Red Bull', exact=True).click()
        expect(self.page.get_by_label('Red Bull confirmed count')).to_have_value('1')
        expect(self.page.locator('[data-class-id="0"] .prediction')).to_have_text('AI detected 2')
        with self.page.expect_response('**/inventory/confirm') as event:
            self.page.get_by_role('button', name='Confirm Inventory').click()
        self.assertEqual(event.value.json()['items'][0]['predicted_count'], 2)
        self.assertEqual(event.value.json()['items'][0]['confirmed_count'], 1)
        expect(self.page.locator('#confirmed')).to_be_visible()
        expect(self.page.locator('#confirmed-items')).to_contain_text('AI detected 2 → You confirmed 1')
        expect(self.page.locator('#confirmed')).to_contain_text('Saved on this device')
        self.page.locator('#confirmed .new-scan').click()
        expect(self.page.locator('#scan')).to_be_visible()
        expect(self.page.locator('#preview')).to_be_hidden()
        expect(self.page.locator('#analyse')).to_be_disabled()
        expect(self.page.locator('#confirmed-items')).to_be_empty()
        self.review()
        expect(self.page.get_by_label('Red Bull confirmed count')).to_have_value('2')

    def test_zero_boundary_invalid_typed_count_and_missing_product(self):
        self.review()
        self.page.get_by_label('Red Bull confirmed count').fill('0')
        self.page.get_by_label('Red Bull confirmed count').press('Tab')
        expect(self.page.get_by_role('button', name='Decrease Red Bull', exact=True)).to_be_disabled()
        for value in ['-1', '1.5', '']:
            self.page.get_by_label('Red Bull confirmed count').fill(value)
            self.page.get_by_label('Red Bull confirmed count').press('Tab')
            expect(self.page.get_by_label('Red Bull confirmed count')).to_have_value('0')
        expect(self.page.locator('[data-class-id="0"] .prediction')).to_have_text('AI detected 2')
        self.page.locator('#missed summary').click()
        self.page.get_by_role('button', name='+ Knoppers', exact=True).click()
        self.page.get_by_role('button', name='Increase Knoppers', exact=True).click()
        expect(self.page.locator('[data-class-id="1"] .prediction')).to_have_text('AI detected 0')
        expect(self.page.get_by_label('Knoppers confirmed count')).to_have_value('1')

    def test_empty_result_can_be_reviewed_without_claiming_empty_shelf(self):
        self.detector.empty = True
        self.review()
        expect(self.page.locator('#empty')).to_contain_text('does not mean the shelf is empty')
        expect(self.page.locator('#products .product-row')).to_have_count(0)
        self.page.get_by_role('button', name='Confirm Inventory').click()
        expect(self.page.locator('#confirmed-items')).to_contain_text('No supported products confirmed')

    def test_invalid_upload_and_retry(self):
        self.page.locator('#file').set_input_files({'name':'broken.png', 'mimeType':'image/png', 'buffer':b'bad bytes'})
        self.page.get_by_role('button', name='Analyse shelf photo').click()
        expect(self.page.locator('#error')).to_contain_text('cannot be decoded')
        expect(self.page.locator('#scan')).to_be_visible()
        self.review()
        expect(self.page.locator('#error')).to_be_hidden()

    def test_confirmation_failure_preserves_edits_and_can_retry(self):
        self.review()
        self.page.get_by_role('button', name='Increase Red Bull', exact=True).click()
        self.page.route('**/inventory/confirm', lambda route: route.fulfill(status=500, json={'detail':'Please retry confirmation'}))
        self.page.get_by_role('button', name='Confirm Inventory').click()
        expect(self.page.locator('#error')).to_have_text('Please retry confirmation')
        expect(self.page.get_by_label('Red Bull confirmed count')).to_have_value('3')
        self.page.unroute('**/inventory/confirm')
        self.page.get_by_role('button', name='Confirm Inventory').click()
        expect(self.page.locator('#confirmed')).to_be_visible()

    def test_loading_cancel_does_not_restore_old_results(self):
        self.upload()
        held = []
        self.page.route('**/predict?annotate=true', lambda route: held.append(route))
        self.page.get_by_role('button', name='Analyse shelf photo').click()
        expect(self.page.locator('#loading')).to_be_visible()
        expect(self.page.locator('#analyse')).to_be_disabled()
        self.page.get_by_role('button', name='Cancel scan').click()
        expect(self.page.locator('#loading')).to_be_hidden()
        expect(self.page.locator('#analyse')).to_be_disabled()
        for route in held:
            route.fulfill(status=200, json={'products': [], 'total_count': 0})
        expect(self.page.locator('#review')).to_be_hidden()

    def test_mobile_has_no_horizontal_overflow(self):
        self.review()
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))

    def test_saved_history_survives_refresh_and_opens_read_only(self):
        self.review()
        self.page.get_by_role('button', name='Decrease Red Bull', exact=True).click()
        with self.page.expect_response('**/inventory/confirm') as response:
            self.page.get_by_role('button', name='Confirm Inventory').click()
        first = response.value.json()['scan_id']
        self.page.reload()
        self.page.get_by_role('button', name='Scan History', exact=True).click()
        row = self.page.locator(f'[data-scan-id="{first}"]')
        expect(row).to_be_visible()
        expect(row).to_contain_text('2 product classes')
        self.page.get_by_role('button', name='Refresh history').click()
        row.get_by_role('button', name='Open scan').click()
        expect(self.page.locator('#saved-items')).to_contain_text('AI detected 2 → You confirmed 1')
        expect(self.page.locator('#saved-scan input')).to_have_count(0)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        self.page.locator('#saved-scan .new-scan').click()
        self.review()
        with self.page.expect_response('**/inventory/confirm') as response:
            self.page.get_by_role('button', name='Confirm Inventory').click()
        second = response.value.json()['scan_id']
        self.page.get_by_role('button', name='View Scan History', exact=True).click()
        expect(self.page.locator(f'[data-scan-id="{first}"]')).to_be_visible()
        expect(self.page.locator(f'[data-scan-id="{second}"]')).to_be_visible()

    def test_history_failure_retry_and_return_preserves_current_edits(self):
        self.review()
        self.page.get_by_role('button', name='Increase Red Bull', exact=True).click()
        self.page.route('**/inventory/scans?limit=20', lambda route: route.abort())
        self.page.get_by_role('button', name='Scan History', exact=True).click()
        expect(self.page.locator('#error')).to_contain_text('Couldn’t load saved scans')
        self.page.unroute('**/inventory/scans?limit=20')
        self.page.get_by_role('button', name='Refresh history').click()
        expect(self.page.locator('#history-loading')).to_be_hidden()
        self.page.get_by_role('button', name='Back to current scan').click()
        expect(self.page.get_by_label('Red Bull confirmed count')).to_have_value('3')

    def test_history_empty_and_missing_scan_messages(self):
        self.page.route('**/inventory/scans?limit=20', lambda route: route.fulfill(json={'scans': []}))
        self.page.get_by_role('button', name='Scan History', exact=True).click()
        expect(self.page.locator('#history-empty')).to_contain_text('No saved scans yet')
        self.page.unroute('**/inventory/scans?limit=20')
        self.page.locator('#history .new-scan').click()
        self.review()
        self.page.get_by_role('button', name='Confirm Inventory').click()
        self.page.get_by_role('button', name='View Scan History', exact=True).click()
        self.page.route('**/inventory/scans/*', lambda route: route.fulfill(status=404, json={'detail':'Scan not found'}))
        self.page.locator('#history-list .history-row').first.get_by_role('button', name='Open scan').click()
        expect(self.page.locator('#error')).to_have_text('Scan not found')
        expect(self.page.locator('#saved-receipt')).to_be_hidden()

    def test_historical_evidence_and_correction_are_visible_after_refresh(self):
        self.review()
        self.page.get_by_role('button', name='Decrease Red Bull', exact=True).click()
        with self.page.expect_response('**/inventory/confirm') as response:
            self.page.get_by_role('button', name='Confirm Inventory').click()
        id = response.value.json()['scan_id']
        self.page.reload()
        self.page.get_by_role('button', name='Scan History', exact=True).click()
        self.page.locator(f'[data-scan-id="{id}"]').get_by_role('button', name='Open scan').click()
        expect(self.page.locator('#saved-evidence')).to_be_visible()
        for image in ['saved-original', 'saved-annotated']:
            self.page.locator('#'+image).evaluate('(img) => img.decode()')
            expect(self.page.locator('#'+image)).to_be_visible()
        expect(self.page.locator('#saved-ai-counts')).to_contain_text('Red Bull: 2')
        expect(self.page.locator('#saved-items')).to_contain_text('AI detected 2 → You confirmed 1')
        expect(self.page.locator('#saved-items .correction')).to_have_count(1)
