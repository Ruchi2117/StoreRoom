"""Evidence invariants and local failure recovery; no model or dataset required."""
from io import BytesIO
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.api import create_app
from src.evidence import EvidenceFiles
from src.storage import Scan, ScanDetection, ScanItem, ScanStore
from ui_support import FixtureDetector, staged_review, photo_bytes


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.db = self.root/'history.db'
        self.files = self.root/'scans'
        self.client = self.enterContext(TestClient(self.app()))
        self.store = self.client.app.state.store
        self.body = staged_review(self.store, [dict(class_id=0, class_name='Red Bull', predicted_count=8, confirmed_count=7)])

    def app(self):
        return create_app(detector_factory=FixtureDetector, output_dir=self.root/'annotations',
                          database_path=self.db, scan_storage_dir=self.files)

    def confirm(self):
        response = self.client.post('/inventory/confirm', json=self.body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_original_bytes_paths_detections_and_nondestructive_correction(self):
        result = self.confirm()
        self.assertEqual(result['items'][0]['predicted_count'], 8)
        self.assertEqual(result['items'][0]['confirmed_count'], 7)
        self.assertEqual(len(result['detections']), 8)
        self.assertEqual(result['detections'][0], {'class_id':0, 'class_name':'Red Bull',
            'confidence':.8125, 'bbox':[1.5,2.5,20.5,30.5]})
        self.assertEqual(result['original_prediction']['products'][0]['count'], 8)
        self.assertEqual(len(result['original_prediction']['products']), 5)
        original = self.client.get(result['original_image_url'])
        annotated = self.client.get(result['annotated_image_url'])
        self.assertEqual(original.content, photo_bytes())
        self.assertEqual(original.headers['content-type'], 'image/png')
        self.assertEqual(annotated.headers['content-type'], 'image/jpeg')
        with Session(self.store.engine) as session:
            scan = session.get(Scan, result['scan_id'])
            self.assertEqual(scan.source_image_path, result['scan_id']+'/original.png')
            self.assertEqual(scan.annotated_image_path, result['scan_id']+'/annotated.jpg')
            self.assertEqual(len(scan.detections), 8)
        self.assertFalse(self.store.evidence.directory(self.body['prediction_id'], pending=True).exists())

    def test_evidence_reopens_through_new_app_without_overwriting_prediction(self):
        saved = self.confirm()
        with TestClient(self.app()) as client:
            for _ in range(2):
                self.assertEqual(client.get('/inventory/scans/'+saved['scan_id']).json(), saved)
                self.assertEqual(client.get(saved['original_image_url']).content, photo_bytes())
                self.assertEqual(client.get(saved['annotated_image_url']).status_code, 200)

    def test_prediction_tampering_missing_classes_and_client_paths_rejected(self):
        changed = {**self.body, 'items': [{**self.body['items'][0], 'predicted_count':7}]}
        self.assertEqual(self.client.post('/inventory/confirm', json=changed).status_code, 422)
        self.assertEqual(self.client.post('/inventory/confirm', json={**self.body, 'items':[]}).status_code, 422)
        self.assertEqual(self.client.post('/inventory/confirm', json={**self.body, 'source_image_path':'../private'}).status_code, 422)
        self.assertEqual(self.client.post('/inventory/confirm', json={'items':self.body['items']}).status_code, 422)
        self.assertEqual(self.client.post('/inventory/confirm', json={**self.body, 'prediction_id':str(uuid4())}).status_code, 404)
        self.assertEqual(self.client.get('/inventory/scans').json()['scans'], [])

    def test_retry_is_idempotent_and_conflicting_correction_cannot_mutate_scan(self):
        saved = self.confirm()
        self.assertEqual(self.confirm(), saved)
        changed = {**self.body, 'items': [{**self.body['items'][0], 'confirmed_count':6}]}
        self.assertEqual(self.client.post('/inventory/confirm', json=changed).status_code, 409)
        self.assertEqual(len(self.client.get('/inventory/scans').json()['scans']), 1)
        self.assertEqual(self.client.get('/inventory/scans/'+saved['scan_id']).json(), saved)

    def test_missing_images_unknown_ids_and_traversal(self):
        saved = self.confirm()
        self.assertEqual(self.client.get('/inventory/scans/'+str(uuid4())+'/original').status_code, 404)
        self.assertEqual(self.client.get('/inventory/scans/not-a-uuid/original').status_code, 422)
        self.assertIn(self.client.get('/inventory/scans/..%2F..%2Fprivate/original').status_code, [404,422])
        image = self.store.image(saved['scan_id'], 'original')
        image.unlink()  # Explicit temporary test fixture, never project/user data.
        self.assertEqual(self.client.get(saved['original_image_url']).status_code, 404)
        with Session(self.store.engine) as session, session.begin():
            session.get(Scan, saved['scan_id']).annotated_image_path = '../private.jpg'
        self.assertEqual(self.client.get(saved['annotated_image_url']).status_code, 404)
        self.assertNotIn(str(self.root), self.client.get('/inventory/scans/'+saved['scan_id']).text)

    def test_detection_insert_failure_rolls_back_all_rows_and_published_files(self):
        def fail(mapper, connection, target): target.confidence = -1
        event.listen(ScanDetection, 'before_insert', fail)
        try:
            response = self.client.post('/inventory/confirm', json=self.body)
        finally:
            event.remove(ScanDetection, 'before_insert', fail)
        self.assertEqual(response.status_code, 503)
        with Session(self.store.engine) as session:
            for table in [Scan, ScanItem, ScanDetection]:
                self.assertEqual(session.scalar(select(func.count()).select_from(table)), 0)
        self.assertEqual([p.name for p in self.files.iterdir()], ['.pending'])
        self.assertTrue(self.store.evidence.directory(self.body['prediction_id'], pending=True).is_dir())
        self.confirm()  # Retained draft can be retried after the failed transaction.

    def test_copy_failure_cleans_partial_directory_without_scan(self):
        import shutil
        real_copy = shutil.copyfile
        def fail_second(source, target):
            if Path(source).name == 'annotated.jpg': raise OSError('injected disk failure')
            return real_copy(source, target)
        with patch('src.evidence.shutil.copyfile', side_effect=fail_second):
            response = self.client.post('/inventory/confirm', json=self.body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual([p.name for p in self.files.iterdir()], ['.pending'])
        self.assertEqual(self.store.recent(), [])

    def test_jpeg_upload_bytes_and_single_inference_survive_client_filename(self):
        stream = BytesIO(); Image.new('RGB', (60,40), 'blue').save(stream, format='JPEG')
        data = stream.getvalue()
        response = self.client.post('/predict?annotate=false', files={'file':('../../private.png', data, 'image/jpeg')})
        self.assertEqual(response.status_code, 200, response.text)
        predicted = response.json()
        self.assertIsNone(predicted['annotated_image'])
        body = {'prediction_id':predicted['prediction_id'], 'items':[
            {'class_id':p['class_id'], 'class_name':p['class_name'], 'predicted_count':p['count'], 'confirmed_count':p['count']}
            for p in predicted['products'] if p['count']]}
        saved = self.client.post('/inventory/confirm', json=body).json()
        self.assertEqual(self.client.get(saved['original_image_url']).content, data)
        self.assertEqual(self.client.get(saved['original_image_url']).headers['content-type'], 'image/jpeg')
        self.assertEqual(self.client.get(saved['annotated_image_url']).status_code, 200)
        self.assertEqual(self.client.app.state.detector.calls, 1)

    def test_damaged_pending_file_cannot_create_a_scan(self):
        path = self.store.evidence.directory(self.body['prediction_id'], pending=True)/'original.png'
        path.write_bytes(b'damaged fixture')
        self.assertEqual(self.client.post('/inventory/confirm', json=self.body).status_code, 409)
        self.assertEqual(self.store.recent(), [])

    def test_legacy_migration_preserves_old_scan_without_fabricating_evidence(self):
        db = self.root/'v04.db'; id = str(uuid4())
        with closing(sqlite3.connect(db)) as connection:
            connection.executescript('''CREATE TABLE scans (id VARCHAR(36) PRIMARY KEY, created_at DATETIME NOT NULL, status VARCHAR(16) NOT NULL);
                CREATE TABLE scan_items (id INTEGER PRIMARY KEY, scan_id VARCHAR(36) NOT NULL, class_id INTEGER NOT NULL,
                class_name VARCHAR(100) NOT NULL, predicted_count INTEGER NOT NULL, confirmed_count INTEGER NOT NULL);''')
            connection.execute('INSERT INTO scans VALUES (?, ?, ?)', (id, '2026-01-01 00:00:00.000000', 'confirmed'))
            connection.execute('INSERT INTO scan_items VALUES (1, ?, 0, ?, 8, 7)', (id, 'Red Bull'))
            connection.commit()
        store = ScanStore(db, self.root/'legacy-images')
        try:
            store.initialize(); store.initialize()
            result = store.get(id)
            self.assertEqual(result.items[0].predicted_count, 8)
            self.assertEqual(result.items[0].confirmed_count, 7)
            self.assertIsNone(result.original_prediction)
            self.assertIsNone(result.original_image_url)
            self.assertIsNone(store.image(id, 'original'))
        finally: store.close()

    def test_storage_root_is_configurable(self):
        with patch.dict('os.environ', {'SCAN_STORAGE_DIR': str(self.root/'custom')}):
            self.assertEqual(EvidenceFiles().root, self.root/'custom')
