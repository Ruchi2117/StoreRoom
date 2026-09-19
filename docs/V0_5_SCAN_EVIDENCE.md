# V0.5 — scan evidence and prediction history

**AI prediction ≠ confirmed inventory.** The original photo, AI counts, boxes and
confidence scores remain separate from shopkeeper corrections. Historical scans now
show original and annotated photos, original AI counts, and the reviewed counts.
Changed counts are labelled **Corrected by shopkeeper**. Unchanged counts are not
presented as proof that the model was correct.

## Run locally

Use the existing environment and frozen local checkpoint. No new dependencies are
needed beyond v0.4. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Open [StoreRoom](http://127.0.0.1:8000/). Use a single application process.
Optional settings, supplied before startup:

```powershell
$env:STOREROOM_DB_PATH = 'data/storeroom.db'
$env:SCAN_STORAGE_DIR = 'data/scans'
```

Both default to these locations relative to the repository root. Absolute paths
can be configured on the server, but clients cannot submit file paths. Keep the
same database **and** storage root on restart. Changing roots does not move photos.
Custom locations inside a Git checkout must also be ignored.

## Flow and original-prediction ownership

```text
POST /predict (uploaded bytes)
   → existing detector, exactly one inference pass
   → original result + annotation from those same detections
   → server-held pending evidence + prediction_id
Browser reviews counts
   → POST /inventory/confirm with prediction_id and edited items
   → verify original counts against server evidence
   → copy evidence into a scan-owned directory
   → commit scan, items and detections together
History → original photo + AI evidence + confirmed counts
```

The API preserves the uploaded byte string independently of decoding/resizing.
`original.jpg` or `original.png` contains exactly those bytes, not a re-encoded
image, thumbnail, 320px input or annotation. The original client filename is never
used for storage. PNG/JPEG content determines the generated extension.

The existing annotation file is copied byte-for-byte. If a caller requests
`annotate=false`, the response still omits the temporary annotation URL, but an
evidence annotation is rendered from the existing detections. No second inference
pass occurs. No confidence thresholds, NMS, preprocessing or counting logic changed.

## Data model

```text
Scan
 ├── ScanItem (predicted_count, confirmed_count, product_id, reviewed)
 ├── ScanDetection (class_id, class_name, confidence, x1, y1, x2, y2)
 ├── original_image reference
 └── annotated_image reference
```

Scan retains its UUID/time/status plus relative image references, prediction UUID,
model ID/checkpoint hash and image dimensions. Images are not SQLite blobs.
ScanDetection is a normalized child table with a foreign key, confidence and box
constraints. The model output's scores/coordinates are not rounded on persistence.

All five original class records are retained in ScanItem, including zero predictions.
`reviewed` distinguishes submitted review rows from omitted zero classes. Only
reviewed rows appear in the response's `items` and history class count; omitted zero
classes do not become claims that the shopkeeper reviewed them. The complete
`original_prediction` is reconstructed from all class rows and ScanDetection rows
using the existing typed Prediction schema. Thus zero detections remain recoverable.

Every nonzero predicted class must be included in the review. Added missed classes
can have original count zero and positive confirmed count. Submitted predicted
counts/names must match the server record. Clients cannot submit replacement boxes,
scores or paths. Historical updates are not supported.

## Local files and retention

```text
data/scans/
  .pending/<prediction_id>/
    original.jpg (or original.png)
    annotated.jpg
    prediction.json
  <scan_id>/
    original.jpg (or original.png)
    annotated.jpg
```

Pending JSON uses the existing Prediction schema to carry a server-owned draft
across requests/restarts. Its image digests detect damaged draft files before
confirmation. The confirmed database uses relational rows, not an opaque JSON
detection blob. Only managed relative image references enter Scan records.

Confirmed photos are retained locally indefinitely. No scan deletion endpoint,
expiration, quota, cloud storage or retention manager exists. Abandoned pending
predictions are also retained; storage growth is a known limitation. A successful
confirmation removes its pending directory only after DB commit. This cleanup
does not delete historical evidence. Existing temporary annotation output behavior
also remains unchanged.

## Transactions, cleanup and limits

Image copies must finish before the scan transaction commits. The parent, all class
rows and every detection share one SQLite transaction. Caught copy/write failures
clean the partial scan directory. DB failure rolls back all rows and cleans only
the newly generated, containment-checked UUID directory. Pending evidence remains
available for retry. If commit succeeds, a later pending-cleanup failure does not
undo the scan.

An identical retry with the same prediction ID returns the existing scan; changed
counts for an already confirmed prediction return 409. A unique DB index prevents
multiple scans for one prediction. File promotion is serialized within the supported
single-process app; distributed/multi-process coordination is not implemented.

**SQLite and filesystem writes are not one atomic resource transaction.** A process
crash or power loss between copying and committing may leave an orphan directory;
an uncertain commit outcome preserves files rather than risking deletion of
committed evidence. Cleanup itself can fail on permission/disk errors. There is no
automatic crash reconciliation or protection against manual file/DB edits. Missing
files return 404 and the UI shows an unavailable-image message. Back up the database
and storage tree together while the application is stopped.

## Migration and older history

Startup runs the additive migration in `src/migrations.py`, using an explicit
SQLite transaction. It adds nullable Scan evidence columns, ScanItem metadata, the
detection table and a unique prediction index; `PRAGMA user_version` becomes 1.
It does not rebuild or erase v0.4 records. Repeated startup is safe; newer unknown
schema versions are rejected. This is a small fixed migration, not a general
migration framework. See SQLite's [ADD COLUMN documentation](https://www.sqlite.org/lang_altertable.html).

Existing v0.4 scans remain readable with their original counts and timestamps.
They have null evidence URLs/prediction and no detections. The UI explicitly labels
them as older count-only scans; it never fabricates photos or AI evidence.

## API

| Endpoint | Contract |
| --- | --- |
| `POST /predict` | Existing response plus server-generated `prediction_id` |
| `POST /inventory/confirm` | Requires that ID and review items; persists linked evidence |
| `GET /inventory/scans` | Existing newest-first history and bounded limit |
| `GET /inventory/scans/{scan_id}` | Saved items, image URLs, original prediction and flat detections |
| `GET /inventory/scans/{scan_id}/original` | Exact original bytes; image/jpeg or image/png |
| `GET /inventory/scans/{scan_id}/annotated` | Saved annotation; image/jpeg |

Confirmation request (ID is obtained from `/predict`):

```json
{
  "prediction_id": "9bcd611d-fd65-4fd0-b37b-c999d49e5651",
  "items": [{"class_id":0,"class_name":"Red Bull","predicted_count":8,"confirmed_count":7}]
}
```

Include every class with a nonzero prediction. Count-only v0.4 clients must add the
prediction reference; missing IDs return 422. Existing field validation still
rejects invalid IDs/names/counts and extra fields. Unavailable drafts return 404;
damaged drafts or conflicting retries return 409; original-count tampering returns
422; storage failures use generic 503 messages.

Saved responses add `original_image_url`, `annotated_image_url`, `prediction_id`,
`original_prediction` and `detections`. A flat detection includes class ID/name,
confidence and original-image `[x1,y1,x2,y2]`. Image references in responses are
routes, never raw filesystem paths. The annotation reference in reconstructed
prediction points to the durable route, replacing the temporary URL.

Image routes validate UUIDs, require a persisted scan, check managed names and
resolved containment, and verify files exist. Unknown scans/images return 404;
malformed UUIDs return 422. No directory is mounted publicly and no arbitrary path
parameter is accepted.

## Verification and limitations

Run `.venv\Scripts\python.exe -m unittest discover -s tests -v` after installing the
existing UI test dependencies/browser. Expected: 85 tests pass. New coverage checks
8→7 immutability, exact bytes, PNG/JPEG content types, detections, migration, restart,
tampering, missing files/traversal, retry behavior, damaged drafts, rollback/copy
cleanup and historical UI. Tests use temporary files and deterministic predictions.

The real smoke uses ordinary validation image
`data/yolo_v01/images/val/IMG_20181218_170247.jpg`, corrects one count, confirms,
refreshes, opens both photos, restarts the backend and reopens the same evidence,
then starts a new scan. It makes one inference request and does no accuracy scoring.
See [recorded results](../reports/V0_5_RESULTS.md).

Five source classes only; visible packages only; hidden stock remains unknown.
The model is provisional and independent-scene generalization remains unverified.
No authentication/multi-shop isolation, cloud/object storage or deletion/retention
management was added. Local filesystem/database access is trusted; this is not a
tamper-proof evidence vault.

Photos and corrections may support future training/evaluation after appropriate
review and scene-aware data governance. They are **not automatically used for model
training** in v0.5. The next single milestone is local backup and restore of complete
scan evidence (database plus photos); it is not implemented here.
