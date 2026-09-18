# StoreRoom

v0.1: detect and count **visible instances of five known products** in one shelf
image. This checkout contains a **frozen dataset and a first trained CPU baseline**.
Product recommendations and marketplace features remain in
[ROADMAP.md](ROADMAP.md).

**Preflight result:** 175 usable images across 33 sticker-supported machine groups;
123 train / 26 validation / 26 test images. Selected classes: Red Bull, Knoppers,
Valser Classic, Valser Still, and Capri-Sun Multivitamin. Read
[PREFLIGHT_REPORT.md](reports/PREFLIGHT_REPORT.md) before interpreting the counts:
the labels primarily describe front packages, and do not establish exact pack sizes.

**Baseline result:** all 175 images and 1,480 boxes were exported and validated.
`yolo11n.pt` completed 10 CPU epochs at 320 pixels in 7.59 minutes. Standalone
validation mAP50 is 0.667646; counting MAE is 0.992308 items per image/class.
After freezing the checkpoint and thresholds, one final test evaluation gave
mAP50 0.648399 and counting MAE 1.030769. Counting still misses many products.
Read [measured results](reports/BASELINE_001_RESULTS.md) and
[failure review / next experiment](reports/BASELINE_001_REVIEW.md).

The immutable dataset manifest is [dataset_v01_manifest.json](reports/dataset_v01_manifest.json).
The full YAML is [yolo_v01.yaml](configs/yolo_v01.yaml). Model weights live at
`runs/baseline_001/weights/best.pt`; dataset files and weights are excluded from Git.
Configuration, protocol, raw metric snapshots, and JSON reports are retained.

On the completed checkout, verify without retraining or reopening the test set:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -c "from src.train_baseline import verify_dataset; print(verify_dataset())"
```

Expect 23 passing tests and manifest SHA-256
`878424031a9ab66bb64a89ac4dfbb5bebc889d67ef5e295d5e3ee494edae5513`.

Commands used for this completed milestone (export/training/evaluation refuse to
overwrite the frozen version or repeat an already-recorded experiment):

```powershell
.\.venv\Scripts\python.exe -m src.convert_smoke --full
.\.venv\Scripts\python.exe -m src.train_baseline
.\.venv\Scripts\python.exe -m src.evaluate_baseline --split val
.\.venv\Scripts\python.exe -m src.review_baseline
# This checks the fixed validation gate and freezes the checkpoint BEFORE test inference.
.\.venv\Scripts\python.exe -m src.evaluate_baseline --split test
.\.venv\Scripts\python.exe -m src.report_baseline
```

Training settings are in `configs/baseline_001.yaml`; the experiment protocol
defines confidence 0.25, NMS IoU 0.70, counting metrics, and the test gate. AP uses
a 0.001 confidence floor. The next recommended experiment is documented, not run.

## Earlier runtime milestone (historical)

**Runtime result:** Python 3.14.4 works with the installed CPU PyTorch stack.
Supervision converted eight representative images with all 76 target boxes
preserved. Visual review passed; official `yolo11n.pt` ran inference on two images.
No training or augmentation has run. See [RUNTIME_CHECK.md](reports/RUNTIME_CHECK.md)
for versions, exact reproduction commands, coordinate conventions, and limitations.

On this existing checkout, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The runtime milestone had 17 tests; the current suite has 23. To regenerate only the smoke export and visual checks:

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

The original seven preflight checks are included in the expanded 23-test suite.
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
