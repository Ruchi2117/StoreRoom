"""Local data operations: python -m src.data_cli --help."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4
from src.backup import BackupService, RestoreService, validate_backup, BackupError


def main(argv=None):
    parser = argparse.ArgumentParser(description='StoreRoom local confirmed-history backup/restore')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('backup', 'restore', 'validate'):
        child = sub.add_parser(command)
        if command == 'backup':
            child.add_argument('--output', type=Path, default=Path('backups'), help='Archive output directory')
        else:
            child.add_argument('archive', type=Path)
        if command != 'validate':
            child.add_argument('--database', type=Path, help='Overrides STOREROOM_DB_PATH')
            child.add_argument('--scans', type=Path, help='Overrides SCAN_STORAGE_DIR')
    args = parser.parse_args(argv)
    try:
        if args.command == 'backup':
            name = 'storeroom-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8] + '.zip'
            archive = args.output/name
            print('Creating and validating consistent backup...')
            result = BackupService(args.database, args.scans).create_backup(archive)
            print('Backup created successfully: ' + str(archive))
        elif args.command == 'restore':
            print('Validating and restoring full application data (app must be stopped)...')
            result = RestoreService(args.database, args.scans).restore_backup(args.archive)
            print('Restore completed successfully.')
            if result['rollback_token']:
                print('Previous data retained in sibling .rollback-' + result['rollback_token'] + ' paths.')
        else:
            print('Validating archive, checksums, database and referenced images...')
            result = validate_backup(args.archive)
            print('Backup validated successfully.')
        print(f"Scans: {result['scan_count']}\nImages: {result['image_count']}\nSchema: {result['schema_version']}")
        return 0
    except (BackupError, OSError, sqlite3.Error) as error:
        print('Data operation failed: ' + str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
