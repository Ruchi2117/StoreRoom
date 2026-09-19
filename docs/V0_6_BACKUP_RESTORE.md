# V0.6 — local backup and restore

StoreRoom's confirmed history depends on **SQLite plus its referenced photos**.
Backing up one without the other can lose the evidence behind corrected counts.
V0.6 packages them together in a validated portable ZIP. This is local backup,
not cloud backup, synchronization or model training.

## Commands

Use the existing virtual environment, from the project root. No new dependencies.
Start the application once to initialize/migrate its database before the first backup.

```powershell
.\.venv\Scripts\python.exe -m src.data_cli backup --output ./backups
.\.venv\Scripts\python.exe -m src.data_cli validate ./backups/<backup-filename>.zip
```

Expected: successful creation/validation, archive path, scan count, image count
and schema version. A fresh timestamp/UUID filename avoids overwriting an earlier
snapshot. On failure the CLI prints the reason and exits with status 1.

**Restore replaces the whole configured database and scan directory; it does not
merge histories. Stop the backend first with Ctrl+C.** Then run:

```powershell
.\.venv\Scripts\python.exe -m src.data_cli restore ./backups/<backup-filename>.zip
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Open Scan History. Photos, detections, timestamps, original predicted counts and
confirmed counts should match the snapshot. **AI prediction ≠ confirmed inventory**
remains true after restore. Refresh any browser that held an unfinished review;
that draft is not in the backup, so upload it again.

`<backup-filename>` is a placeholder: use the filename printed by backup.
To restore into a clean, separate location instead of replacing default history:

```powershell
.\.venv\Scripts\python.exe -m src.data_cli restore ./backups/<backup-filename>.zip --database ./data/restored/storeroom.db --scans ./data/restored/scans
$env:STOREROOM_DB_PATH = 'data/restored/storeroom.db'
$env:SCAN_STORAGE_DIR = 'data/restored/scans'
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Both backup/restore accept `--database` and `--scans`; otherwise they reuse
`STOREROOM_DB_PATH` (default `data/storeroom.db`) and `SCAN_STORAGE_DIR` (default
`data/scans`). Database/scan relative paths resolve from the repository root,
as before. CLI archive/output paths resolve from the current working directory.
Use a dedicated scan directory and a separate `.db`, `.sqlite` or `.sqlite3` file.
The archive never chooses destination paths; only the local operator does.

## Included and excluded state

Included: all confirmed `Scan`, `ScanItem` and `ScanDetection` database rows, their
timestamps/model identity, all five original counts, reviewed flags, corrections,
scores/boxes, exact original JPEG/PNG bytes and exact annotation bytes. Older
migrated count-only scans are also retained, without inventing missing evidence.

Excluded: `scans/.pending/` (unfinished predictions), unreferenced/orphan photos,
temporary `outputs/annotations`, datasets, model weights, caches, logs, secrets,
environments and development/test artifacts. Inspection of v0.5 confirmed these
are not needed to reopen **confirmed** history. Pending drafts survive normal
restart in v0.5, but they are explicitly outside this confirmed-history snapshot.
On replacement, the entire old scan root, including pending files, is preserved
in the rollback directory. A backup is not a copy of the development workspace.

To run inference on a different machine, install the same application/dependencies
and supply the separately managed frozen checkpoint. They are not in this archive.

## Archive contract

```text
storeroom-backup-<UTC timestamp>-<unique suffix>.zip
  manifest.json
  database.sqlite
  scans/<scan UUID>/original.jpg (or original.png)
  scans/<scan UUID>/annotated.jpg
```

The root-level JSON manifest contains `format_version: 1`, `application_version:
"0.6"`, `schema_version: 1`, UTC `created_at`, `scan_count`, `image_count` and
`files`. Each file entry (database and every photo) records its relative archive
name, byte size and SHA-256. It has no absolute machine paths. The manifest itself
is not self-hashed; SHA-256 detects corruption, **not authenticity** against someone
who can replace both payload and manifest. Archives are not encrypted; keep them
private and copy a validated backup to another local device if disk loss matters.

## Consistency and coordination

`src/data_lock.py` uses OS-backed advisory locks (`msvcrt` on Windows, `flock` on
POSIX). Both canonical database and scan-root paths have sibling lock files.
These files stay in place; **never delete a lock file to bypass a busy operation**.
The OS releases locks when their owning handles/process close.

Confirmation holds a writer lock from before photo promotion through SQLite commit
and pending cleanup. Initialization/migration also holds that lock. Backup holds
the same lock for its whole operation, including archive validation/publication.
Thus existing confirmation must finish before backup starts; attempts during backup
fail cleanly (HTTP 503), without losing their pending review. Retry once backup
finishes. Locks fail immediately when busy rather than creating a long HTTP wait.

Backup uses `sqlite3.Connection.backup()` to create a consistent SQLite snapshot,
including committed WAL data. It switches the snapshot to DELETE journal mode so
no WAL sidecar is needed. It validates the snapshot and its referenced original
files, copies only those files, calculates checksums, builds the ZIP and validates
the archive before and after publishing it. Any missing referenced image fails
the operation and identifies the scan/kind. Caught output failures remove partial
new output. Existing archives are never overwritten.

Prediction may continue during live backup: it only creates unfinished drafts.
Confirmed photo files are immutable in the app. There is no deletion endpoint.
External SQL editors/manual file edits do not honor these locks and must not run
during data operations. Use local disks, a single backend process, and the same
configured paths. Network filesystem lock semantics are not supported/verified.

The running FastAPI app additionally owns a runtime lock for its full lifespan.
Restore requires that lock and the writer lock. This prevents restore while the
app is running, and app startup during replacement. Library callers must also
close any standalone ScanStore/SQLite readers before restore. This is cooperative
single-machine coordination, not a multi-server transaction protocol.

## Validation and replacement

1. Acquire runtime/writer locks; never load the model.
2. Reject unsafe ZIP names, duplicates, symlinks, unexpected files and unsupported
   versions. Extract only explicitly allowed names into a generated staging directory.
3. Validate every byte size/checksum, SQLite integrity/foreign keys, schema version,
   known tables/columns, reconstructed predictions/counts, scan count and exact
   agreement between DB image references and archive entries.
4. Reject unrelated files or links in an existing scan destination. Reject unknown
   DB schemas or remaining SQLite journal/WAL/SHM sidecars. Fully validate existing
   state before replacement; if it cannot be verified, restore to a **new location**.
5. Stage photos beside their target (allowing separate local disks), verify copied
   photo hashes, and record `.restore-in-progress` markers beside both resources.
6. Rename old DB/root to sibling `<name>.rollback-<token>` paths. Install the staged
   database/photos, then remove the markers. The CLI prints the rollback token.
7. Retain the old pair indefinitely. No automatic deletion/retention cleanup exists.

An error during installation attempts to restore both old resources. If rollback
itself fails, the markers remain and prevent app startup, confirmations, backup
and another restore. Old state is not automatically discarded.

If sidecars remain after shutdown, do not delete them. Ensure all SQLite users
are closed and use SQLite's checkpoint/clean-close procedure, or restore into a
fresh location. Backup itself supports a live WAL database; the stricter sidecar
rule applies only to replacing old data.

## Interrupted restore recovery

SQLite and filesystem renames across two locations cannot provide one atomic
power-loss transaction. Abrupt termination can leave a partially installed pair.
Markers deliberately block ordinary use instead of silently serving mixed state.
They contain the rollback token. The old pair, if present before replacement, is
retained beside the configured paths. Generated staging/output files can also
remain after a hard crash; no automatic orphan cleanup runs.

Keep the app stopped. Preserve the current paths, rollback paths, markers and
archive. Validate the archive, restore it into **new empty configured locations**
using the CLI, and start the app pointed at that verified pair. This gives a safe
recovery path without deleting markers or guessing which half was installed.
Inspect/recover the old pair separately if newer records were outside the backup.
Do not remove recovery markers merely to force the original paths to open.

The normal replacement rollback test covers a caught file-install failure; sudden
power loss is documented, not claimed to be exhaustively simulated.

## Security, scale and compatibility

Only format 1 with already-migrated schema 1 is accepted. No schema changes or new
migration were needed in v0.6. Restore validates without migrating; ordinary app
startup still performs the existing idempotent migration. First start an old v0.4
database with the current app to migrate before backing it up.

The reader refuses `../`, absolute/drive paths, backslashes, special filesystem
entries, duplicate names and unexpected members. It does not use `extractall`.
Database checks reject unknown tables, triggers and views. Destinations never come
from the archive. Current limits are 10 GiB expanded, 100,000 members and a 32 MiB
manifest; validation/extraction can fail safely on insufficient disk/permissions.
Allow space for the archive, staged/validation copies, and retained previous data.

There are no backup/restore HTTP routes or frontend changes. A local CLI keeps full
data replacement out of the unauthenticated browser API. The product scan/review
workflow is unchanged. Backups, DB files, evidence, lock and recovery files are
Git-ignored. Custom storage paths inside a checkout must also be ignored.

## Local architecture

```text
Shopkeeper UI → FastAPI
                   ├── SQLite: Scan → ScanItem + ScanDetection
                   └── Local photos: originals + annotations
                           ↓ writer lock + consistent snapshot
Local CLI → BackupService → Portable ZIP + manifest/checksums
Local CLI → RestoreService → validated staging → replace DB/photo pair
                                              ↘ retained rollback pair
```

No cloud storage, scheduled jobs, multi-device synchronization, authentication,
multi-shop support or model changes. Five product classes, visible packages only,
hidden stock unknown; the model remains provisional and independent-scene
generalization remains unverified. Retained corrections are not automatically
used for training.

See [results and verification](../reports/V0_6_RESULTS.md). The next single major
milestone is **independent-scene field validation using newly collected, consented
shelf photos**. It is not implemented here.
