# V0.3 shopkeeper scan and review

## Run locally

The frontend is plain HTML, CSS and JavaScript, served by the existing FastAPI
application. There is one server and no Node build, frontend framework, CDN or
separate frontend installation. The API keeps its existing one-time model load.

From the repository root on the existing environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Open [StoreRoom](http://127.0.0.1:8000/) after `Application startup complete`.
Stop with Ctrl+C. A fresh checkout needs the existing CPU environment and recorded
local checkpoint restored; see [inference setup](INFERENCE_PIPELINE.md).
No new runtime dependencies were needed for v0.3.

## Shopkeeper workflow

1. Choose a JPG/PNG photo, inspect its preview, and select **Analyse shelf photo**.
2. Wait for the loading message. Invalid images and server errors stay on the scan
   screen with an explanation and a retry path. Cancel returns to an empty scan.
3. Inspect the annotated photo and **AI detected** counts. Only detected products
   initially appear in the review list.
4. Use minus, plus, or the numeric field to edit **Your count**. Counts cannot go
   below zero or accept fractions. The original AI count remains visible.
5. If the model missed a supported product entirely, expand **Add a missed product**.
   Its predicted count remains zero; enter the visible count yourself. This is why
   the UI retains zero-count classes in its internal prediction, without listing
   all of them by default. Unrecognized products cannot be added.
6. Select **Confirm Inventory**. The receipt shows the original prediction and
   confirmed counts, with the review time. It describes this photo only.
7. Select **Start a new scan** to clear the photo, predictions, edits and receipt.

An empty detection result explicitly does not mean an empty shelf. The shopkeeper
can add supported products, try another photo, or confirm an empty supported-class
review. Zero-count rows resulting from corrections remain in the confirmed object.

## UI and API flow

```text
Shopkeeper UI (GET /)
     ↓ multipart POST /predict?annotate=true
FastAPI → existing reusable Detector
     ↓ original best-class confidence gate → NMS → counting
Prediction JSON + annotated image URL
     ↓ shopkeeper reviews and edits a separate count copy
POST /inventory/confirm
     ↓ validate mapping, unique classes and integer counts
Confirmed visible-package review (no storage)
```

`src/web/index.html`, `style.css`, and `app.js` contain the interface.
`src/api.py` serves the page/static assets and handles the existing prediction
route. `src/review.py` defines the confirmation contract. Inference, preprocessing,
thresholds, NMS, model weights and counting are unchanged.

Requests use same-origin relative URLs; no CORS service or proxy is needed.
The browser aborts outstanding requests on reset and ignores stale responses.
Cancelling a browser request cannot interrupt CPU inference already in progress;
it prevents that result from repopulating the reset UI. Repeated submits and edits
while confirming are disabled. A failed confirmation preserves edits for retry.
If annotation retrieval fails, the original photo remains available as a fallback.

## Prediction versus confirmation

The API's original `Prediction` object is kept separately from editable review
items. Editing does not change boxes or model scores. Confirmation sends:

```json
{
  "items": [
    {
      "class_id": 0,
      "class_name": "Red Bull",
      "predicted_count": 4,
      "confirmed_count": 3
    }
  ]
}
```

The response preserves `items` and adds:

```json
{
  "status": "confirmed",
  "count_meaning": "visible_items",
  "persisted": false,
  "confirmed_at": "2026-09-19T00:00:00Z",
  "items": [
    {"class_id": 0, "class_name": "Red Bull", "predicted_count": 4, "confirmed_count": 3}
  ]
}
```

The timestamp above is illustrative. The actual timestamp is generated
in UTC by the server and displayed in the browser's local time zone.

Validation uses the existing class mapping: IDs and names must match, IDs must be
unique, and counts must be non-negative integers within JavaScript's safe integer
range. Strings, booleans, fractions, nulls, unknown fields, extra classes and malformed
JSON are rejected with HTTP 422. An empty `items` list is allowed.

This endpoint is stateless. It checks the payload's structure and class mapping,
**not whether a submitted predicted count came from an earlier model response**.
It does not authenticate a shopkeeper or make the correction trusted training data.
The browser preserves provenance within the current interaction only. No SKU,
price, stock value, database record or complete-shop inventory is invented.

Confirmation exists in the page's memory and HTTP response only. Refreshing or
starting a new scan discards it. Annotation files retain the existing local-output
behavior; they are not a saved inventory history. There is no database, localStorage,
automatic download, inventory synchronization, or production persistence.

## Tests

Browser tests add a development-only dependency. Install it once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ui-test.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: **62 tests pass** (48 existing, 6 confirmation/API, 8 browser).
The browser suite runs Chromium against real HTTP routes with deterministic mock
inference. It does not load trained weights or read dataset images. Missing browser
installation is a setup error, not a silently skipped test. It covers upload and
preview, errors/retry, rendered counts, edits and zero limits, unchanged predictions,
confirmation/retry, missed classes, empty results, cancellation/reset, and mobile
layout. API tests reject invalid IDs/names/counts, duplicates and malformed bodies.

## Real local smoke test

This is an explicit product check, not part of test discovery or an ML evaluation.
Use the ordinary validation photo
`data/yolo_v01/images/val/IMG_20181218_170247.jpg`, never the test partition.

1. Start the server and open `/` in a browser.
2. Upload that image; verify preview and analyse it once.
3. Check that the annotated image loads and detected products appear.
4. Change Red Bull from the displayed AI count to one less; ensure **AI detected**
   remains unchanged and **Your count** changes.
5. Confirm, inspect the receipt, and verify the two counts remain distinct.
6. Start a new scan; verify there is no old preview, receipt, or enabled analyse action.
7. Check desktop and mobile widths; stop the server with Ctrl+C.

The recorded browser-driven smoke made one actual prediction request and passed all
steps. Its outputs are in [the smoke record](../reports/v0_3_smoke.json); screenshots
were inspected locally under `outputs/v03_*.png`. The correction was an interaction
exercise, not a ground-truth count or a model-performance judgment.

## Limits and next milestone

Five product classes only; visible packages only; hidden stock is unknown.
Independent-scene generalization remains unverified and the model is provisional.
No guarantee exists for a new Indian shop or an unseen product. This is a local,
English-language workflow without authentication, durable storage or deployment
hardening. Camera capture is left to the browser's file picker; dedicated live-camera
capture is not implemented. Existing input limits and output cleanup limitations apply.

Next major product milestone: **durable scan-and-review history**, preserving the
photo reference, model identity, original prediction, human edits and timestamp so
reviewed observations can be retrieved and compared. This is a future milestone;
it should not silently merge observations into complete-shop stock counts.

Static serving follows FastAPI's [official StaticFiles documentation](https://fastapi.tiangolo.com/tutorial/static-files/).
