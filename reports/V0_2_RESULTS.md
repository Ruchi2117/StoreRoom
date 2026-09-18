# V0.2 results: reusable inference pipeline and API

Completed 2026-09-19. This product-engineering milestone adds a local
upload → detection → visible-item count → JSON + annotated image workflow.
No new ML experiment was performed.

## Implementation and files

- `src/inference/`: shared detector, profile loader, validated image decoding,
  result schema, and annotation renderer. Reuses frozen pre-NMS confidence gate
  and existing counting function; no evaluator changes.
- `src/api.py`: FastAPI adapter with one detector loaded during startup,
  serialized access to shared model state, and upload/error handling.
- `src/smoke_api.py`: explicit single-image loopback HTTP smoke check.
- `tests/test_inference_api.py`: 12 deterministic tests, using a fake model.
- `requirements-api.txt`: additional pinned API/test dependencies; existing
  CPU/ML requirements and historical lock remain unchanged.
- `configs/inference_v01.json`: now consumed by the module/API. Only its usage
  description changed; all frozen values remain identical.
- `docs/INFERENCE_PIPELINE.md` and `README.md`: setup, architecture, Python and
  HTTP usage, result contract, error behavior, limitations, and next milestone.
- `reports/v0_2_smoke.json`, `v0_2_integrity.json`, `v0_2_tests.log`: verification
  evidence. Generated images and disposable logs remain ignored under `outputs/`.

## API

| Endpoint | Behavior |
| --- | --- |
| `GET /health` | 200 with `{"status":"ok"}` after model startup |
| `POST /predict` | One multipart `file`; returns all five counts and detections |
| `GET /annotations/{id}.jpg` | Retrieve the optional rendered result |

`POST /predict?annotate=false` skips annotation; default is true. Python callers
use `Detector().predict(image, annotate=True)` on a reused detector instance.
Outputs include model identity/hash, original image dimensions, source class IDs,
product identities, nonnegative counts, confidence and pixel-coordinate boxes.
Counts and rendering consume exactly the same retained detections.

Startup rejects missing or changed weights before loading. No replacement weights
are downloaded. JPEG/PNG inputs are content-validated; empty/multiple uploads,
corrupted images, unsupported formats, and oversized inputs produce explicit errors.
The decoder bypasses the installed Ultralytics HEIF fallback so invalid bytes do
not trigger optional decoder installation or a server error.

## Frozen configuration

| Setting | Value |
| --- | --- |
| Model | AUGMENTATION_001 YOLO11n, 30 training epochs |
| Checkpoint | `runs/augmentation_001/weights/best.pt` |
| SHA-256 | `099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4` |
| Inference | CPU, 320px, rect true, batch 1, max_det 300, augment false |
| NMS | class-aware, IoU 0.50 |
| Confidence | Red Bull 0.15; Knoppers / Valser Classic / Valser Still / Capri-Sun Multivitamin 0.25 |

Cutoffs use the original best class, strict `>`, before NMS, with no runner-up
relabeling. The existing configuration file is the only active settings source.
No thresholds, weights, class mappings or evaluation logic changed.

## Tests and integrity

Full command: `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
**48 tests passed** (36 existing + 12 new), final run 45.536 seconds.
New tests cover profile values, one-time loading, frozen predictor reuse,
structured counts, zero detections, checkpoint failures, mapping mismatch,
valid/invalid/corrupt image inputs, annotation behavior, HTTP errors, startup
failure, and exact JSON parity between direct Python and HTTP with a fake model.
`pip check` also passed. See [test output](v0_2_tests.log).

The existing `verify_protected()` verified **921 protected files** and frozen
dataset hashes. AUGMENTATION_001 and BASELINE_002 checkpoint hashes match their
recorded values. See [integrity evidence](v0_2_integrity.json).
Dataset, split, labels, frozen test set, old experiment source, and protected
artifacts remain unchanged. No retraining or test-set evaluation occurred.
Historical tests inspect saved evidence; they do not rerun inference on test data.

## Local runtime smoke

Used exactly one ordinary validation image:
`data/yolo_v01/images/val/IMG_20181218_170247.jpg` (4640 × 3480).
A real Uvicorn server listened on loopback and used the real frozen checkpoint.

| Check | Result |
| --- | --- |
| Health | HTTP 200 |
| Real upload | HTTP 200; valid structured JSON |
| Predicted counts | Red Bull 4, Knoppers 0, Valser Classic 1, Valser Still 1, Capri-Sun 0; total 6 |
| Annotation retrieval | HTTP 200, valid full-size JPEG |
| Invalid image bytes | HTTP 422 |
| Server shutdown | Clean |

These are runtime outputs, **not accuracy measurements**. No ground-truth scoring,
model selection or tuning was performed. The saved six detections were rendered
again after improving label readability, without another model call. Visual
inspection confirmed readable class/confidence labels and matching boxes.
The original HTTP evidence and final local render path are in
[smoke record](v0_2_smoke.json). No test image was used.

## Limitations

Only five source product classes are supported. The model is provisional, selected
on a small repeatedly used validation set, and independent-scene generalization
remains unverified. Existing Valser regressions are not resolved by this API.
Visible-package counting cannot reveal hidden inventory or certify sizes, prices,
ingredients, dietary suitability or actual stock availability.

This is a local CPU demonstration with serialized inference, no authentication,
no automatic output retention, and no public-service deployment hardening. No
frontend, database, accounts, queues, Docker or distributed infrastructure was added.
Fresh clones require separately restoring the ignored checkpoint; historical
artifact tests also require their dataset/run evidence.

## Next single product milestone

Build a **shopkeeper scan-and-review interface**: upload a shelf photo, inspect the
annotated detections and counts, and correct visible counts before using the result.
This makes the provisional detector useful in a human-reviewed workflow without
claiming reliable autonomous inventory synchronization. Do not introduce another
hyperparameter experiment as part of that milestone.

## Git delivery

Implementation, tests, documentation and small verification evidence are delivered
in one `feat: add reusable inference pipeline and API` commit. No raw data, weights,
virtual environment, secrets or rendered images are included. No GitHub remote is
configured; the commit is local. The delivered commit hash and final clean-tree
confirmation are reported in the task's final response.
