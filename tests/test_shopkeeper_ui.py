"""Real browser + real HTTP, with deterministic inference instead of trained weights."""
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
        cls.server = local_server(create_app(detector_factory=lambda **_: cls.detector, output_dir=cls.temp.name))
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
        expect(self.page.locator('#confirmed')).to_contain_text('Not saved permanently')
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
