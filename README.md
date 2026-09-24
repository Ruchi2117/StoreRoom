# StoreRoom

Detect and count **visible instances of five source product classes** in shelf images.
The v0.1 CV experimentation phase is complete. The **provisional v0.1 model** is
augmented YOLO11n from AUGMENTATION_001, trained for 30 epochs.

| Current configuration | Value |
| --- | --- |
| Local checkpoint | `runs/augmentation_001/weights/best.pt` |
| Inference | CPU, 320px, class-aware NMS IoU 0.50 |
| Confidence | Red Bull 0.15; Knoppers, Valser Classic, Valser Still, Capri-Sun 0.25 |
| Validation | Precision 0.791, recall 0.888, counting MAE 0.423, exact counts 11/26 |

Class-specific confidence filtering occurs **before NMS**, using the original
best-scoring class without relabeling. These results are measured on the existing
26-image validation set; **independent-scene generalization remains unverified**.
There are no eligible unused verified scene groups in the current dataset.
Both Valser classes have worse counting MAE than the preceding model.

Read the [v0.1 results summary](reports/V0_1_RESULTS.md),
[detailed augmentation comparison](reports/AUGMENTATION_001_RESULTS.md), and
[independent-scene audit](reports/INDEPENDENT_VALIDATION_001_RESULTS.md).
This model is not production-ready and does not estimate hidden stock, prices,
verified pack sizes, ingredients or availability.

The frozen HoloSelecta export contains 175 images across 33 machine groups:
123 training / 26 validation / 26 test, with 1,480 target boxes. The test set was
not used for model selection. One historical BASELINE_001 evaluation was performed
after freezing that baseline; later experiments never re-evaluated the test set.
Do not use it for independent validation or further tuning.

## Verification and reproducibility

On the existing artifact-complete checkout (install `requirements-ui-test.txt` and
run `python -m playwright install chromium` in the virtual environment first):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -c "from src.independent_validation_001_audit import verify_protected; print(verify_protected())"
```

Expected: 136 passing tests and 921 protected files verified, plus frozen dataset
hash checks. These commands perform no new model inference or training.
A fresh Git clone lacks the ignored dataset, checkpoints, run files and rendered
visuals; full artifact tests require restoring them. Read
[reproducibility and artifact policy](docs/REPRODUCIBILITY.md) before rebuilding.
Historical scripts contain guarded training/test commands; they are not the next
step and should not be rerun on this frozen checkout.

## V0.2: reusable inference and local API

V0.2 adds `Detector.predict(image)` and a FastAPI adapter using the same frozen
model, pre-NMS class thresholds, and counting implementation. Upload a JPEG/PNG
and receive all five counts, pixel boxes, confidence scores, and an optional
annotated image. The model loads once at startup and its SHA-256 is checked.

On the existing checkout with its local checkpoint restored:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs for the upload form, or use `POST /predict`
with multipart field `file`. `GET /health` returns `{"status":"ok"}`.
See [setup, Python usage and HTTP examples](docs/INFERENCE_PIPELINE.md) and
[v0.2 implementation and verification](reports/V0_2_RESULTS.md).

This remains a local demonstration with a provisional five-class model;
independent-scene generalization remains unverified. The scan-and-review workflow
is now available in v0.3 below.

## V0.3: shopkeeper scan and review

StoreRoom is an **AI-assisted retail shelf inventory** project:

- **v0.1:** reproducible CV model pipeline.
- **v0.2:** reusable inference API.
- **v0.3:** photo upload → review → count correction → confirmation.
- **v0.4:** durable local scan history.
- **v0.5:** scan evidence and original prediction history.
- **v0.6:** local backup and restore of confirmed history and evidence.
- **v0.7:** frozen independent field-validation workflow; real cohort collection pending.
- **v0.8:** source-class catalog, confirmed inventory bridge and customer search prototype.
- **v0.9:** explicit product alternatives, transient preferences and freshness-aware discovery.

## V0.9: product alternatives

The customer page now shows explicitly related products when the selected product
has no recent positive count. Unknown metadata cannot pass restrictive preference
filters. The only opt-in demo relationships are Valser Classic ↔ Valser Still;
other products honestly return no alternatives. No ingredients or dietary claims
were invented, and demo relationships do not imply equivalent products.

```powershell
.\.venv\Scripts\python.exe -m src.catalog_cli seed-alternatives-demo
```

Use the existing server and `/customer`. See the [V0.9 guide](docs/V0_9_ALTERNATIVES.md)
for matching rules, API examples and schema-1/2/3 backup compatibility, and the
[verification report](reports/V0_9_RESULTS.md) for test evidence.
Next: a basic order-request flow with shopkeeper availability confirmation.

### Existing shopkeeper workflow

Run the same backend command above, then open [StoreRoom](http://127.0.0.1:8000/).
The mobile-friendly interface previews the photo, shows annotated detections,
keeps **AI detected** counts separate from editable **Your count** values, and
returns a confirmed review. Missed products from the five supported classes can
be added manually. No frontend build or separate server is required.

Confirmation describes visible packages in this photo only. V0.3 introduced temporary
reviews; v0.4 now saves confirmed counts locally. Hidden stock remains unknown.
See the [workflow and setup guide](docs/V0_3_SHOPKEEPER_WORKFLOW.md) and
[v0.3 results](reports/V0_3_RESULTS.md).

## V0.4: durable scan history

Confirmed scans now survive refresh and restart. Open **Scan History**, refresh the
recent list, or open a previous scan to see predicted and confirmed counts.
Historical reviews are read-only and never added together as shop inventory.

SQLite + SQLAlchemy store each scan and its items in one transaction. On startup,
the app creates the schema at `data/storeroom.db` (ignored by Git). Set
`STOREROOM_DB_PATH` before starting the same backend to use another local path.
No separate database server or frontend build is needed.

V0.4 introduced timestamps and counts without photos; v0.5 adds evidence below.
This is local persistence, not production infrastructure. Keep the database file to retain history;
there is no automated backup, multi-shop support, or inventory synchronization.
See [database setup and API contracts](docs/V0_4_SCAN_HISTORY.md) and
[v0.4 results](reports/V0_4_RESULTS.md).

## V0.5: scan evidence and prediction history

Historical scans now show the **original uploaded photo**, original AI detections,
annotated prediction and shopkeeper-confirmed counts. **AI prediction ≠ confirmed
inventory**: correcting 8 to 7 leaves the stored prediction and its eight boxes intact.
Corrections are visibly labelled; an unchanged count is not proof of model accuracy.

The server links confirmation to a `prediction_id` returned by `/predict`, checks
original counts against its own evidence, and stores detections in relational rows.
Photos live under `data/scans/<scan_id>/`, configurable with `SCAN_STORAGE_DIR`.
SQLite stores managed relative references rather than image blobs. Keep both the
database and image tree; older count-only scans remain readable after migration.

No historical scans are automatically deleted. Abandoned drafts also consume local
storage; deletion/retention management is not implemented. Retained corrections are
potential future evidence, **not automatically used for training**.
See [evidence setup, contracts and cleanup limits](docs/V0_5_SCAN_EVIDENCE.md) and
[v0.5 results](reports/V0_5_RESULTS.md).

## V0.6: local backup and restore

Create a portable ZIP containing SQLite, referenced original/annotated photos and
a manifest with SHA-256 checksums. Backups briefly block confirmation writes;
restore requires the backend to be stopped and validates everything before replacing
the data pair. Previous data is retained for rollback. No database schema change.

```powershell
.\.venv\Scripts\python.exe -m src.data_cli backup --output ./backups
.\.venv\Scripts\python.exe -m src.data_cli validate ./backups/<backup-filename>.zip
# Stop the backend first; restore replaces all configured history and photos.
.\.venv\Scripts\python.exe -m src.data_cli restore ./backups/<backup-filename>.zip
```

Use the printed archive filename in place of `<backup-filename>`. This is **local
backup**, not cloud backup. Pending reviews, temporary annotations, model weights
and datasets are excluded. The original AI prediction and confirmed counts remain
separate after restore. See [commands, safety and recovery](docs/V0_6_BACKUP_RESTORE.md)
and [v0.6 results](reports/V0_6_RESULTS.md).

## V0.7: independent field validation

The evaluation-only workflow freezes consented field photos, human count labels,
scene groups and model/configuration hashes before running the unchanged detector.
It reports count MAE, exact counts, over/under-counts and per-class/per-scene results.
There is **no real field cohort yet**, so no field performance or generalization
claim is made. Synthetic unit fixtures are never reported as field evidence.

```powershell
.\.venv\Scripts\python.exe -m src.field_cli init
# Collect new consented images and complete collection.json / ground_truth.json first.
.\.venv\Scripts\python.exe -m src.field_cli validate
```

Read the [collection, blind annotation, freeze and evaluation instructions](docs/V0_7_FIELD_VALIDATION.md)
and [v0.7 status report](reports/V0_7_FIELD_VALIDATION_RESULTS.md). No thresholds,
NMS, resolution, checkpoint or prior experiments changed. Next milestone: collect
and independently annotate the first real field cohort, then run this frozen protocol.

## V0.8: product catalog and inventory

New confirmations update the demo shop's latest **reviewed visible count** per
product while preserving original AI evidence. Stable catalog IDs are separate
from quantities; package sizes remain unverified/null. This is not total shop
stock, sales-adjusted stock or guaranteed availability.

Run the existing backend, then open [customer search](http://127.0.0.1:8000/customer).
Search by product/brand and select a product to see its quantity, last-confirmed
time and fresh/stale status. The default freshness window is one hour, configured
by `INVENTORY_FRESHNESS_SECONDS`. To demonstrate quantities without a new scan:

```powershell
.\.venv\Scripts\python.exe -m src.catalog_cli seed-demo
```

The optional seed uses clearly labelled example quantities and never overwrites
confirmed data. Startup seeds metadata only. New APIs: `GET /products/search?q=`,
`GET /inventory` and `GET /inventory/{product_id}` with shop/availability filters.
An additive schema-2 migration and updated backup reader preserve previous history
and support schema-1 backups. The frozen v0.7 workflow is unchanged.

See [catalog, quantity semantics, API and demo setup](docs/V0_8_PRODUCT_CATALOG_INVENTORY.md)
and [v0.8 verification](reports/V0_8_RESULTS.md). Next: a supervised single-shop
pilot; real independent field validation remains pending before broader ML claims.

The remaining sections document the earlier data/runtime milestones. Their rebuild
commands are historical, not instructions to reopen model experimentation.

## Earlier runtime milestone (historical)

**Runtime result:** Python 3.14.4 works with the installed CPU PyTorch stack.
Supervision converted eight representative images with all 76 target boxes
preserved. Visual review passed; official `yolo11n.pt` ran inference on two images.
At that historical milestone, training and augmentation had not yet run. See [RUNTIME_CHECK.md](reports/RUNTIME_CHECK.md)
for versions, exact reproduction commands, coordinate conventions, and limitations.

On this existing checkout, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The runtime milestone had 17 tests; the current suite has 136. To regenerate only the smoke export and visual checks:

```powershell
.\.venv\Scripts\python.exe -m src.convert_smoke
.\.venv\Scripts\python.exe -m src.preview_yolo
```

Expected conversion summary: 8 images, 76 boxes, per-class counts
`[32, 9, 10, 16, 9]`. Inspect `reports/visuals/yolo_smoke_contact.jpg`.
`configs/yolo_smoke.yaml` describes this small diagnostic subset.
The full export and first baseline described above now supersede the earlier
pending-export state. Smoke regeneration does not modify the frozen full YAML.

## Rebuild the original preflight on Windows / PowerShell

These commands are for rebuilding the data audit, not for continuing the completed
runtime check. Run them from the `StoreRoom` folder. Explicitly using the environment's
Python avoids PowerShell activation-policy problems.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\scripts\check_environment.ps1
& .\scripts\download_holoselecta.ps1
.\.venv\Scripts\python.exe -m src.extract_data
.\.venv\Scripts\python.exe -m src.preflight
.\.venv\Scripts\python.exe -m src.audit_machine_codes
.\.venv\Scripts\python.exe -m src.scene_preflight
.\.venv\Scripts\python.exe -m src.preview_candidates
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The downloader obtains the original 2.12 GB detection ZIP and the dataset's small
readme PDF. Allow about 5 GB free for the archive, extracted images, and inspection
outputs. It resumes interrupted downloads and verifies the publisher's SHA-256;
do not rename a `.part` download yourself. Extraction verifies the checksum again,
rejects paths outside the destination, and skips bundled Python/pickle files.

`requirements.txt` contains only Pillow and zxing-cpp. The audit reads XML with
Python's standard library, inspects images with Pillow, and decodes photographed
machine stickers with zxing-cpp to group repeat visits. No decoded links are opened.
It does not implement a VOC-to-YOLO converter. The smoke conversion now uses
Supervision; official Ultralytics training with `yolo11n.pt` remains a later step.

Expected outputs:

- `reports/environment.json`: Python, packages, Git, graphics hardware, and disk.
- `reports/download_manifest.json`: source URLs, license, sizes, verified hashes.
- `reports/dataset_summary.json`: actual pairs, classes, boxes, and missing files.
- `reports/class_counts.csv`: all-XML versus usable-pair class counts and GTIN checks.
- `reports/image_manifest.json`: source labels/boxes, dates, dimensions, image hashes.
- `reports/annotation_issues.json`: concrete issues without modifying raw labels.
- `reports/near_duplicate_candidates.json`: dHash distance <= 8 candidate pairs.
- `reports/visuals/all_*.jpg`: numbered contact sheets for scene review.
- `reports/scene_groups.json`: decoded sticker evidence and reviewed adjacent views.
- `reports/quarantine.json`: 102 excluded image files and the reasons.
- `reports/class_scene_counts.csv`: usable image/instance/group counts for all labels.
- `reports/split_preflight.json`: per-class support and counting variation per split.
- `configs/class_map.json`, `configs/splits.json`: five class IDs and frozen image assignments.

Hashes find exact duplicates and suggest some near duplicates. They cannot prove
that two photos show different machines. Scene review and an explicit grouped
coverage check are required before selecting a training split.

Those checks are complete for this archive. `scene_review.json` records the manual
review and its manifest hash; changing the manifest requires reviewing the grouping
again. Generated assignments include all relevant input hashes, and the tests reject
stale assignments. The split search uses annotation coverage and image balance only;
it has never seen model scores. Runtime packages and COCO weights are installed;
the first baseline has since been fine-tuned using these unchanged assignments.

On the existing checkout, the quick verification command is:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The original seven preflight checks are included in the expanded 36-test suite.
Do not rerun full downloads simply to inspect the result.

## Annotation format

Pascal VOC provides one XML file per image, containing image width/height and an
`object` entry for each labeled product instance. Each object has a product label
and pixel coordinates `xmin, ymin, xmax, ymax` for its bounding box. The source
labels often include a product name, pack size and GTIN separated by underscores.
Keep GTINs as strings so leading zeros survive. Do not assume a class name is a
clean catalog record or that every number is a valid identifier.

The YOLO export uses one text row per instance:

```text
class_id x_center/image_width y_center/image_height box_width/image_width box_height/image_height
```

Those four coordinates are normalized to the image; `class_id` is the fixed model
mapping 0-4. Supervision imports VOC coordinates by subtracting 1 from all four
endpoints, then exports normalized coordinates with five decimal places. An
independent checker verifies the decoded boxes within 0.1 pixels. Counting these
annotations describes labeled front packages; baseline prediction counts and
metrics are now recorded in the experiment reports linked above.

See [V0_1_SCOPE.md](V0_1_SCOPE.md), [REUSE_AUDIT.md](REUSE_AUDIT.md), and
[data/README.md](data/README.md) for scope, reuse decisions, and attribution.
