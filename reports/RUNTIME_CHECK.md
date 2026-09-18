# CPU runtime and conversion smoke check

Historical milestone: the full export and first training experiment are now
complete. See [BASELINE_001_RESULTS.md](BASELINE_001_RESULTS.md). The statements
below describe the earlier runtime-only verification.

Completed without training or augmentation. The class map and the full
123/26/26 grouped split were preserved byte-for-byte. Only eight representative
images were converted (2 train, 3 validation, 3 test); full export remains pending.

## Runtime

| Component | Verified version |
| --- | --- |
| Python | 3.14.4, Windows AMD64 |
| OS | Windows-11-10.0.26200-SP0 |
| PyTorch | 2.14.0+cpu |
| Torchvision | 0.29.0+cpu |
| Ultralytics | 8.4.154 |
| Supervision | 0.30.3 |
| opencv-python | 5.0.0.93 (`cv2.__version__`: 5.0.0) |
| NumPy | 2.5.2 |
| Pillow | 12.3.0 |
| PyYAML | 6.0.3 |

`torch.cuda.is_available()` is False; `torch.version.cuda` is None. Imports, a
CPU tensor operation, dataset conversion, and two CPU inference calls passed.
`pip check` found no broken requirements. No Python downgrade or system-Python
change was needed. Transitive packages came from these libraries' dependencies;
the NVIDIA management binding required by Ultralytics is not a CUDA runtime.
All installed versions are in `requirements-lock.txt` and `runtime_smoke.json`.
The complete suite passed **17 tests**, including the original seven preflight
checks. No tests were skipped.

## Reproduce from the StoreRoom folder

Use the existing environment. Do not recreate it or rerun the data preflight.

```powershell
# For rebuilding the environment later: install CPU wheels from the official index first.
.\.venv\Scripts\python.exe -m pip install -r requirements-cpu.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check

# Small conversion, independent checks and contact sheet; never trains.
.\.venv\Scripts\python.exe -m src.convert_smoke
.\.venv\Scripts\python.exe -m src.preview_yolo

# Optional repeat of the two-image CPU inference check; never trains.
.\.venv\Scripts\python.exe -m src.runtime_smoke
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`requirements-runtime.txt` pins the requested top-level libraries plus the
preflight dependencies. The lock file additionally pins transitive dependencies
for this Windows/Python 3.14 environment. These commands are not a cross-platform
lock or a promise that future wheel downloads will remain available.

## Conversion evidence

`src/convert_smoke.py` stages original images/XML, imports them with
`sv.DetectionDataset.from_pascal_voc`, filters and remaps `Detections.class_id`,
then calls `dataset.as_yolo`. No custom label exporter was written. Images are
copied byte-for-byte instead of recompressed. Supervision itself writes explicit
empty labels for the two zero-target images.

| ID | Source product class | Source boxes | Exported boxes |
| --- | --- | ---: | ---: |
| 0 | Red Bull | 32 | 32 |
| 1 | Knoppers | 9 | 9 |
| 2 | Valser Classic | 10 | 10 |
| 3 | Valser Still | 16 | 16 |
| 4 | Capri-Sun Multivitamin | 9 | 9 |
| | Total | 76 | 76 |

The checker independently reads original XML and reconstructs YOLO pixel boxes.
It checks dimensions, IDs, per-class counts, coordinates, pairing, and image byte
hashes. Worst coordinate error was **0.032 pixels**, below the 0.1-pixel limit.

Two initial validation failures exposed assumptions in the checker:

1. Supervision converts VOC's 1-based endpoints by subtracting 1 from **all four**
   coordinates. The checker initially compared against unshifted XML. All selected
   retained source boxes have minimum coordinates >= 1. We now explicitly check
   the library's convention: `(xmin-1, ymin-1, xmax-1, ymax-1)`, preserving
   `xmax-xmin` widths without adding an inclusive pixel. Source XML is unchanged.
2. YOLO output uses five decimal places. A box touching the image edge can
   reconstruct a corner at -0.000005 even though every serialized value is in
   [0,1]. The checker allows only the derived 0.0000075 corner-rounding bound;
   serialized coordinates still must be strictly in [0,1], with positive area.
   No clipping or broad error tolerance was introduced.

Both behaviors are covered by regression checks. Invalid IDs, NaN/infinite or
out-of-range values, zero/negative areas, missing pairs, changed mapping/counts,
and displaced coordinates fail validation. Detailed per-image evidence is in
`conversion_smoke.json`.

## Visual review

Inspected `visuals/yolo_smoke_contact.jpg` covering all eight comparisons, plus
the crowded `IMG_20181218_175259` and mixed-size `IMG_20181218_165652` examples at
larger size. Left: original VOC boxes in the explicit zero-based convention.
Right: decoded YOLO boxes. Class colors, counts and placement match; no visible
conversion drift or class swapping was found. All five classes have multiple
instances in the crowded example. Both source-negative images remain unboxed.

This is a conversion review, not certification of every source annotation.
Regular Red Bull cans of different sizes remain one class; labels primarily cover
front packages rather than hidden stock. The example containing the unselected
C+Swiss label with missing GTIN preserves target filtering without inventing a
product identity. Reflections, occlusion, and these vending-machine scenes remain
limitations for transfer to Indian shops.

## YAML and model

`configs/yolo_smoke.yaml` points to the actual eight-image export. Its memberships
are inherited from `configs/splits.json`; no image was reassigned.
`configs/yolo_v01.yaml` reserves the full dataset paths with the same five IDs.
**The full YAML is not training-ready: its 175-image export does not exist yet.**
Paths are local absolute paths; rerunning conversion regenerates them for a new
checkout location. Frozen full memberships remain in `configs/splits.json`.

Official `yolo11n.pt` was downloaded from the
[Ultralytics release asset](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt).
SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.
It ran on CPU, `imgsz=640`, on two train-subset images. Programmatic output
contained 3 and 12 COCO detections respectively, with boxes, confidence, class
IDs, names, and original dimensions. These are runtime outputs, **not our product
counts or an accuracy result**. Full output is in `runtime_smoke.json`.

The first invocation used a workspace-local fallback for Ultralytics settings
because its requested parent directory did not exist. The script now creates the
directory first; local settings and model weights are ignored by Git.

Dataset: [HoloSelecta v1](https://data.mendeley.com/datasets/gz39ggf35n/1),
DOI `10.17632/gz39ggf35n.1`, CC BY 4.0. Previously verified archive SHA-256:
`4492e5f544a035cf4884626187ebf39ab5e703f71a3ff05733b6c11baf926afb`.
The exact source-label/ID mapping and frozen configuration hashes are recorded
in the runtime and conversion JSON reports.

## Next gate

Export all 175 retained images with this verified Supervision path, using the
unchanged 123/26/26 assignments. Run the same checks on every exported image,
confirm per-class totals against the frozen preflight, and inspect the full
export's remaining edge cases. Only then choose and review a CPU-sized first
training configuration (batch size, resolution, epochs and seed). No training
loop, optimizer/backward pass, training-memory requirement, or model accuracy
has been tested by this milestone.
