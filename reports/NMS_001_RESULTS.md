# NMS_001: controlled fixed-confidence post-processing experiment

**Result:** NMS IoU 0.50 improves counting on these validation images without losing any previously matched annotated target. The evidence supports a post-processing cause for most observed duplicate candidates; substantial non-duplicate errors remain.

## Exact experimental setup

Frozen BASELINE_002 checkpoint: `C:\Users\Lenovo\Documents\ChatGPT\StoreRoom\runs\baseline_002\weights\best.pt`.
Checkpoint SHA-256: `7e048d48a3b80cf5cab1aafb30dfb63f7f20c94e12b26ded8aac35de5ecd0cbd`.
Dataset manifest SHA-256: `878424031a9ab66bb64a89ac4dfbb5bebc889d67ef5e295d5e3ee494edae5513`.
Same 26 validation images, five classes, CPU, image size 320, one image per prediction call, rectangular preprocessing, confidence 0.25, class-aware NMS, max_det=300, no augmentation. Run A uses NMS IoU 0.70; Run B uses 0.50. Each run loaded the identical frozen weights and performed fresh inference on all validation images.
No training, weight changes, threshold sweep, dataset changes or test evaluation occurred. Run A reproduces BASELINE_002 validation detections, confidence scores and boxes within the recorded numerical tolerance (1e-3 pixels and 1e-6 confidence).
Inference-run durations, including loading and diagnostics: A 13.217s; B 9.576s. These sequential timings are not a controlled speed benchmark.
Setup and outputs: [setup JSON](nms_001_setup.json), [Run A](nms_001_a.json), [Run B](nms_001_b.json), [image comparison JSON](nms_001_comparison.json).

## Metric definitions and AP decision

Detection P/R below are **custom micro-averaged fixed-threshold metrics**, not standard Ultralytics validation P/R at its F1-optimal operating point. Predictions are matched in confidence order, same class, one-to-one, at evaluation IoU >= 0.50. Evaluation matching IoU and NMS IoU are separate concepts. Per-class P/R use the same matching rule.
A duplicate candidate is an unmatched prediction overlapping an already-matched same-class ground-truth box at IoU >= 0.50. Wrong-class candidates overlap a different selected class at that threshold. These are annotation-based diagnostic categories; images were also inspected.
**mAP50 and mAP50-95: not reported.** Full-curve AP is not directly comparable to the earlier confidence-floor-0.001 validation after deliberately discarding predictions below 0.25. Computing confidence-truncated AP is possible but is unnecessary for this fixed-operating-point counting decision. No standard Ultralytics `model.val()` call or lower-confidence pass was made in this experiment.
Counting MAE averages absolute errors over 26 x 5 image/class cells. Exact count accuracy requires the entire five-class vector to match. Over-count items sum positive image/class count errors; under-count items sum their negative magnitudes. These count errors can differ from FP/FN because mistakes can cancel within a class count.

## Overall results

| Metric | A: IoU 0.70 | B: IoU 0.50 | B - A |
| --- | ---: | ---: | ---: |
| Fixed-threshold micro precision | 0.788177 | 0.824742 | +0.036565 |
| Fixed-threshold micro recall | 0.780488 | 0.780488 | +0.000000 |
| True positives | 160.000000 | 160.000000 | +0.000000 |
| False positives | 43.000000 | 34.000000 | -9.000000 |
| False negatives | 45.000000 | 45.000000 | +0.000000 |
| Overall counting MAE | 0.646154 | 0.576923 | -0.069231 |
| Total-item counting MAE | 2.076923 | 1.961538 | -0.115385 |
| Exact five-class count accuracy | 0.230769 | 0.230769 | +0.000000 |
| Total predicted instances | 203.000000 | 194.000000 | -9.000000 |
| Duplicate candidates | 9.000000 | 1.000000 | -8.000000 |
| Over-count items | 41.000000 | 32.000000 | -9.000000 |
| Under-count items | 43.000000 | 43.000000 | +0.000000 |
| Images with any over-count | 17.000000 | 17.000000 | +0.000000 |
| Images with any under-count | 11.000000 | 11.000000 | +0.000000 |

Always-zero MAE remains **1.576923 (1.577 rounded)**. Exact vectors remain **6/26** for both runs; the always-zero baseline is 2/26.
Cell MAE improves by about 10.7%. Six images improve, none worsen, and twenty retain the same count error. Nineteen images have identical raw predictions.

## Per-class detection and counting

| Class | Precision A -> B | Recall A -> B | Count MAE A -> B | Predicted A -> B | Over-count items A -> B | Under-count items A -> B |
| --- | --- | --- | --- | --- | --- | --- |
| Red Bull | 0.783784 -> 0.805556 | 0.690476 -> 0.690476 | 1.538462 -> 1.461538 | 74 -> 72 | 15 -> 13 | 25 -> 25 |
| Knoppers | 0.968750 -> 0.968750 | 0.815789 -> 0.815789 | 0.230769 -> 0.230769 | 32 -> 32 | 0 -> 0 | 6 -> 6 |
| Valser Classic | 0.625000 -> 0.681818 | 0.789474 -> 0.789474 | 0.500000 -> 0.423077 | 24 -> 22 | 9 -> 7 | 4 -> 4 |
| Valser Still | 0.821429 -> 0.884615 | 0.741935 -> 0.741935 | 0.500000 -> 0.423077 | 28 -> 26 | 5 -> 3 | 8 -> 8 |
| Capri-Sun Multivitamin | 0.733333 -> 0.785714 | 1.000000 -> 1.000000 | 0.461538 -> 0.346154 | 45 -> 42 | 12 -> 9 | 0 -> 0 |

Knoppers is unchanged. Red Bull, both Valser variants and Capri-Sun have less over-counting, with no per-class increase in under-counting.

## Duplicate and legitimate-neighbor analysis

Eight of nine duplicate candidates are eliminated. One additional localization/background false positive is removed. A tenth removed box is a true-positive box replaced by a different true-positive box for the same target; therefore net predictions decrease by nine, not ten.

For every image, the set of matched ground-truth indices is unchanged. No previously matched legitimate neighboring product becomes unmatched. This is supported by the same-class matching audit and inspected side-by-side images; it is evidence for these 26 images, not a guarantee for all dense shelves.

The non-monotonic case is `IMG_20190430_111949.jpg`: Run B removes an A true-positive Red Bull box and admits another Red Bull box matching the same ground-truth item. Counts and recall stay unchanged. Greedy NMS at a lower threshold can alter a suppression chain, so B need not be a strict subset of A.

| Requested case | Observed result |
| --- | --- |
| Correct duplicate removal | Five images lose duplicate candidates without losing any GT match. In IMG_20181218_170247.jpg, Classic/Still predictions fall from 4/3 to 2/2 against truth 1/1; three duplicates are removed, but extra wrong-class/localization errors remain. |
| Incorrect suppression of legitimate neighboring products | None observed: no image loses a GT match, and under-count errors do not increase. The box-replacement case above was checked rather than counted as a lost neighbor. |
| No meaningful effect | Nineteen images have identical predictions; DSC01658.png still predicts three regular Red Bulls when the selected regular class count is zero. IMG_20181218_165652.jpg still misses all twelve targets and predicts one false Capri-Sun. |
| Changed wrong-class detection | No selected-class confusion candidate was removed or added. Retained boxes are not relabeled by class-aware NMS. Valser Classic/Still and regular/light mistakes remain. |
| Correct count becomes incorrect | None observed, either for the entire five-class vector or for an individual image/class count that was correct in A. |

Changed images (vectors use Red Bull / Knoppers / Classic / Still / Capri-Sun):

| Image | Truth | A | B | Sum absolute count error A -> B |
| --- | --- | --- | --- | --- |
| DSC01657.png | [2, 3, 1, 1, 2] | [5, 3, 1, 1, 2] | [4, 3, 1, 1, 2] | 3 -> 2 |
| IMG_20181218_170247.jpg | [4, 0, 1, 1, 0] | [0, 0, 4, 3, 0] | [0, 0, 2, 2, 0] | 9 -> 6 |
| IMG_20181218_171755.jpg | [5, 3, 1, 1, 2] | [6, 1, 1, 1, 4] | [5, 1, 1, 1, 3] | 5 -> 3 |
| IMG_20181218_171805.jpg | [0, 3, 0, 0, 2] | [0, 3, 0, 0, 4] | [0, 3, 0, 0, 3] | 2 -> 1 |
| IMG_20190206_170716.jpg | [5, 0, 0, 4, 0] | [3, 0, 2, 5, 1] | [3, 0, 2, 4, 1] | 6 -> 5 |
| IMG_20190206_174852.jpg | [3, 1, 1, 1, 2] | [4, 1, 1, 1, 3] | [4, 1, 1, 1, 2] | 2 -> 1 |
| IMG_20190430_111949.jpg | [3, 1, 0, 1, 2] | [4, 1, 1, 1, 3] | [4, 1, 1, 1, 3] | 3 -> 3 |

### Crowded and multi-instance subsets

| Subset | Images | Cell MAE A -> B | Exact-vector accuracy A -> B |
| --- | ---: | --- | --- |
| crowded_30plus_source_objects | 14 | 0.457143 -> 0.400000 | 0.142857 -> 0.142857 |
| multi_instance_2plus | 24 | 0.700000 -> 0.625000 | 0.166667 -> 0.166667 |

Crowded means at least 30 original source-annotated objects, including non-target classes. Multi-instance means at least two items of any selected class. These definitions match the previous comparison.
Selected-class confusion candidates: 8 -> 8; Classic/Still candidates: 4 -> 4; regular predictions overlapping source Red Bull light: 6 -> 6.
Regular Red Bull pack sizes are merged in the source labels, so size discrimination cannot be evaluated separately.

## Inspected image comparisons

Ground truth / Run A / Run B panels were inspected for duplicate removal, persistent identity errors and the TP replacement.
- [nms_001_page_1](visuals/nms_001_page_1.jpg)
- [nms_001_page_2](visuals/nms_001_page_2.jpg)

## Decision and next experiment

**Prefer 0.50 as the validation-supported NMS setting for further development.** This decision is based on fewer duplicates and over-counted items, lower counting MAE, unchanged matched-target recall, no lost legitimate-neighbor matches and no count regressions—not mAP. BASELINE_002 artifacts and its saved settings remain unchanged.
The removal of eight of nine duplicate candidates supports that most measured duplicates are sensitive to post-processing. However, only nine net false positives disappear; 34 false positives and 45 missed annotated instances remain. Exact count accuracy stays at 6/26. Stronger suppression did not solve recognition or missed-product errors.
**Single next experiment, proposed only:** compare inference image size 320 versus 640 using the same frozen BASELINE_002 weights, confidence 0.25 and NMS IoU 0.50, on validation only. The unchanged Red Bull variant mistakes, water-class confusions and 45 misses justify testing whether more image detail improves these errors. Keep all other settings fixed; measure per-class recall, counting MAE, identity confusions, duplicates and CPU latency. This is a resolution hypothesis, not a claim that resolution will fix the errors. No retraining, additional model, threshold sweep or test evaluation is part of this proposal.
The conclusion is limited to 26 validation images across five machine groups; it does not establish production reliability.

## Verification and reproduction

All 72 protected BASELINE_001/002 and shared frozen artifacts retain their hashes. The existing suite plus NMS-specific tests passed 30 tests. Raw predictions and matching decisions are retained for every image. No BASELINE_002 artifact was modified.
```powershell
.\.venv\Scripts\python.exe -m src.nms_experiment
.\.venv\Scripts\python.exe -m src.analyze_nms
.\.venv\Scripts\python.exe -m src.report_nms
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The inference command refuses to overwrite NMS_001. Analysis and reporting regenerate only NMS_001 outputs. The preservation snapshot and hashes are in `nms_001_preservation.json`; test output is in `nms_001_tests.log`.
