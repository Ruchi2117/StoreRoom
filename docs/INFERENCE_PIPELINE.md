# V0.2 inference pipeline and local API

V0.2 exposes the provisional AUGMENTATION_001 model through one Python component
and a thin FastAPI adapter. No model training, evaluation loop, or label loading
is part of a prediction request.

## Architecture

```text
JPEG/PNG bytes, path, or uint8 BGR image
  ↓ validate and decode with OpenCV
Loaded YOLO model → class scores
  ↓ original best-class confidence gate
Class-aware NMS
  ↓ count retained boxes
Structured JSON + optional annotated image (same detections)
```

`src/inference/detector.py` owns prediction and calls the unchanged
`src/class_confidence_predictor.py` and `src/counting.py`. The HTTP adapter in
`src/api.py` delegates to this detector. `images.py` validates inputs,
`results.py` defines the Pydantic contract, and `annotation.py` draws results.
The existing predictor imports runtime settings through `src/train_baseline.py`;
that import does not train. Frozen research source and evaluators remain unchanged.

## Model and configuration

The single active profile is `configs/inference_v01.json`; class metadata comes
from `configs/class_map.json`. Settings are not exposed as request parameters.

| Setting | Frozen value |
| --- | --- |
| Checkpoint | `runs/augmentation_001/weights/best.pt` |
| Model | AUGMENTATION_001 YOLO11n, trained for 30 epochs |
| SHA-256 | `099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4` |
| Device / image size | CPU / 320 |
| NMS | class-aware, IoU 0.50 |
| Red Bull confidence | 0.15 |
| Other four classes | 0.25 |
| Other inference options | batch 1, rect true, max_det 300, augment false |

Scores must be strictly greater than the class cutoff. The original highest-score
class determines the cutoff; rejected boxes are not relabeled to another class.
The minimum candidate floor is 0.15, followed by the existing gate **before NMS**.
A missing checkpoint or hash mismatch fails startup clearly; no replacement model
is downloaded. One detector loads once per application process. A lock serializes
prediction because Ultralytics shares mutable predictor state.

## Local setup (Windows / PowerShell)

Run from the repository root. The validated environment is Python 3.14.4 with the
existing CPU runtime. A fresh clone does not contain the ignored checkpoint or
dataset; restore the recorded local artifacts as described in
[reproducibility](REPRODUCIBILITY.md). The API itself only needs the checkpoint,
profile, mapping, code, and an input image, not the training dataset.

```powershell
# Only create a virtual environment if one does not already exist:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-cpu.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Use one worker. Wait for `Application startup complete`; press Ctrl+C to stop.
On the existing environment only the API dependency installation is needed.
Existing ML dependency files and the historical runtime lock are preserved.
The additional pinned dependencies are in `requirements-api.txt`.

## Python usage

```python
from src.inference import Detector

detector = Detector()  # load once; reuse this instance
result = detector.predict("shelf.jpg", annotate=True)
print(result.model_dump_json(indent=2))
# JSON-compatible dictionary, if needed:
payload = result.model_dump(mode="json")
```

`predict` also accepts JPEG/PNG bytes or a nonempty uint8 BGR NumPy array.
Direct Python annotation defaults to off. When enabled, `annotated_image` is the
filename under `detector.output_dir`, normally `outputs/annotations/`.
An optional `Detector(output_dir=...)` can select an external directory or a
repository directory under `outputs/`. Protected research directories are refused.

## HTTP usage

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST "http://127.0.0.1:8000/predict?annotate=true" -F "file=@shelf.jpg" -o prediction.json
```

- `GET /health`: 200 and `{"status":"ok"}` after successful model startup.
- `POST /predict`: exactly one multipart upload named `file`.
- `annotate=true` is the HTTP default; use `?annotate=false` to skip rendering.
- `GET /annotations/{id}.jpg`: retrieve a generated image using its response URL.
- `GET /docs`: interactive request form and complete response schema.

The response includes `model_id`, `checkpoint_sha256`, original image dimensions,
`count_meaning: "visible_items"`, `identity_level: "source_product_class"`,
`products`, `total_count`, and `annotated_image` (URL or null). Each of the five
products is present, including zeros:

```text
products[i] = {
  class_id: integer,
  class_name: string,
  product_id: source identity string,
  count: nonnegative integer,
  detections: [{confidence: number, bbox: [x1, y1, x2, y2]}, ...]
}
```

Boxes use original-image pixel coordinates. Each count equals its retained
box count; `total_count` equals their sum. These source identities do not certify
pack size or exact commercial SKU. Annotations contain the same boxes and scores,
with no second inference pass. Unique filenames prevent overwrites. Outputs are
local, ignored by Git, and remain until manually removed; there is no retention
service. The HTTP result URL is relative to the running server.

## Input errors

The content is decoded rather than trusting a filename or MIME label.

| Input | HTTP status |
| --- | --- |
| Missing multipart field | 422 |
| Empty file or multiple uploads | 400 |
| Unsupported decoded format (such as GIF) | 415 |
| Corrupted/unrecognizable image bytes | 422 |
| File above 20 MiB or image above 25 megapixels | 413 |
| Missing annotation | 404 |

Python callers receive `ImageInputError` with a `status_code` for corresponding
input failures. File paths must exist. Pillow checks image structure/dimensions
before OpenCV decoding. Its original decoder is used to bypass Ultralytics'
optional HEIF installation fallback; the API does not install decoders on requests.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -c "from src.independent_validation_001_audit import verify_protected; print(verify_protected())"
# Optional explicit runtime check: runs one ordinary validation image, not accuracy evaluation.
.\.venv\Scripts\python.exe -m src.smoke_api
```

The 48 tests include 36 historical tests and 12 deterministic pipeline/API tests.
The manual smoke script binds a loopback port, uploads the recorded ordinary
validation image, checks its JSON and rendered output, rejects invalid bytes,
and shuts down. It updates `reports/v0_2_smoke.json`; it is not run by test discovery.
See [v0.2 results](../reports/V0_2_RESULTS.md) for the recorded run.

## Limits and next milestone

Only five source product classes are supported. This provisional model was selected
on a small, repeatedly consulted validation set. Independent-scene generalization
remains unverified, and prior Valser counting regressions remain unresolved.
Visible-package counts do not reveal hidden inventory, prices, ingredients or
actual shop availability. The API adds no new performance claim.

This is a local, single-process demonstration: no authentication, database, queues,
cloud storage, or public-deployment hardening. The decoded input limits are not a
reverse-proxy request-body limit. Annotated outputs have no automatic cleanup.

Next single product milestone: a shopkeeper scan-and-review interface that displays
the image and predicted counts and lets the shopkeeper correct them before use.

Implementation references: FastAPI's official [upload documentation](https://fastapi.tiangolo.com/tutorial/request-files/)
and [lifespan documentation](https://fastapi.tiangolo.com/advanced/events/).
