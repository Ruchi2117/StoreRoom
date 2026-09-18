import copy
import tempfile
import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from src.api import create_app
from ui_support import FixtureDetector


class ReviewTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.detector = FixtureDetector(output_dir=directory)
        self.client = self.enterContext(TestClient(create_app(
            detector_factory=lambda **_: self.detector, output_dir=directory)))
        self.payload = {'items': [{'class_id': 0, 'class_name': 'Red Bull',
                                 'predicted_count': 2, 'confirmed_count': 1}]}

    def test_valid_confirmation_preserves_prediction_and_does_not_infer(self):
        response = self.client.post('/inventory/confirm', json=self.payload)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['items'], self.payload['items'])
        self.assertEqual(result['status'], 'confirmed')
        self.assertFalse(result['persisted'])
        self.assertEqual(result['count_meaning'], 'visible_items')
        self.assertIsNotNone(datetime.fromisoformat(result['confirmed_at']).tzinfo)
        self.assertEqual(self.detector.calls, 0)

    def test_invalid_ids_and_names(self):
        for key, value in [('class_id', -1), ('class_id', 5), ('class_id', True),
                           ('class_id', '0'), ('class_name', 'Pepsi'), ('class_name', 'Knoppers')]:
            with self.subTest(key=key, value=value):
                body = copy.deepcopy(self.payload)
                body['items'][0][key] = value
                self.assertEqual(self.client.post('/inventory/confirm', json=body).status_code, 422)

    def test_counts_are_strict_nonnegative_integers(self):
        for key in ['predicted_count', 'confirmed_count']:
            for value in [-1, 1.5, True, '2', None, 9007199254740992]:
                with self.subTest(key=key, value=value):
                    body = copy.deepcopy(self.payload)
                    body['items'][0][key] = value
                    self.assertEqual(self.client.post('/inventory/confirm', json=body).status_code, 422)

    def test_malformed_extra_and_duplicate_items_rejected(self):
        for body in [{}, {'items': None}, {'items': [{}]}, {'items': self.payload['items'] * 2},
                     {**self.payload, 'price': 10}, {'items': [{**self.payload['items'][0], 'sku': 'invented'}]}]:
            with self.subTest(body=body):
                self.assertEqual(self.client.post('/inventory/confirm', json=body).status_code, 422)
        self.assertEqual(self.client.post('/inventory/confirm', content='invalid',
            headers={'Content-Type': 'application/json'}).status_code, 422)

    def test_empty_and_corrected_to_zero_reviews_are_explicitly_allowed(self):
        self.assertEqual(self.client.post('/inventory/confirm', json={'items': []}).json()['items'], [])
        self.payload['items'][0]['confirmed_count'] = 0
        self.assertEqual(self.client.post('/inventory/confirm', json=self.payload).status_code, 200)

    def test_ui_and_static_assets_served(self):
        self.assertIn('Review before confirming', self.client.get('/').text)
        self.assertEqual(self.client.get('/static/app.js').status_code, 200)
        self.assertEqual(self.client.get('/static/style.css').status_code, 200)
        self.assertEqual(self.client.get('/health').json(), {'status': 'ok'})
