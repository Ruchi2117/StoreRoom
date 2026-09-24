"""Versioned local snapshots of confirmed scans. No inference or checkpoint loading."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import tempfile
from uuid import UUID, uuid4
import zipfile
from sqlalchemy.exc import SQLAlchemyError

from src.data_lock import data_lock, marker_paths
from src.evidence import EvidenceFiles
from src.storage import Base, ScanStore, database_path


class BackupError(ValueError):
    pass


def checksum(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def connect_readonly(path):
    if not path.is_file():
        raise BackupError('Application database is missing; start StoreRoom first')
    return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)


def inventory(database, scans):
    """Validate current schema, relational data and exact managed image references."""
    from src import catalog  # Register v0.8 tables even in the standalone backup CLI.
    try:
        with closing(connect_readonly(database)) as connection:
            schema = connection.execute('PRAGMA user_version').fetchone()[0]
            if schema not in (1,2,3):
                raise BackupError('Only migrated schema versions 1, 2 and 3 are supported')
            if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise BackupError('Database integrity check failed')
            if connection.execute('PRAGMA foreign_key_check').fetchall():
                raise BackupError('Database has orphaned records')
            objects = connection.execute("SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
            tables = {'scans','scan_items','scan_detections'} if schema==1 else set(Base.metadata.tables)
            if schema==2:
                tables -= {'product_metadata','product_alternatives'}
            if {n for n, t in objects if t == 'table'} != tables or any(t in {'view', 'trigger'} for _, t in objects):
                raise BackupError('Unexpected database schema')
            for name, table in Base.metadata.tables.items():
                if name not in tables:
                    continue
                columns = {r[1] for r in connection.execute(f'PRAGMA table_info({name})')}
                if columns != {c.name for c in table.columns}:
                    raise BackupError('Incompatible database columns: ' + name)
            rows = connection.execute('SELECT id,prediction_id,source_image_path,annotated_image_path FROM scans ORDER BY id').fetchall()
            if schema>=2:
                invalid = connection.execute('''SELECT i.product_id FROM shop_inventory i
                    LEFT JOIN scan_items s ON s.scan_id=i.source_scan_id AND s.product_id=i.product_id
                    WHERE i.is_demo=0 AND (s.id IS NULL OR s.reviewed<>1 OR s.confirmed_count<>i.quantity)''').fetchall()
                if invalid:
                    raise BackupError('Inventory does not match its source confirmed scan')
        files = {}
        evidence = EvidenceFiles(scans)
        for id, prediction_id, original, annotated in rows:
            if str(UUID(id)) != id:
                raise BackupError('Invalid scan ID')
            if prediction_id is None:
                if original is not None or annotated is not None:
                    raise BackupError('Incomplete legacy scan evidence: ' + id)
                continue
            for kind, reference in [('original', original), ('annotated', annotated)]:
                path = evidence.image(id, reference, kind)
                if path is None or path.is_symlink() or path.parent.is_symlink():
                    raise BackupError(f'Missing or unsafe {kind} evidence for scan {id}')
                files['scans/' + reference] = path
        store = ScanStore(database, scans)
        try:
            for id, *_ in rows:
                result = store.get(id)  # Existing typed prediction/count validation.
                if result.original_prediction is not None:
                    products = result.original_prediction.products
                    if {p.class_id for p in products} != set(range(5)) or sum(p.count for p in products) != len(result.detections):
                        raise BackupError('Incomplete original prediction: ' + id)
                elif result.detections:
                    raise BackupError('Legacy scan has unlinked detections: ' + id)
        finally:
            store.close()
        return len(rows), files
    except (sqlite3.Error, SQLAlchemyError, ValueError, TypeError, OSError) as error:
        if isinstance(error, BackupError):
            raise
        raise BackupError('Invalid application state: ' + str(error)) from error


def safe_member(info):
    name = info.filename
    path = PurePosixPath(name)
    mode = info.external_attr >> 16
    if (info.is_dir() or '\\' in name or ':' in name or path.is_absolute()
            or any(p in {'..', '.'} for p in path.parts) or path.as_posix() != name
            or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG})):
        raise BackupError('Unsafe archive entry: ' + name)
    if name not in {'manifest.json', 'database.sqlite'} and not re.fullmatch(
            r'scans/[0-9a-f-]{36}/(original\.(jpg|png)|annotated\.jpg)', name):
        raise BackupError('Unexpected archive entry: ' + name)


def unpack_validated(archive, target):
    """Explicit allowlist extraction; never use extractall or trust manifest paths."""
    try:
        with zipfile.ZipFile(archive) as zipped:
            infos = zipped.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or not {'manifest.json', 'database.sqlite'} <= set(names):
                raise BackupError('Duplicate entries or incomplete archive')
            # Local format limit: 10 GiB expanded, at most 100,000 files, 32 MiB manifest.
            if len(infos) > 100000 or sum(i.file_size for i in infos) > 10 * 1024**3:
                raise BackupError('Backup exceeds local format limits')
            for info in infos:
                safe_member(info)
            if zipped.getinfo('manifest.json').file_size > 32 * 1024**2:
                raise BackupError('Manifest is too large')
            manifest = json.loads(zipped.read('manifest.json'))
            if manifest['format_version'] != 1 or manifest['schema_version'] not in (1,2,3):
                raise BackupError('Unsupported backup or database version')
            datetime.fromisoformat(manifest['created_at'])
            files = manifest['files']
            if set(files) != set(names) - {'manifest.json'}:
                raise BackupError('Manifest file list does not match archive')
            for name, entry in files.items():
                if not re.fullmatch('[0-9a-f]{64}', entry['sha256']) or entry['size'] != zipped.getinfo(name).file_size:
                    raise BackupError('Invalid file metadata: ' + name)
                destination = target / name
                if not destination.resolve().is_relative_to(target.resolve()):
                    raise BackupError('Unsafe extraction path')
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(name) as source, destination.open('xb') as output:
                    shutil.copyfileobj(source, output)
                if checksum(destination) != entry['sha256']:
                    raise BackupError('Checksum mismatch: ' + name)
        count, images = inventory(target / 'database.sqlite', target / 'scans')
        with closing(connect_readonly(target/'database.sqlite')) as connection:
            if connection.execute('PRAGMA user_version').fetchone()[0] != manifest['schema_version']:
                raise BackupError('Manifest schema version differs from database')
        if set(images) != set(files) - {'database.sqlite'}:
            raise BackupError('Archive evidence does not match database references')
        if count != manifest['scan_count'] or len(images) != manifest['image_count']:
            raise BackupError('Manifest counts do not match database')
        (target / 'scans').mkdir(exist_ok=True)
        return manifest
    except (zipfile.BadZipFile, KeyError, TypeError, ValueError, OSError, RuntimeError) as error:
        if isinstance(error, BackupError):
            raise
        raise BackupError('Invalid backup: ' + str(error)) from error


def validate_backup(archive):
    with tempfile.TemporaryDirectory(prefix='storeroom-validate-') as directory:
        return unpack_validated(Path(archive), Path(directory))


def locations(database=None, scans=None):
    database = database_path(database)
    scans = EvidenceFiles(scans).root
    if database.suffix not in {'.db', '.sqlite', '.sqlite3'} or database == scans or database.is_relative_to(scans) or scans.is_relative_to(database):
        raise BackupError('Use a SQLite filename and a separate dedicated scan directory')
    return database, scans


class BackupService:
    def __init__(self, database=None, scans=None):
        self.database, self.scans = locations(database, scans)

    def create_backup(self, destination):
        destination = Path(destination).resolve()
        if destination.is_relative_to(self.scans) or destination == self.database:
            raise BackupError('Backups must be stored outside the scan directory/database')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise BackupError('Backup destination already exists; choose a new filename')
        with data_lock(self.database, self.scans), tempfile.TemporaryDirectory(
                prefix='.storeroom-backup-', dir=destination.parent) as directory:
            stage = Path(directory)
            # SQLite backup API captures committed WAL content; never copy a live DB file.
            with closing(connect_readonly(self.database)) as source, closing(sqlite3.connect(stage/'database.sqlite')) as target:
                source.backup(target)
                target.execute('PRAGMA journal_mode=DELETE')
            count, images = inventory(stage/'database.sqlite', self.scans)
            for name, source in images.items():
                target = stage/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            payload = {'database.sqlite': stage/'database.sqlite', **{name: stage/name for name in images}}
            with closing(connect_readonly(stage/'database.sqlite')) as connection:
                schema = connection.execute('PRAGMA user_version').fetchone()[0]
            manifest = {'format_version': 1, 'application_version': '0.9', 'schema_version': schema,
                'created_at': datetime.now(timezone.utc).isoformat(), 'scan_count': count,
                'image_count': len(images), 'files': {name: {'sha256': checksum(path), 'size': path.stat().st_size}
                for name, path in payload.items()}}
            archive = stage/'snapshot.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
                zipped.writestr('manifest.json', json.dumps(manifest, indent=2))
                for name, path in payload.items():
                    zipped.write(path, name)
            validate_backup(archive)
            # Exclusive creation avoids overwriting a concurrently created backup.
            created = False
            try:
                with destination.open('xb') as output, archive.open('rb') as source:
                    created = True
                    shutil.copyfileobj(source, output)
                validate_backup(destination)
            except Exception:
                if created:
                    destination.unlink(missing_ok=True)
                raise
            return manifest


def verify_replaceable(database, scans):
    """Refuse unrelated data and links before any move of existing user state."""
    if database.exists():
        inventory(database, scans)
    for suffix in ('-wal', '-shm', '-journal'):
        if Path(str(database)+suffix).exists():
            raise BackupError('SQLite sidecars remain; stop all database users and checkpoint/close SQLite first')
    if scans.exists():
        if not scans.is_dir():
            raise BackupError('Scan destination is not a directory')
        for path in scans.rglob('*'):
            if path.is_symlink() or not path.resolve().is_relative_to(scans):
                raise BackupError('Linked scan paths cannot be replaced')
            parts = path.relative_to(scans).parts
            offset = 1 if parts[0] == '.pending' else 0
            if len(parts) == offset:
                continue
            try:
                if str(UUID(parts[offset])) != parts[offset]:
                    raise ValueError()
            except ValueError as error:
                raise BackupError('Destination contains unrelated data; use a dedicated scan directory') from error
            if len(parts) > offset + 2 or (len(parts) == offset+2 and parts[-1] not in {'original.jpg','original.png','annotated.jpg','prediction.json'}):
                raise BackupError('Unexpected scan storage contents')


class RestoreService:
    def __init__(self, database=None, scans=None):
        self.database, self.scans = locations(database, scans)

    def restore_backup(self, archive):
        # Runtime lock makes restore offline-only and also prevents app startup mid-restore.
        with data_lock(self.database, self.scans, 'runtime'), data_lock(self.database, self.scans):
            self.database.parent.mkdir(parents=True, exist_ok=True)
            self.scans.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.storeroom-restore-', dir=self.database.parent) as directory:
                stage = Path(directory)
                manifest = unpack_validated(Path(archive), stage)
                verify_replaceable(self.database, self.scans)
                token = uuid4().hex
                staged_scans = self.scans.with_name(self.scans.name+'.staged-'+token)
                old_db = self.database.with_name(self.database.name+'.rollback-'+token)
                old_scans = self.scans.with_name(self.scans.name+'.rollback-'+token)
                markers = marker_paths(self.database, self.scans)
                # Place photos beside destination for same-volume rename even with separate roots.
                moved_db = moved_scans = installed_db = installed_scans = False
                try:
                    shutil.copytree(stage/'scans', staged_scans)
                    for name, entry in manifest['files'].items():
                        if name.startswith('scans/') and checksum(staged_scans/name.removeprefix('scans/')) != entry['sha256']:
                            raise BackupError('Restored image copy failed verification: ' + name)
                    for marker in markers:
                        marker.write_text(json.dumps({'rollback_token': token}), encoding='utf-8')
                    if self.database.exists():
                        self.database.rename(old_db)
                        moved_db = True
                    if self.scans.exists():
                        self.scans.rename(old_scans)
                        moved_scans = True
                    (stage/'database.sqlite').rename(self.database)
                    installed_db = True
                    staged_scans.rename(self.scans)
                    installed_scans = True
                except Exception:
                    # Keep a recovery marker if rollback itself fails. Never delete old state.
                    if installed_db:
                        self.database.rename(stage/'failed-database.sqlite')
                    if installed_scans:
                        self.scans.rename(staged_scans)
                    if moved_db:
                        old_db.rename(self.database)
                    if moved_scans:
                        old_scans.rename(self.scans)
                    for marker in markers:
                        marker.unlink(missing_ok=True)
                    raise
                else:
                    for marker in markers:
                        marker.unlink(missing_ok=True)
                finally:
                    if staged_scans.exists():
                        # Generated sibling path checked before recursive deletion.
                        if staged_scans.resolve().parent != self.scans.parent:
                            raise BackupError('Unsafe staging cleanup location')
                        shutil.rmtree(staged_scans)
                return {**manifest, 'rollback_token': token if moved_db or moved_scans else None}
