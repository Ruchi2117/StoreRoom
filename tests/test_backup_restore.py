"""Portable data integrity and failure recovery. Synthetic predictions, no model."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient
from src.api import create_app
from src.backup import BackupService, RestoreService, BackupError, validate_backup, checksum
from src.data_lock import data_lock, DataBusyError, marker_paths
from src.review import ReviewRequest
from src.storage import ScanStore
from ui_support import staged_review, FixtureDetector


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.db = self.root/'history.db'
        self.scans = self.root/'scans'
        self.archive = self.root/'backup.zip'
        self.store = ScanStore(self.db, self.scans)
        self.store.initialize()
        self.addCleanup(self.store.close)
        self.service = BackupService(self.db, self.scans)

    def scan(self, predicted=8, confirmed=7):
        return self.store.confirm(ReviewRequest.model_validate(staged_review(self.store, [
            {'class_id': 0, 'class_name': 'Red Bull', 'predicted_count': predicted, 'confirmed_count': confirmed}])))

    def rewrite(self, change):
        with zipfile.ZipFile(self.archive) as archive:
            payload = {n: archive.read(n) for n in archive.namelist()}
        change(payload)
        damaged = self.root/'damaged.zip'
        with zipfile.ZipFile(damaged, 'w') as archive:
            for name, body in payload.items():
                archive.writestr(name, body)
        return damaged

    def app(self):
        return create_app(database_path=self.db, scan_storage_dir=self.scans,
            detector_factory=FixtureDetector, output_dir=self.root/'annotations')

    def test_empty_backup_validates_and_restores(self):
        self.service.create_backup(self.archive)
        self.assertEqual(validate_backup(self.archive)['scan_count'], 0)
        target = self.root/'clean'
        RestoreService(target/'history.db', target/'scans').restore_backup(self.archive)
        restored = ScanStore(target/'history.db', target/'scans')
        try:
            restored.initialize()
            self.assertEqual(restored.recent(), [])
        finally:
            restored.close()

    def test_manifest_and_one_scan_exact_files_exclude_drafts(self):
        result = self.scan()
        staged_review(self.store, [])  # Unfinished work is excluded by contract.
        (self.scans/'unreferenced.tmp').write_text('not confirmed evidence')
        manifest = self.service.create_backup(self.archive)
        self.assertEqual((manifest['scan_count'], manifest['image_count']), (1, 2))
        self.assertNotIn(str(self.root), json.dumps(manifest))
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(set(archive.namelist()), {'manifest.json', 'database.sqlite',
                f'scans/{result.scan_id}/original.png', f'scans/{result.scan_id}/annotated.jpg'})
            for name, entry in manifest['files'].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), entry['sha256'])
        self.assertEqual(validate_backup(self.archive), manifest)

    def test_full_roundtrip_reset_and_history_apis(self):
        expected = [self.scan(8,7), self.scan(4,4)]
        original_files = {p.relative_to(self.scans): p.read_bytes() for p in self.scans.rglob('*') if p.is_file()}
        self.service.create_backup(self.archive)
        self.store.close()
        # Move only these explicitly owned temporary test resources, preserving the old copy.
        self.db.rename(self.root/'reset.db')
        self.scans.rename(self.root/'reset-scans')
        RestoreService(self.db, self.scans).restore_backup(self.archive)
        with TestClient(self.app()) as client:
            self.assertEqual(len(client.get('/inventory/scans').json()['scans']), 2)
            for item in expected:
                self.assertEqual(client.get('/inventory/scans/'+str(item.scan_id)).json(), item.model_dump(mode='json'))
                for route, name in [(item.original_image_url, 'original.png'), (item.annotated_image_url, 'annotated.jpg')]:
                    response = client.get(route)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.content, original_files[Path(str(item.scan_id))/name])

    def test_full_replace_keeps_rollback_and_does_not_merge(self):
        first = self.scan()
        self.service.create_backup(self.archive)
        second = self.scan(4,4)
        self.store.close()
        result = RestoreService(self.db, self.scans).restore_backup(self.archive)
        self.assertIsNotNone(result['rollback_token'])
        reopened = ScanStore(self.db, self.scans)
        try:
            reopened.initialize()
            self.assertIsNotNone(reopened.get(first.scan_id))
            self.assertIsNone(reopened.get(second.scan_id))
        finally:
            reopened.close()
        self.assertTrue(Path(str(self.db)+'.rollback-'+result['rollback_token']).is_file())
        self.assertTrue(Path(str(self.scans)+'.rollback-'+result['rollback_token']).is_dir())

    def test_missing_image_fails_without_output(self):
        result = self.scan()
        (self.scans/str(result.scan_id)/'original.png').unlink()
        with self.assertRaisesRegex(BackupError, 'Missing.*original'):
            self.service.create_backup(self.archive)
        self.assertFalse(self.archive.exists())

    def test_corrupt_sqlite_fails_even_with_matching_checksum(self):
        self.service.create_backup(self.archive)
        def corrupt(payload):
            payload['database.sqlite'] = b'not a database'
            manifest = json.loads(payload['manifest.json'])
            manifest['files']['database.sqlite'] = {'size': len(payload['database.sqlite']),
                'sha256': hashlib.sha256(payload['database.sqlite']).hexdigest()}
            payload['manifest.json'] = json.dumps(manifest)
        with self.assertRaises(BackupError):
            validate_backup(self.rewrite(corrupt))

    def test_checksum_failure_preserves_live_state(self):
        saved = self.scan()
        self.service.create_backup(self.archive)
        name = f'scans/{saved.scan_id}/original.png'
        bad = self.rewrite(lambda p: p.__setitem__(name, b'x'*len(p[name])))
        before = checksum(self.db)
        with self.assertRaisesRegex(BackupError, 'Checksum mismatch'):
            RestoreService(self.db, self.scans).restore_backup(bad)
        self.assertEqual(checksum(self.db), before)
        self.assertEqual(self.store.get(saved.scan_id), saved)
        self.assertFalse(any(p.exists() for p in marker_paths(self.db, self.scans)))

    def test_incomplete_and_wrong_version_rejected(self):
        saved = self.scan()
        self.service.create_backup(self.archive)
        with self.assertRaises(BackupError):
            validate_backup(self.rewrite(lambda p: p.pop(f'scans/{saved.scan_id}/annotated.jpg')))
        def wrong(payload):
            manifest = json.loads(payload['manifest.json'])
            manifest['format_version'] = 99
            payload['manifest.json'] = json.dumps(manifest)
        with self.assertRaisesRegex(BackupError, 'Unsupported'):
            validate_backup(self.rewrite(wrong))

    def test_unsafe_archive_paths_are_rejected_before_extraction(self):
        self.service.create_backup(self.archive)
        for name in ['../../evil.txt', '/absolute.txt', 'C:/evil.txt', 'scans\\evil.txt', 'scans/../evil.txt']:
            with self.subTest(name=name), self.assertRaises(BackupError):
                validate_backup(self.rewrite(lambda p: p.__setitem__(name, b'bad')))
        self.assertFalse((self.root.parent/'evil.txt').exists())

    def test_duplicate_members_and_symlinks_rejected(self):
        self.service.create_backup(self.archive)
        bad = self.rewrite(lambda p: None)
        with zipfile.ZipFile(bad, 'a') as archive:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                archive.writestr('database.sqlite', b'duplicate')
        with self.assertRaises(BackupError):
            validate_backup(bad)
        bad = self.rewrite(lambda p: None)
        with zipfile.ZipFile(bad, 'a') as archive:
            entry = zipfile.ZipInfo('scans/'+'a'*36+'/original.jpg')
            entry.create_system = 3
            entry.external_attr = 0o120777 << 16
            archive.writestr(entry, '../../evil')
        with self.assertRaises(BackupError):
            validate_backup(bad)

    def test_backup_lock_blocks_confirmation_across_processes(self):
        body = staged_review(self.store, [])
        command = [sys.executable, '-c',
            'import sys\nfrom src.data_lock import data_lock\nwith data_lock(sys.argv[1],sys.argv[2]):\n print("locked",flush=True)\n sys.stdin.readline()',
            str(self.db), str(self.scans)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'locked')
            with self.assertRaises(DataBusyError):
                self.store.confirm(ReviewRequest.model_validate(body))
            with self.assertRaises(DataBusyError):
                self.service.create_backup(self.archive)
        finally:
            process.communicate('\n', timeout=10)
        self.store.confirm(ReviewRequest.model_validate(body))

    def test_live_backup_allowed_but_restore_requires_stopped_app(self):
        self.scan()
        with TestClient(self.app()) as client:
            self.service.create_backup(self.archive)
            with self.assertRaises(DataBusyError):
                RestoreService(self.db, self.scans).restore_backup(self.archive)
            self.assertEqual(len(client.get('/inventory/scans').json()['scans']), 1)

    def test_failed_install_rolls_back_both_resources(self):
        self.scan()
        self.service.create_backup(self.archive)
        latest = self.scan(4,4)
        self.store.close()
        before = checksum(self.db)
        rename = Path.rename
        def fail_once(path, target):
            if '.staged-' in path.name and Path(target) == self.scans:
                raise OSError('simulated install failure')
            return rename(path, target)
        with patch.object(Path, 'rename', fail_once), self.assertRaisesRegex(OSError, 'simulated'):
            RestoreService(self.db, self.scans).restore_backup(self.archive)
        self.assertEqual(checksum(self.db), before)
        self.assertEqual(self.store.get(latest.scan_id), latest)
        self.assertFalse(any(p.exists() for p in marker_paths(self.db, self.scans)))

    def test_unrelated_destination_is_not_replaced(self):
        self.service.create_backup(self.archive)
        self.scans.mkdir(exist_ok=True)
        protected = self.scans/'important.txt'
        protected.write_text('keep')
        with self.assertRaises(BackupError):
            RestoreService(self.db, self.scans).restore_backup(self.archive)
        self.assertEqual(protected.read_text(), 'keep')

    def test_legacy_count_only_scan_survives(self):
        from datetime import datetime
        from sqlalchemy.orm import Session
        from src.storage import Scan, ScanItem
        from uuid import uuid4
        id = str(uuid4())
        with Session(self.store.engine) as session, session.begin():
            row = Scan(id=id, created_at=datetime(2026,1,1))
            row.items.append(ScanItem(class_id=0,class_name='Red Bull',predicted_count=8,confirmed_count=7))
            session.add(row)
        self.assertEqual(self.service.create_backup(self.archive)['image_count'], 0)
        self.assertEqual(validate_backup(self.archive)['scan_count'], 1)

    def test_wal_snapshot_contains_committed_records(self):
        self.store.close()
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute('PRAGMA journal_mode=WAL')
            self.scan()
            self.assertEqual(self.service.create_backup(self.archive)['scan_count'], 1)
            self.assertEqual(validate_backup(self.archive)['scan_count'], 1)

    def test_cli_backup_validate_restore_and_failure_exit(self):
        self.scan()
        base = [sys.executable, '-m', 'src.data_cli']
        backup = subprocess.run(base+['backup','--database',str(self.db),'--scans',str(self.scans),
            '--output',str(self.root/'backups')], capture_output=True, text=True)
        self.assertEqual(backup.returncode, 0, backup.stderr+backup.stdout)
        archive = next((self.root/'backups').glob('*.zip'))
        valid = subprocess.run(base+['validate',str(archive)], capture_output=True, text=True)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        restored = subprocess.run(base+['restore',str(archive),'--database',str(self.root/'new.db'),
            '--scans',str(self.root/'new-scans')], capture_output=True, text=True)
        self.assertEqual(restored.returncode, 0, restored.stderr+restored.stdout)
        missing = subprocess.run(base+['validate',str(self.root/'absent.zip')], capture_output=True, text=True)
        self.assertEqual(missing.returncode, 1)

    def test_interrupted_restore_marker_blocks_app_writes(self):
        marker_paths(self.db, self.scans)[0].write_text('{}')
        with self.assertRaises(DataBusyError):
            self.store.initialize()
        with self.assertRaises(DataBusyError):
            self.service.create_backup(self.archive)
