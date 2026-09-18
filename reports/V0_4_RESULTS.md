# V0.4 results — durable scan and review history

Completed 2026-09-19. Confirmed scans now survive browser refresh and backend
restart and can be reopened read-only. No ML experiment was performed.

## Implementation and data model

Added SQLite persistence through SQLAlchemy, atomic confirmation, recent/single-scan
APIs, and a responsive history/read-only review UI. Each observation retains a
server-generated UUID, UTC timestamp, original submitted predictions and human counts.

```text
Scan: UUID, created_at (UTC), status='confirmed'
 │
 ├── ScanItem: ID, scan_id, class_id, class_name, predicted_count, confirmed_count
 ├── ScanItem
 └── ...
```

Foreign keys, unique classes per scan and nonnegative integer constraints protect
consistency. Input validation enforces class identity and strict counts. Empty
supported-class reviews and counts corrected to zero remain valid.

Each operation owns a session. Confirmation flushes parent/items in one transaction
and returns only after commit. Failure rolls back the complete scan. Errors do not
reveal SQL or database paths. No catalog, user, shop, price or SKU tables were added.

## API and UI

| Endpoint | Behavior |
| --- | --- |
| `POST /inventory/confirm` | Persist review; return UUID, timestamps, `persisted: true` and items |
| `GET /inventory/scans` | Newest first; default 20, validated limit 1–100; class count per scan |
| `GET /inventory/scans/{scan_id}` | Full saved review; invalid UUID 422, absent UUID 404 |

The confirmation request and HTTP 200 are retained. `confirmed_at` aliases
`created_at` for v0.3 clients. No historical edit/delete endpoints exist.
The prediction route and shared inference/counting code remain unchanged.

Scan History shows date/time and represented class count. Open scan displays both
counts read-only. Refresh, empty/error states, draft return and new scan work.
Reset clears browser state, not saved history. Observations are never summed into
complete-shop inventory.

## Database and images

Default: `data/storeroom.db`, configurable with `STOREROOM_DB_PATH`. Relative paths
resolve from the repository root. Automatic startup initialization creates missing
tables idempotently; it does not migrate existing schemas. SQLAlchemy 2.0.54 is the
new direct dependency. No separate DB server, Docker or frontend build is needed.

History stores metadata/counts only, not photos, image paths, boxes or model IDs.
The current scan still displays its temporary annotation; history works without it.
The UI explicitly states that historical photos are not stored.

## Files

- New `src/storage.py`: tables, SQLite initialization, transactions and retrieval.
- Updated `src/review.py`, `src/api.py`: persisted schemas, lifecycle and routes.
- Updated `src/web/`: history, saved-review view and saved receipt language.
- Updated `requirements-api.txt`, `.gitignore`: dependency and DB/sidecar exclusions.
- New `tests/test_scan_history.py`: eight persistence/API tests.
- Updated `tests/test_shopkeeper_ui.py`: three history browser tests.
- Updated `tests/test_review.py`, `tests/test_inference_api.py`: isolated temporary DBs;
  the confirmation assertion now verifies persistence and retrieval.
- New `docs/V0_4_SCAN_HISTORY.md`; updated `README.md`.
- This report plus `v0_4_tests.log`, `v0_4_smoke.json`, `v0_4_integrity.json`.

V0.3 assertions explicitly describing non-persistence were updated to the new
contract. Existing count, inference and input-validation coverage was retained.

## Tests

**73 tests passed: 62 retained/updated + 11 new**, in 41.901 seconds.
Command: `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
See [test output](v0_4_tests.log). `pip check` passed.

Eight new DB/API tests cover initialization/configuration, relationships, timestamps,
reopening SQLite, multiple/zero items, a real item-constraint failure and rollback,
DB count/foreign-key constraints, ordering/limits, app restart, UUID/404/422 handling,
read-only routes and storage-error hygiene. Three browser tests cover history after
refresh, reopening, two saved scans, retry/draft preservation, and empty/missing UI.
Tests use temporary databases and mock inference, never the default local history.

## Real local smoke

Used ordinary validation photo `data/yolo_v01/images/val/IMG_20181218_170247.jpg`
twice, with a separate ignored smoke database recorded in [evidence](v0_4_smoke.json).
The default local history was not seeded by the smoke.

| Step | Result |
| --- | --- |
| Upload/predict/review | Real frozen model; annotation and counts appeared |
| Correct first scan | Red Bull predicted 4, confirmed 3; other classes preserved |
| Confirm | HTTP 200, real UUID and persisted receipt |
| Refresh UI | First scan remained in history |
| Stop backend, start new app with same DB | First scan reopened with identical counts/timestamp |
| Confirm second scan | Separate UUID; Red Bull predicted/confirmed 4 |
| History | Both scans newest first; both API details matched receipts |
| Browser | No errors; mobile history and read-only detail visually inspected |
| Shutdown | Both server instances and browser stopped cleanly |

Exactly two real prediction requests occurred. The correction exercised the UI,
not ground-truth scoring. Screenshots remain ignored under `outputs/v04_*.png`.
No model-performance measurement or tuning occurred.

## Preservation and hygiene

Verified **921 protected files**, frozen dataset hashes and **139 tracked inference,
configuration and prior-report files** unchanged from `265df18`. Checkpoint SHA-256:
`099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4`.
See [integrity evidence](v0_4_integrity.json).

No retraining, inference-setting changes, dataset/split changes or protected test-set
evaluation occurred. DB/sidecar ignore rules were checked. No datasets, caches,
secrets, database files or temporary screenshots are included in the commit.

## Limitations and next milestone

Five classes only, visible packages only, hidden inventory unknown. The model remains
provisional and independent-scene generalization unverified. This local SQLite layer
is not production infrastructure: no backup service, authentication, multi-shop
isolation, migrations or inventory synchronization. Historical photos are not stored.

Submitted predictions are validated structurally, not checked against server-held
inference evidence; these reviews are not automatically trusted ML labels. Every
successful POST creates a new scan, with no idempotency protocol. Check history
before retrying an uncertain save. The UI shows only the 20 newest records.

Next major milestone: **traceable scan evidence** linking retained photos and
server-side prediction records to human reviews. This would make corrections
auditable and address missing image/provenance linkage. It was not implemented.

## Git delivery

One `feat: persist shopkeeper scan history` commit. No GitHub remote is configured,
so delivery is local. The final response records the hash and clean-tree verification.
