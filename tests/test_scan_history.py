"""Durability, transaction and HTTP contracts using isolated SQLite files."""
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from src.api import create_app
from src.review import ReviewRequest
from src.storage import ScanStore, Scan, ScanItem, database_path
from src.inference.config import ROOT
from ui_support import FixtureDetector, staged_review


class ScanHistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.directory / 'nested/history.db'
        self.store = ScanStore(self.path, self.directory/"scans")
        self.addCleanup(self.store.close)
        self.store.initialize()
        self.body = {'items': [
            {'class_id': 0, 'class_name': 'Red Bull', 'predicted_count': 4, 'confirmed_count': 3},
            {'class_id': 2, 'class_name': 'Valser Classic', 'predicted_count': 1, 'confirmed_count': 0}]}
        self.body = staged_review(self.store, self.body['items'])
        self.review = ReviewRequest.model_validate(self.body)

    def app(self):
        return create_app(detector_factory=FixtureDetector, output_dir=self.directory/'images', database_path=self.path, scan_storage_dir=self.directory/"scans")

    def test_initialize_idempotently_and_configure_path(self):
        self.store.initialize()
        self.assertTrue(self.path.is_file())
        self.assertEqual(set(inspect(self.store.engine).get_table_names()), {'scans', 'scan_items', 'scan_detections', 'products', 'shops', 'shop_inventory', 'product_metadata', 'product_alternatives', 'orders', 'order_items', 'demo_customers'})
        with patch.dict('os.environ', {'STOREROOM_DB_PATH': 'data/custom.db'}):
            self.assertEqual(database_path(), ROOT/'data/custom.db')
        self.assertEqual(database_path(self.path), self.path)

    def test_relationship_counts_and_timestamp_survive_reopening(self):
        result = self.store.confirm(self.review)
        with Session(self.store.engine) as session:
            scan = session.get(Scan, str(result.scan_id))
            self.assertEqual(len(scan.items), 5)
            self.assertEqual(sum(i.reviewed for i in scan.items), 2)
            self.assertEqual(scan.items[0].scan, scan)
            self.assertEqual(scan.items[0].predicted_count, 4)
            self.assertEqual(scan.items[0].confirmed_count, 3)
            self.assertIsNotNone(scan.created_at)
        self.store.close()
        reopened = ScanStore(self.path, self.directory/"scans")
        try:
            reopened.initialize()
            self.assertEqual(reopened.get(result.scan_id), result)
        finally:
            reopened.close()

    def test_item_failure_rolls_back_already_flushed_parent_and_items(self):
        # Parent has already been flushed; force the second item to fail a DB constraint.
        seen = []
        def fail_second(mapper, connection, target):
            seen.append(target.class_id)
            if target.class_id == 2:
                target.confirmed_count = -1
        event.listen(ScanItem, 'before_insert', fail_second)
        try:
            with self.assertRaises(IntegrityError):
                self.store.confirm(self.review)
        finally:
            event.remove(ScanItem, 'before_insert', fail_second)
        self.assertEqual(seen, [0, 1, 2, 3, 4])
        with Session(self.store.engine) as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Scan)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(ScanItem)), 0)
        self.assertEqual(len(self.store.confirm(self.review).items), 2)

    def test_database_constraints_reject_bad_counts_and_orphans(self):
        for count in [-1, 1.5]:
            with self.subTest(count=count), self.assertRaises(IntegrityError):
                with Session(self.store.engine) as session, session.begin():
                    scan = Scan(id=str(uuid4()), created_at=datetime.now())
                    scan.items.append(ScanItem(class_id=0, class_name='Red Bull', predicted_count=1, confirmed_count=count))
                    session.add(scan)
        with self.assertRaises(IntegrityError):
            with Session(self.store.engine) as session, session.begin():
                session.add(ScanItem(scan_id=str(uuid4()), class_id=0, class_name='Red Bull', predicted_count=1, confirmed_count=1))
        self.assertEqual(self.store.recent(), [])

    def test_history_order_limit_and_empty_scan(self):
        self.assertEqual(self.store.recent(), [])
        ids = [str(self.store.confirm(ReviewRequest.model_validate(staged_review(self.store, self.body['items']))).scan_id) for _ in range(3)]
        with Session(self.store.engine) as session, session.begin():
            for index, id in enumerate(ids):
                session.get(Scan, id).created_at = datetime(2026, 1, 1) + timedelta(days=index)
        self.assertEqual([str(row.scan_id) for row in self.store.recent(2)], ids[::-1][:2])
        self.assertEqual(self.store.recent(1)[0].item_count, 2)
        empty = self.store.confirm(ReviewRequest.model_validate(staged_review(self.store, [])))
        self.assertEqual(self.store.recent(1)[0].item_count, 0)
        self.assertEqual(self.store.get(empty.scan_id).items, [])

    def test_api_confirm_restart_and_retrieve(self):
        with TestClient(self.app()) as client:
            self.assertEqual(client.get('/inventory/scans').json(), {'scans': []})
            response = client.post('/inventory/confirm', json=self.body)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertTrue(result['persisted'])
            self.assertEqual(result['items'], self.body['items'])
            self.assertEqual(result['created_at'], result['confirmed_at'])
        with TestClient(self.app()) as client:
            history = client.get('/inventory/scans').json()['scans']
            self.assertEqual(history[0]['scan_id'], result['scan_id'])
            self.assertEqual(history[0]['item_count'], 2)
            self.assertEqual(client.get('/inventory/scans/'+result['scan_id']).json(), result)
            # No update endpoint exists for historical scans.
            self.assertEqual(client.patch('/inventory/scans/'+result['scan_id'], json=self.body).status_code, 405)

    def test_http_limits_ids_and_invalid_confirmation_do_not_write(self):
        with TestClient(self.app()) as client:
            for limit in ['0', '-1', '101', 'x', '1.5']:
                self.assertEqual(client.get('/inventory/scans', params={'limit': limit}).status_code, 422)
            self.assertEqual(client.get('/inventory/scans/not-a-uuid').status_code, 422)
            self.assertEqual(client.get('/inventory/scans/'+str(uuid4())).status_code, 404)
            self.assertEqual(client.post('/inventory/confirm', json={'items':[{}]}).status_code, 422)
            self.assertEqual(client.get('/inventory/scans').json()['scans'], [])
            for _ in range(3): client.post('/inventory/confirm', json=staged_review(self.store, self.body['items']))
            self.assertEqual(len(client.get('/inventory/scans?limit=2').json()['scans']), 2)

    def test_storage_errors_are_generic_and_no_partial_scan_is_exposed(self):
        with TestClient(self.app()) as client:
            with patch.object(ScanStore, 'confirm', side_effect=OperationalError('secret path/SQL', {}, Exception('disk failure'))):
                response = client.post('/inventory/confirm', json=self.body)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('secret', response.text)
            self.assertEqual(client.get('/inventory/scans').json()['scans'], [])
