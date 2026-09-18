# V0.3 results — shopkeeper scan and review

Completed 2026-09-19. A shopkeeper can upload a shelf photo, inspect AI detections,
correct visible-package counts, and confirm the review. This is a product
engineering milestone; no ML experiment, training or threshold tuning occurred.

## What was built

- A responsive scan screen with image selection, preview, loading, cancel and error/retry states.
- A review screen with the existing annotated output and detected-product list.
- Separate original predicted counts and editable confirmed counts, with minus/plus
  controls and direct numeric entry. Counts cannot be negative or fractional.
- An optional **Add a missed product** control for supported classes with zero
  detections. Only detected/explicitly added classes appear in the main list.
- A **Confirm Inventory** action and receipt showing the human-reviewed counts,
  original predictions and timestamp. Starting a new scan clears the page state.
- A stateless confirmation endpoint validating class identity, unique IDs, strict
  nonnegative integer counts, and malformed/extra payload fields.

Confirmation is kept in browser memory and the HTTP response. It is not stored in
a database, browser storage or a permanent inventory file. The UI states this.
An empty detection result explicitly does not assert that the shelf is empty.

## Architecture

```text
Shopkeeper UI (plain HTML / CSS / JavaScript)
     ↓ same-origin POST /predict
FastAPI
     ↓ existing reusable Detector (one startup load)
Class-specific filtering → NMS → counting
     ↓ unchanged prediction result + annotation
Shopkeeper review (separate editable counts)
     ↓ POST /inventory/confirm (no inference)
Validated confirmed visible-package review (no persistence)
```

The existing FastAPI process serves `GET /` and `/static/`. No separate frontend
server, package build, application framework or runtime dependency was added.
The prediction route, model, configuration, preprocessing and counting logic remain
unchanged. Static serving uses FastAPI's existing StaticFiles support.

The confirmation endpoint validates structure and the known class mapping, but
cannot attest that client-submitted predictions came from a prior model response.
It is not an authenticated or durable provenance record for training data.

## Files created / modified

| Files | Purpose |
| --- | --- |
| `src/api.py` | Serve UI/assets; add `/inventory/confirm`; API version 0.3 |
| `src/review.py` | Confirmation request/response validation and UTC timestamp |
| `src/web/index.html`, `style.css`, `app.js` | Scan, review, correction, confirmation and reset |
| `tests/test_review.py` | Six API/confirmation tests |
| `tests/test_shopkeeper_ui.py`, `tests/ui_support.py` | Eight real-browser tests and deterministic HTTP fixtures |
| `requirements-ui-test.txt` | Development-only Playwright dependency |
| `docs/V0_3_SHOPKEEPER_WORKFLOW.md`, `README.md` | Local setup, user/API flows, contracts, tests and limits |
| `reports/v0_3_tests.log`, `v0_3_smoke.json`, `v0_3_integrity.json` | Small verification records |
| `reports/V0_3_RESULTS.md` | This delivery report |

The earlier v0.2 report and inference guide remain historical documentation;
this workflow guide covers the new UI/confirmation routes. No protected model or
dataset files are included in this change. Local screenshots stay under ignored
`outputs/` rather than entering Git.

## Tests

**62 tests passed: 48 existing + 14 new**, in 40.837 seconds.
Command: `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
See [full test log](v0_3_tests.log). `pip check` also passed.

Six API tests cover valid confirmation, no extra inference, known ID/name pairs,
strict counts, negative/fractional/string/boolean rejection, duplicate classes,
extra fields, malformed JSON, empty/zero confirmations, and static routes.
Eight Chromium tests exercise real DOM interactions and HTTP with mock inference:
upload/preview, rendered products, increment/decrement, typed counts and zero limits,
unchanged predicted counts, missed products, empty detections, errors/retry,
confirmation and retry, cancellation/stale response handling, reset/new scan, and
mobile overflow. The full image → prediction → correction → confirmation flow is tested.

Browser tests require `requirements-ui-test.txt` and `python -m playwright install
chromium` in the virtual environment. They never load model weights or dataset
images. Tests are not skipped when browser dependencies are absent.

## Real local smoke

A real local Uvicorn application and Chromium browser used the frozen model on:
`data/yolo_v01/images/val/IMG_20181218_170247.jpg` (ordinary validation, not test).

| Step | Observed result |
| --- | --- |
| Open UI and choose image | Preview displayed |
| Analyse | One `/predict` request; HTTP 200; annotated image decoded/displayed |
| AI counts | Red Bull 4, Valser Classic 1, Valser Still 1; total 6 |
| Correction | Red Bull changed to 3; **AI detected 4** remained unchanged |
| Confirmation | HTTP 200; Red Bull predicted 4 / confirmed 3; reviewed total 5 |
| Persistence flag | `persisted: false`; page explicitly says not saved permanently |
| New scan | Old image, result and receipt cleared; analyse disabled until selection |
| Browser health | No page errors; no horizontal overflow at 390px |
| Shutdown | Browser and local server stopped cleanly |

Desktop scan and desktop/mobile review screenshots, plus the mobile receipt,
were visually inspected. Large touch controls and distinct AI/reviewed counts
were readable. Screenshots are local in `outputs/v03_*.png`.
See [smoke evidence](v0_3_smoke.json).

The correction was a workflow exercise, not a ground-truth annotation. No accuracy
metric was calculated and no model/configuration decision was based on the image.

## Preservation

The existing audit verified **921 protected files** and frozen dataset hashes.
Additionally, **135 tracked inference/configuration/report files** were compared
byte-for-byte with v0.2 commit `c1ed247`; all were unchanged. This includes the
shared inference package, model profile, class mapping and previous reports.
AUGMENTATION_001 checkpoint SHA-256 remains
`099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4`.
See [integrity record](v0_3_integrity.json).

No retraining, threshold tuning, dataset/split modification or protected test-set
evaluation occurred. Historical tests inspect saved evidence without new test inference.

## Limitations

- Five product classes only; visible-package counting only; hidden stock is unknown.
- The model is provisional. Independent-scene generalization remains unverified.
- Correcting counts does not correct boxes or verify product variants/pack sizes.
- Confirmation is not persisted to a production database or any durable review store.
- No authentication, accounts, catalog, synchronization, payments, delivery or cloud infrastructure.
- English-language local workflow; dedicated live-camera capture is not implemented.
- Existing annotation files have no automatic retention policy. Cancelling a request
  resets the UI but cannot interrupt CPU inference that has already started.

## Next major product milestone

**Durable scan-and-review history**: preserve the original prediction, human
corrections, photo/model references and timestamp, with a way to retrieve past
reviews. This addresses the current loss of confirmed results on refresh. Keep
these records as visible-shelf observations rather than silently treating them as
complete-shop stock. This next milestone was not implemented.

## Git delivery

Changes are delivered in one `feat: add shopkeeper scan and review workflow`
commit. No GitHub remote is configured, so delivery is local. The final task
response records the commit hash and clean working-tree verification.
