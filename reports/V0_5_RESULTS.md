# V0.5 results — scan evidence and prediction history

Completed 2026-09-19. Confirmed history now retains the actual uploaded image,
original AI class counts/detections, annotation and separate reviewed counts.

**The system preserves the original AI prediction separately from the
shopkeeper-confirmed inventory so that human corrections are not destructive.**

## Implementation and database changes

```text
Scan (UUID, time, prediction ID, model identity/hash, dimensions)
 │
 ├── ScanItem (original predicted_count, confirmed_count, reviewed flag)
 ├── ScanDetection (class ID/name, confidence, x1/y1/x2/y2)
 ├── original_image reference
 └── annotated_image reference
```

Original upload bytes are retained exactly as JPEG/PNG, independently of inference
decoding/resizing. The annotation uses the same predictions, never a second model
pass. Confirmed detections use a normalized child table, not a JSON blob.
All five original class records, including zeros, remain recoverable. Unsubmitted
zero classes are flagged unreviewed; only submitted rows appear as confirmed items.

`POST /predict` adds a server-generated prediction UUID and stages its evidence.
Confirmation validates original counts against that server-held prediction. The
client can change confirmed counts, not overwrite scores, boxes, names or AI counts.
Repeated identical confirmation of the same prediction returns the original scan;
different counts on an already confirmed prediction return 409.

Startup performs an additive, transactional migration from v0.4: nullable evidence
metadata, ScanItem product/review metadata, detection table and unique prediction
index. Existing count-only rows remain unchanged and explicitly lack evidence.
No dependencies were added and no frozen inference source/settings changed.

## API and historical UI

| Endpoint | Behavior |
| --- | --- |
| `POST /predict` | Existing inference result plus `prediction_id` |
| `POST /inventory/confirm` | Validate reference/review, publish files and commit scan/items/detections |
| `GET /inventory/scans` | Existing bounded newest-first history |
| `GET /inventory/scans/{scan_id}` | Reviewed counts, original prediction, detections and safe image URLs |
| `GET /inventory/scans/{scan_id}/original` | Original bytes with JPEG/PNG content type |
| `GET /inventory/scans/{scan_id}/annotated` | Original annotation as JPEG |

The UI sends the prediction reference, displays original and annotated photos,
lists original AI counts separately, and marks changed counts **Corrected by
shopkeeper**. Unchanged counts are not labelled as model correctness. Older scans
show a count-only notice; missing files show an unavailable-image message.

Image routes require validated UUIDs and persisted scans, accept no filesystem path,
check fixed managed filenames and resolved containment, and return 404 for missing
scans/files. Raw server paths never enter the API response.

## Files created / modified

- `src/evidence.py`: pending evidence, exact-byte storage, safe paths and cleanup.
- `src/migrations.py`: additive v0.4 database upgrade.
- `src/storage.py`: evidence metadata, normalized detections, original-prediction
  reconstruction, linked confirmation transaction and retry behavior.
- `src/review.py`, `src/api.py`: prediction reference, evidence responses/image routes.
- `src/web/`: evidence panels, prediction/confirmation distinction, correction labels.
- `tests/test_scan_evidence.py`: 11 evidence/data-integrity tests.
- Existing inference/review/history/browser test files and `tests/ui_support.py`:
  server-held prediction fixtures, new contract assertions and one extra browser test.
- `.gitignore`, `README.md`, `docs/V0_5_SCAN_EVIDENCE.md` and this report.
- `reports/v0_5_tests.log`, `v0_5_smoke.json`, `v0_5_integrity.json`: small evidence records.

## Tests

**85 tests passed: 73 existing/adapted + 12 new**, final full run 105.869 seconds.
Command: `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
See [test output](v0_5_tests.log). `pip check` passed.

New tests cover exact original bytes, managed references, 8→7 count separation,
confidence/box/class persistence, reopening with a new app, prediction tampering,
missing/invalid references, idempotent/conflicting retries, missing files/traversal,
JPEG/PNG content types, hostile client filenames, single-inference behavior, damaged
drafts, detection insertion rollback, partial-copy cleanup, storage configuration,
legacy migration, and browser evidence/correction display after refresh.

Tests use temporary databases/files and deterministic predictions. Existing tests
were adapted to obtain a server prediction reference rather than submit unlinked
counts; their inference/count/input-validation and persistence checks remain.

## Real product smoke

One ordinary validation image:
`data/yolo_v01/images/val/IMG_20181218_170247.jpg`.
The smoke used an isolated ignored database/storage root recorded in
[smoke evidence](v0_5_smoke.json), leaving default user history unseeded.

| Check | Result |
| --- | --- |
| Prediction | One real frozen-model inference; six retained detections |
| Correction | Red Bull predicted 4 / confirmed 3; Valser Classic and Still remained 1 each |
| Source retention | Saved original matched uploaded bytes exactly |
| Annotation retention | Saved annotation matched prediction annotation bytes exactly |
| Original prediction | Counts, dimensions, class metadata, boxes and scores matched the original result |
| Browser refresh | History reopened both photos and distinct counts |
| Full backend restart | Same saved response and both image byte sequences remained available |
| New scan | Returned to an empty scan screen |
| Browser/layout | No page errors; desktop and mobile evidence views visually inspected |
| Shutdown | Both app instances and browser stopped cleanly |

The annotation URL changes from a temporary route to its durable scan route; the
underlying bytes and prediction data do not change. No model metrics were calculated,
and the correction was an interaction exercise, not a ground-truth judgement.
Screenshots remain local under ignored `outputs/v05_evidence_*.png`.

## Preservation and data hygiene

Verified **921 protected files**, frozen dataset hashes and **143 tracked inference,
configuration and previous-report files** unchanged from v0.4 commit `f2f42ad`.
Checkpoint SHA-256 remains
`099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4`.
See [integrity record](v0_5_integrity.json).

No retraining, threshold/NMS/preprocessing changes, dataset/split changes or protected
test-set evaluation occurred. Local evidence, SQLite, pending drafts and screenshots
are ignored. No raw datasets, photos, secrets or database files are committed.

## Failure and retention policy

Images are copied before the DB transaction commits. Caught filesystem failures
clean the partial new UUID directory. DB failures roll back parent/items/detections
and clean published files; pending drafts remain for retry. Cleanup never targets
unrelated/historical directories. After commit, pending cleanup is best effort.

Filesystem plus SQLite does not provide a single atomic crash transaction. Abrupt
termination may leave orphan directories; unknown commit outcomes preserve files
for recovery. There is no automatic crash reconciliation. Historical scans/photos
are never automatically deleted, and abandoned drafts also remain. Storage growth,
manual file loss/tampering and the need to back up DB plus image tree are documented.

## Limitations and next milestone

Five source classes only; visible packages only; hidden inventory unknown.
Independent-scene generalization remains unverified and the model is provisional.
Local filesystem/SQLite only; no cloud/object storage, authentication, multi-shop
support, deletion or retention management. Old count-only scans cannot gain evidence
retroactively. Local machine/database access is trusted; this is not tamper-proof.

Retained photos/corrections may be useful for future training/evaluation after
review, but **they are not automatically used for model training** in this milestone.

Exactly one next milestone: **local backup and restore of complete scan evidence**,
covering both SQLite and retained photos. It was not implemented.

## Git delivery

One `feat: persist scan evidence and predictions` commit; no GitHub remote configured.
The final task response records the local commit hash and clean working tree.
