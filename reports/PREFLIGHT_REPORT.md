# HoloSelecta v0.1 data preflight

Completed 2026-09-17. **Data-support gate passed for a limited five-class public-data
baseline. No training, model download, or YOLO conversion has run.**

The requested project folders are present. Reproduction commands and annotation
format explanations are in [README.md](../README.md). The future product roadmap
has not been expanded.

## Environment

| Check | Actual result |
|---|---|
| Python | CPython 3.14.4, isolated `.venv` |
| pip / venv | pip 26.0.1; both work |
| Git | 2.54.0.windows.1 |
| GPU | Intel UHD Graphics; no NVIDIA GPU detected |
| CUDA tools | Neither `nvidia-smi` nor `nvcc` found |
| System RAM | Approximately 8 GB |
| Installed audit dependencies | Pillow 12.3.0, zxing-cpp 3.1.1 |
| Training dependencies | PyTorch, Ultralytics, Supervision not installed |

This verifies the audit runtime only. Python/PyTorch compatibility and the training
compute choice still need their own check before installing the training stack.
See [environment.json](environment.json) for the machine-readable snapshot.

## Original data and integrity

Downloaded the detection archive and readme PDF from
[HoloSelecta V1, Mendeley Data](https://data.mendeley.com/datasets/gz39ggf35n/1),
DOI `10.17632/gz39ggf35n.1`, licensed CC BY 4.0. Attribution is in
[data/README.md](../data/README.md). No user-study files were downloaded.

The 2,122,992,435-byte ZIP matches the publisher's SHA-256:

```text
4492e5f544a035cf4884626187ebf39ab5e703f71a3ff05733b6c11baf926afb
```

Source images/XMLs remain unchanged. Extraction skipped the bundled Python and
pickle files without executing or deserializing them. The readme PDF was also
checksum-verified. See [download_manifest.json](download_manifest.json).

| Measurement | Actual downloaded data |
|---|---:|
| XML files | 295 |
| Image files / valid stem pairs | 277 |
| Orphan XMLs, with no matching image | 18 |
| Boxes across all XMLs | 10,036 |
| Boxes with an image available | 9,486 |
| Literal product label strings | 115 |
| Distinct extractable GTIN strings | 59 |
| Exact file / decoded-pixel duplicate groups | 0 / 0 |
| Approximate dHash candidate pairs | 30 |

The published 295 images, 10,035 instances and 109 classes do not exactly describe
this archive. Do not replace measured counts with the publication figures. See
[dataset_summary.json](dataset_summary.json), [class_counts.csv](class_counts.csv),
and [LABEL_REVIEW.md](LABEL_REVIEW.md).

## Annotation findings and quarantine

No nonpositive, nonfinite, tiny-under-five-pixel, out-of-XML-bounds, or exact
duplicate annotation boxes were found by the implemented checks. That does not
certify semantic correctness or exhaustive labeling.

- Eighteen `DSC...` XMLs lack their source images and never enter the paired manifest.
- One image, `20190125_114246.jpg`, decodes as 1959x4031 while its XML says
  1960x4032. It is quarantined; boxes were not silently resized.
- Three images show product icons on a vending-machine screen rather than actual
  packages: `IMG_20190306_104622.jpg`, `IMG_20190430_111230.jpg`, and
  `IMG_20190430_111456.jpg`. They are quarantined.
- Ninety-eight further images have unresolved cross-visit machine identity. They
  are quarantined from this benchmark rather than assigned independent groups.
- Some labels lack identifiers; five extracted identifier strings fail the GTIN
  checksum; eight IDs are shared by conflicting product/size/variant labels.
  No blanket alias merge or catalog enrichment was performed.

Total quarantine: **102 of 277 images**. This is exclusion from split metadata,
not deletion. All source files are preserved. Reasons are recorded per image in
[quarantine.json](quarantine.json).

## Scene independence and duplicate review

Different capture dates are not independent scenes. The audit decoded machine
stickers in 104 images, yielding **33 distinct sticker payloads**. Visual review of
all eight contact sheets links adjacent views of the same machine. Shared stickers
join repeat visits across dates; 19 supported groups span multiple filename dates.

For example, `IMG_20181218_165922.jpg`, `IMG_20190206_170606.jpg`, and
`IMG_20190430_105959.jpg` share a sticker and stay in one group. A random image or
date split could leak that machine into multiple sets.

The 30 approximate-hash pairs resolve to six within-machine pairs, sixteen pairs
of similar layouts with different readable machine stickers, and eight involving
quarantined images. Hash similarity alone was not used to invent machine identity.
See [scene_groups.json](scene_groups.json),
[near_duplicate_review.json](near_duplicate_review.json), and the explicit visual
review record [scene_review.json](../configs/scene_review.json).

These are evidence-backed **machine-group proxies**, not externally verified store
IDs. Similar equipment, assortments and planograms remain across machines. Results
will describe this vending-machine domain, not independent Indian shops.

## Five selected classes

Counts below describe the **175 eligible images**, not the entire archive.

| Model ID | Source product class | Positive images | Instances | Machine groups | Images with 2+ |
|---|---|---:|---:|---:|---:|
| 0 | Red Bull regular | 152 | 597 | 33 | 150 |
| 1 | Knoppers | 138 | 268 | 28 | 66 |
| 2 | Valser Classic | 133 | 150 | 32 | 17 |
| 3 | Valser Still | 117 | 165 | 32 | 19 |
| 4 | Capri-Sun Multivitamin | 151 | 300 | 29 | 147 |

All five have valid, non-colliding source GTIN strings and geometrically usable
boxes in the retained subset. That validates the source mapping, not manufacturer
catalog identity. The stable `hs_*` IDs are separate from YOLO IDs 0-4; see
[class_map.json](../configs/class_map.json).

M&M's was rejected because its retained examples all have count one. Valser Still
adds counting variation while preserving whole-image negatives. It also creates a
useful Classic-versus-Still confusion check. The alternatives and label-family
checks are documented in [LABEL_REVIEW.md](LABEL_REVIEW.md).

Source box/crop previews are in `reports/visuals/`; they are annotations, never
model predictions. Some exploratory previews include quarantined images and must
not be confused with the final split membership.

## Fixed split and support

| Split | Images | Machine groups | Images with no selected products |
|---|---:|---:|---:|
| Train | 123 | 23 | 0 |
| Validation | 26 | 5 | 2 |
| Test | 26 | 5 | 1 |

The assignment approximates 70/15/15 and keeps every included view of a machine in
one split. The seed-42 search used annotation support and size balance only;
no prediction or model metric influenced the assignment.

| Class | Train groups / instances | Val groups / instances | Test groups / instances |
|---|---:|---:|---:|
| Red Bull regular | 23 / 427 | 5 / 84 | 5 / 86 |
| Knoppers | 20 / 192 | 4 / 38 | 4 / 38 |
| Valser Classic | 22 / 106 | 5 / 19 | 5 / 25 |
| Valser Still | 22 / 101 | 5 / 31 | 5 / 33 |
| Capri-Sun Multivitamin | 21 / 229 | 4 / 33 | 4 / 38 |

Every class has at least one multi-item image in **every** split. The explicit
minimum was three train / two validation / two test groups per class, at least
20/10/10 instances, and multi-item support in each split. These are pragmatic
prototype gates, not statistical guarantees. Input hashes bind the assignments to
the source manifest, QR evidence, review, exclusions, class selection and policy.

Full image lists: [splits.json](../configs/splits.json). Full distributions and
per-class count histograms: [split_preflight.json](split_preflight.json).
All 115 labels' retained scene support: [class_scene_counts.csv](class_scene_counts.csv).

## What this benchmark can and cannot establish

The original labels primarily describe front packages. Visible fragments of rear
items may lack boxes. Counts will therefore measure agreement with the source's
front-package annotations, not exhaustive visible stock. Reflections, missing
labels and occlusions remain error-analysis targets.

Pack size is not reliable: regular Red Bull includes 250 ml and 355 ml cans under
one source label. The selected classes must not be treated as exact catalog SKUs
for ingredients, prices, ordering, or size claims. Real product/SKU validation is
still required for the later catalog layer.

Only three whole-image negatives survive across two groups. There are none in
training; validation has two and test has one. Each target still has per-class
zero examples, but broad false-positive/unknown-product claims would be unsupported.
Add independent negative scenes before making such claims. Small count ranges,
repeated views and near-fixed planograms also limit generalization; compare future
count predictions against both zero and training-derived constant-count baselines.

The next authorized milestone would be a compatible training-runtime setup and a
small Supervision VOC-to-YOLO round-trip check, preserving the frozen class IDs,
selected boxes, and negative images. Confirm coordinates and drawn boxes before
bulk export. No custom converter or trainer is needed. **Training has not begun.**

## Verification

The automated checks cover GTIN string/checksum handling, invalid boxes, extraction
path containment, transitive scene grouping, rejection of many repeated images as
independent scenes, stale-success invalidation, and real split leakage/coverage.
The full local suite passes seven tests; `pip check` reports no broken requirements.
No learned-model accuracy or speed has been measured.
