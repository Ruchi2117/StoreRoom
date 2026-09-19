# V0.6 results — local backup and restore

Completed 2026-09-19. Confirmed scans can be backed up as a portable local ZIP and
restored with the same photos, predictions, detections, corrections and history.
No ML experiment, retraining or protected test-set evaluation was performed.

## What was built

- `src/backup.py`: reusable `BackupService.create_backup(destination)`,
  `validate_backup(archive)` and `RestoreService.restore_backup(archive)`.
- `src/data_cli.py`: `python -m src.data_cli backup`, `validate`, `restore`.
- `src/data_lock.py`: local OS-backed writer/runtime locks and interrupted-restore
  markers, shared by application and CLI processes.
- `src/storage.py`: confirmation and schema initialization join the writer lock.
- `src/api.py`: lifespan runtime lock, explicit busy response, application version 0.6.
- `tests/test_backup_restore.py`: 18 new integrity, round-trip, CLI and safety tests.
- `tests/test_scan_evidence.py`: restart test now shuts down the first app before
  opening another on the same data, honoring the single-process runtime contract.
- `.gitignore`, `README.md`, [backup/restore guide](../docs/V0_6_BACKUP_RESTORE.md),
  this report, test log, smoke record and preservation record.

No database model/schema changes, new migrations or dependencies. Schema version
remains 1. No browser controls or HTTP backup/restore endpoints were added: CLI-only
keeps full replacement outside the unauthenticated API. The product workflow and
historical evidence UI remain unchanged.

## Backup contents and format

```text
storeroom-backup-<UTC timestamp>-<unique suffix>.zip
  manifest.json
  database.sqlite
  scans/<scan UUID>/original.jpg (or original.png)
  scans/<scan UUID>/annotated.jpg
```

Manifest format 1 records application version, schema version, creation timestamp,
scan/image counts and byte size/SHA-256 for the DB and each image. All paths are
portable archive-relative names. The SQLite snapshot preserves all three tables,
timestamps, original predictions, detection scores/boxes and human corrections.
Migrated legacy scans without evidence remain count-only.

Only confirmed history and referenced evidence belong to this snapshot. Pending
predictions, orphan files, temporary annotations, datasets, checkpoints, environments,
caches and logs are excluded. No raw photos/databases/archives enter Git.

## Consistency and restore behavior

Confirmation holds the same cross-process writer lock as backup, covering photo
promotion, transaction commit and cleanup. Backup uses SQLite's backup API (including
committed WAL contents), validates state, copies referenced photos, writes checksums
and validates its archive before and after publication. Missing referenced evidence
fails clearly; backup never reports a partial snapshot as successful. New confirmation
attempts while locked receive a retryable busy error; existing drafts remain intact.

Restore requires the app to be stopped, enforced by its lifespan runtime lock.
It validates the complete archive in temporary staging before changing live data,
including every checksum, schema, SQLite integrity/foreign keys, reconstructable
predictions and exact correspondence between DB references and archive images.
Traversal/absolute paths, duplicate entries, symlinks and unexpected members fail.

Restore fully replaces the configured pair without merging. Old DB and scan root
are retained in sibling `.rollback-<token>` paths. Caught installation failures
attempt to roll both resources back. If recovery cannot finish, markers block
ordinary use; the guide documents restoring a validated archive into new paths.
SQLite plus filesystem replacement is not one atomic power-loss transaction.

Existing unrelated files, invalid existing state and SQLite sidecars block in-place
replacement. Restoring to a new empty location is available when the old state
cannot safely be replaced. Pending drafts are excluded from the snapshot and must
be rescanned after restore; the old draft files stay in the retained rollback root.

## Tests

**103 tests passed: 85 existing/adapted plus 18 new.**
Final full suite: 97.827 seconds. Command:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See [complete test output](v0_6_tests.log).

New coverage includes empty/one/multiple scans; exact original/annotated images;
manifest sizes/digests and exclusions; reopen validation; missing images; corrupted
SQLite even with a matching manifest digest; corrupt checksums; incomplete/wrong
version archives; path traversal/drive paths; duplicate ZIP entries/symlinks; live
backup with offline-only restore; cross-process writer exclusion; CLI success/error
exits; WAL snapshots; legacy count-only scans; unrelated-destination refusal;
replacement/rollback preservation and interrupted-restore markers.

The key synthetic round trip saves Scan A **8 predicted / 7 confirmed** and Scan B
**4 predicted / 4 confirmed**, backs up, moves the test state aside, restores into
clean paths and checks the history/single-scan APIs plus exact image bytes. Complete
scan responses, including detections and timestamps, match the originals.

Two failure checks are distinct: checksum rejection happens before replacement;
a simulated failure while installing the staged photo directory rolls back the
already replaced DB and old photo root. Both preserve the prior scan state.

## Real two-scan smoke

Ran actual frozen-model inference through the real browser upload/review workflow
using two ordinary **validation** images, exclusively for product/persistence checks:

- `IMG_20181218_170247.jpg`: six detections; Red Bull corrected **4 → 3**.
- `IMG_20181218_165646.jpg`: fourteen detections; counts confirmed unchanged.

Both live under `data/yolo_v01/images/val/`. No ground-truth scoring or tuning was
performed. The successful run used an isolated ignored app-data directory, leaving
default user history untouched. See [smoke evidence](v0_6_smoke.json).

| Check | Result |
| --- | --- |
| Two browser scans confirmed | Passed; original predictions stayed separate from corrections |
| Backup via separate CLI while app running | Passed; 2 scans, 4 photos, schema 1 |
| Archive reopened/validated by CLI | Passed |
| Stop app, move isolated old state aside, restore clean paths | Passed |
| Corrupt-image archive restore | Rejected on checksum before replacement |
| Valid DB/photo hashes after rejected restore | Unchanged |
| Restart backend and reopen both scans in browser | Passed |
| History and complete per-scan JSON | Exactly identical before/after |
| Original/annotated photo bytes | Exactly identical before/after |
| Browser photo decoding and correction label | Passed |
| Browser page errors | None |

The restored scan screenshot was visually inspected. Screenshots, archives and
smoke databases stay in ignored local directories. This was a data-integrity
smoke, not evidence of improved detection quality.

## Protected artifacts and hygiene

See [preservation record](v0_6_integrity.json) for the protected-file count, frozen
dataset verification, unchanged tracked inference/configuration/prior-report files
against v0.5 commit `d98d0cc`, and unchanged schema modules.
The frozen checkpoint remains:
`099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4`.

No inference settings, model weights, datasets/splits, evaluation/counting logic or
historical reports were modified. No retraining or test-set evaluation occurred.
Git ignores local DBs, photos, backups, lock/staging/rollback/recovery files. No
secrets, uploaded images, raw datasets or machine-specific absolute paths are added.

## Limitations and next milestone

Local backup only; no cloud backup, scheduled backups or multi-device sync. No
authentication/multi-shop system or marketplace features. Archive checksums detect
corruption but do not authenticate the author; archives are unencrypted. Locks
coordinate this app/CLI, not external editors. Local filesystems and a single app
process are supported. Disk usage can grow through backups and retained rollback
pairs; no automatic retention policy. Abrupt power loss is documented, not fully
simulated. The format limits expanded payload to 10 GiB and 100,000 entries.

Five product classes, visible-package counting only, hidden inventory unknown.
Independent-scene generalization remains unverified; the model remains provisional.
Restoring a backup does not include the application runtime or model checkpoint.

Exactly one next major milestone: **independent-scene field validation using newly
collected, consented shelf photos**. The product now retains evidence and can recover
it; generalization to genuinely new scenes is still the central unverified ML claim.
This milestone was recommended only, not implemented.

## Git delivery

One meaningful `feat: add local scan data backup and restore` commit. No GitHub
remote is configured, so no push is possible. The final task response records the
commit hash and verified working-tree status.
