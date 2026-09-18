# BASELINE_002: controlled training-budget comparison

Validation-only development experiment. BASELINE_001 artifacts remain unchanged. No test evaluation was run for BASELINE_002.

## Exact configuration

The configuration diff is exactly `epochs: 10 -> 30`. A fresh model was initialized from the same official `yolo11n.pt`, not from BASELINE_001's checkpoint.
Frozen dataset manifest SHA-256: `878424031a9ab66bb64a89ac4dfbb5bebc889d67ef5e295d5e3ee494edae5513`.
Same 175 images, 123/26/26 machine-group split and five classes. No labels, files or assignments changed.

CPU; imgsz=320; batch=4; workers=0; seed=42; deterministic=True; optimizer=AdamW.
lr0=0.001; lrf=0.01; momentum/beta1=0.9; weight_decay=0.0005; warmup_epochs=1.0; warmup_bias_lr=0.001; patience=20; nbs=64.
All augmentation disabled, AMP=False, cache=False, no threshold tuning. Counting confidence=0.25, class-aware NMS IoU=0.70, max_det=300. AP confidence floor=0.001.
Python 3.14.4; PyTorch 2.14.0+cpu; Ultralytics 8.4.154; PyTorch CPU threads=7.
Actual settings: [experiment JSON](baseline_002_experiment.json); requested settings: [YAML](../configs/baseline_002.yaml).

## Training duration and learning curve

Completed **30 epochs**. Training call duration **1747.68 seconds (29.13 minutes)**, including setup and built-in final validation.
Highest recorded training-time validation mAP50-95: epoch 23 (0.549420). The evaluated checkpoint is Ultralytics best.pt, selected only from validation fitness, as in BASELINE_001.
Checkpoint: `C:\Users\Lenovo\Documents\ChatGPT\StoreRoom\runs\baseline_002\weights\best.pt`. SHA-256: `7e048d48a3b80cf5cab1aafb30dfb63f7f20c94e12b26ded8aac35de5ecd0cbd`.
Raw metrics and actual LR traces: [CSV](baseline_002_learning_curve.csv). No metric values were manually edited or smoothed.

![Validation learning curves and classification losses](visuals/baseline_002_learning_curve.png)

The epoch-relative LR schedule retains its parameters but stretches over 30 epochs. Thus this measures the larger training budget with the same scheduling policy; it is not 20 additional epochs appended to the old LR trajectory. Training-time validation uses batch 8; standalone evaluation below uses batch 4 consistently for both experiments.

| Epoch | Precision | Recall | mAP50 | mAP50-95 |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 5 | 0.876030 | 0.233080 | 0.378650 | 0.202470 |
| 10 | 0.734020 | 0.750650 | 0.796350 | 0.483220 |
| 15 | 0.777830 | 0.759460 | 0.804020 | 0.520070 |
| 20 | 0.786200 | 0.790000 | 0.828090 | 0.540960 |
| 23 | 0.781070 | 0.775110 | 0.833720 | 0.549420 |
| 25 | 0.765690 | 0.797490 | 0.826360 | 0.537740 |
| 30 | 0.785220 | 0.774060 | 0.827370 | 0.536550 |

## Final standalone validation comparison

P/R in this table use Ultralytics' F1 operating point. Counting uses the unchanged fixed confidence threshold. No metric or threshold is selected from the test set.

| Metric | BASELINE_001 | BASELINE_002 | Change (002 - 001) |
| --- | ---: | ---: | ---: |
| metrics/precision(B) | 0.697250 | 0.772149 | +0.074899 |
| metrics/recall(B) | 0.532644 | 0.795039 | +0.262394 |
| metrics/mAP50(B) | 0.667646 | 0.837706 | +0.170060 |
| metrics/mAP50-95(B) | 0.422553 | 0.551673 | +0.129120 |
| overall_cell_mae | 0.992308 | 0.646154 | -0.346154 |
| total_count_mae | 4.192308 | 2.076923 | -2.115385 |
| mean_sum_absolute_class_errors | 4.961538 | 3.230769 | -1.730769 |
| exact_five_class_accuracy | 0.076923 | 0.230769 | +0.153846 |

Always-zero counting MAE: **1.576923** for both. Always-zero exact-vector accuracy: **0.076923**.
Overall cell MAE averages absolute errors over 26 images x 5 classes. Mean sum absolute class errors is five times cell MAE; total-count MAE can hide swaps between classes. Exact accuracy requires all five counts to match.

## Per-class validation changes

| Class | Instances | P 001 -> 002 | R 001 -> 002 | AP50 001 -> 002 | AP50-95 001 -> 002 | Count MAE 001 -> 002 | Zero MAE |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: |
| Red Bull | 84 | 0.666074 -> 0.772326 | 0.738095 -> 0.690476 | 0.682588 -> 0.786425 | 0.418753 -> 0.491308 | 1.692308 -> 1.538462 | 3.230769 |
| Knoppers | 38 | 0.796311 -> 1.000000 | 0.823176 -> 0.802377 | 0.885262 -> 0.993095 | 0.458221 -> 0.556552 | 0.500000 -> 0.230769 | 1.461538 |
| Valser Classic | 19 | 0.704632 -> 0.568665 | 0.252488 -> 0.789474 | 0.535664 -> 0.745439 | 0.418236 -> 0.548618 | 0.692308 -> 0.500000 | 0.730769 |
| Valser Still | 31 | 0.512219 -> 0.781578 | 0.516129 -> 0.692866 | 0.511280 -> 0.737389 | 0.351250 -> 0.516946 | 0.884615 -> 0.500000 | 1.192308 |
| Capri-Sun Multivitamin | 33 | 0.807014 -> 0.738175 | 0.333333 -> 1.000000 | 0.723435 -> 0.926183 | 0.466305 -> 0.644940 | 1.192308 -> 0.461538 | 1.269231 |

## Fixed-threshold error analysis

Diagnostic TP/FP/FN use identical confidence-ordered, same-class, one-to-one matching at IoU >= 0.5. Candidate duplicate/confusion counts are diagnostic labels, not an exhaustive visual ground truth.

| Class | TP 001 -> 002 | FP 001 -> 002 | Misses 001 -> 002 |
| --- | --- | --- | --- |
| Red Bull | 44 -> 58 | 18 -> 16 | 40 -> 26 |
| Knoppers | 26 -> 31 | 1 -> 1 | 12 -> 7 |
| Valser Classic | 1 -> 15 | 0 -> 9 | 18 -> 4 |
| Valser Still | 9 -> 23 | 1 -> 5 | 22 -> 8 |
| Capri-Sun Multivitamin | 2 -> 33 | 0 -> 12 | 31 -> 0 |

Image-level summed class error: 18 improved, 4 worsened, 4 unchanged.
Positive images with zero predictions: 4 -> 0.
Exact positive-image count vectors: 0 -> 4 (out of 24 positive validation images).
Valser Classic/Still confusion candidates: 1 -> 4.
Duplicate candidates: 1 -> 9.
Regular Red Bull predictions overlapping source Red Bull light at IoU >= 0.5: 8 -> 6.
Red Bull size accuracy cannot be measured: the selected regular class merges sizes. Regular/light overlap can be measured using the original excluded-class labels, without relabeling training data.

### Representative image comparisons

Count vectors use Red Bull / Knoppers / Valser Classic / Valser Still / Capri-Sun order.

| Image | Truth | 001 | 002 | Sum absolute error change |
| --- | --- | --- | --- | ---: |
| DSC01658.png | [0, 3, 1, 1, 2] | [3, 3, 0, 0, 0] | [3, 3, 1, 1, 2] | -4 |
| DSC01659.png | [2, 3, 0, 0, 2] | [5, 4, 0, 0, 0] | [4, 1, 1, 0, 2] | -1 |
| IMG_20181218_165652.jpg | [6, 0, 2, 4, 0] | [0, 0, 0, 0, 0] | [0, 0, 0, 0, 1] | +1 |
| IMG_20181218_170247.jpg | [4, 0, 1, 1, 0] | [0, 0, 0, 1, 0] | [0, 0, 4, 3, 0] | +4 |
| IMG_20181218_171607.jpg | [5, 0, 1, 1, 2] | [7, 0, 1, 2, 0] | [5, 0, 1, 1, 2] | -5 |
| IMG_20181218_171749.jpg | [5, 3, 1, 1, 2] | [5, 1, 0, 0, 0] | [5, 2, 1, 1, 2] | -5 |
| IMG_20190206_170714.jpg | [5, 0, 0, 4, 0] | [0, 0, 0, 0, 0] | [2, 0, 2, 3, 0] | -3 |
| IMG_20190206_170716.jpg | [5, 0, 0, 4, 0] | [3, 0, 0, 1, 0] | [3, 0, 2, 5, 1] | +1 |

All 26 paired count vectors and diagnostic summaries are in [comparison JSON](baseline_002_comparison.json).

Visual comparisons (ground truth / 001 / 002):
- [baseline_002_comparison_page_1](visuals/baseline_002_comparison_page_1.jpg)
- [baseline_002_comparison_page_2](visuals/baseline_002_comparison_page_2.jpg)
- [baseline_002_comparison_page_3](visuals/baseline_002_comparison_page_3.jpg)

### Crowded and multi-instance subsets

Definitions were fixed before final evaluation: crowded means at least 30 source-annotated objects including non-target classes; multi-instance means at least two instances of any selected class.

| Validation subset | Images | Cell MAE 001 -> 002 | Exact-vector accuracy 001 -> 002 |
| --- | ---: | --- | --- |
| crowded_30plus_source_objects | 14 | 1.028571 -> 0.457143 | 0.000000 -> 0.142857 |
| multi_instance_any_class_2plus | 24 | 1.075000 -> 0.700000 | 0.000000 -> 0.166667 |

## Interpretation and the next experiment

The following interpretation is based on validation evidence and inspected image comparisons.

### Was the ten-epoch baseline undertrained?

Yes, relative to this optimizer and scheduling policy: the larger budget improved
validation detection and counting, including every class's AP50, AP50-95 and
counting MAE. Overall cell counting MAE fell by about 35%, and four positive
validation images now have exactly correct five-class counts; BASELINE_001 had
none. The training curves show gains beyond epoch 10, with the highest recorded
validation fitness at epoch 23. Epochs 24–30 did not establish a higher peak.

This supports insufficient optimization budget as one bottleneck in BASELINE_001.
It does not establish that duration is the only bottleneck or that further epochs
will keep helping. The epoch-dependent learning-rate schedule was stretched by
the requested budget change, so the effect includes that scheduling consequence.
The first epoch reproduced the previous losses, and the effective settings differ
only in epochs and the experiment/output-directory names.

### What improved, and what did not?

The side-by-side review covered original failure images, crowded shelves,
multi-instance examples, and the largest image-level improvements and regressions.
Left panels are ground truth, middle panels BASELINE_001, right panels BASELINE_002.

- **Capri-Sun:** all 33 annotated validation instances were matched at confidence
  0.25 and diagnostic IoU 0.5, versus only two previously. There are now 12 false
  predictions, including three duplicate candidates. Recall improved strongly,
  while count bias changed from under-counting to over-counting.
- **Valser variants:** correct matches increased from 1 to 15 for Classic and
  from 9 to 23 for Still. However, Classic/Still confusion candidates increased
  from one to four. More training improved aggregate coverage without solving
  variant discrimination. The old `IMG_20181218_171607.jpg` confusion is fixed:
  its entire count vector is now correct. Other frames contain new wrong-class
  or overlapping water-bottle predictions.
- **Red Bull:** regular predictions overlapping excluded light-product annotations
  decreased from eight to six. This confusion persists. Regular Red Bull counting
  error remains the largest of the five classes. Its crowded-subset MAE actually
  worsened from 1.143 to 1.286, despite a small improvement over all validation
  images. Size accuracy remains unmeasurable because the source class merges sizes.
- **Crowded/multi-instance images:** crowded-image cell MAE improved from 1.029
  to 0.457 across 14 images. Across all 24 multi-instance images, cell MAE improved
  from 1.075 to 0.700. `IMG_20181218_171749.jpg` improves from six total predicted
  products to eleven, against twelve annotated products, recovering both water
  variants and Capri-Sun while still missing one Knoppers.
- **Duplicate predictions:** candidates increased from one to nine. They span
  Red Bull, both Valser classes and Capri-Sun. At `IMG_20181218_170247.jpg`, true
  `[4,0,1,1,0]` becomes `[0,0,4,3,0]`; extra overlapping water boxes accompany
  persistent Red Bull misses. More training alone did not produce better counts
  on this image.
- **Zero-output images:** positive images with no predictions decrease from four
  to zero, but this is not equivalent to finding the correct products. The hard
  mixed-size-can image `IMG_20181218_165652.jpg` still misses all twelve targets
  and adds a false Capri-Sun detection: `[0,0,0,0,0]` becomes `[0,0,0,0,1]`.
  Its count error worsens. Both actual zero-target images remain correctly empty.

Overall, 18 image-level count errors improved, four worsened and four stayed the
same. Detection is substantially better, and counting also improves, but exact
five-class accuracy is still only 6/26. More training reduced misses while exposing
additional duplicate and classification errors. These remain exploratory results
from 26 images across five validation machine groups and one random seed.

### The single most justified next experiment

Run one **validation-only NMS comparison using the frozen BASELINE_002 checkpoint**:
change class-aware NMS IoU from **0.70 to 0.50**, keeping confidence **0.25**, image
size **320**, the model weights, class mapping and all other inference settings
fixed. This is a proposed separate experiment; it has not been run here.

The evidence is specific: nine duplicate candidates remain, and eight overlap
another same-class prediction at IoUs between approximately 0.51 and 0.66, below
the current suppression threshold. Compare duplicate count, per-class counting
MAE, exact-vector accuracy, and crowded-scene recall against the stored 0.70
results. The hypothesis is that stronger duplicate suppression helps counts;
the tradeoff is possible suppression of genuine adjacent products. An IoU change
does not guarantee that all eight candidates disappear, and it does not address
cross-class or regular/light mistakes. This small comparison isolates a measured
failure mode without another training run or a new model technique.

### Reproducibility and verification

All 30 epochs completed in 1747.68 seconds (29 minutes 8 seconds). The same original
pretrained weights and frozen dataset were used. All 34 recorded BASELINE_001 and
shared frozen artifacts retained their original hashes. The raw training CSV was
copied byte-for-byte, and no reported metrics were edited. The full test suite
passed 27 tests, including configuration equality, effective settings, dataset
integrity, counting checks, preservation checks, and explicit rejection of a
BASELINE_002 test-evaluation request.

Commands used for this new experiment:

```powershell
.\.venv\Scripts\python.exe -m src.train_baseline_002
.\.venv\Scripts\python.exe -m src.evaluate_baseline_002 --split val
.\.venv\Scripts\python.exe -m src.review_baseline_002
.\.venv\Scripts\python.exe -m src.compare_baselines
.\.venv\Scripts\python.exe -m src.report_baseline_002
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Training and evaluation refuse to overwrite their completed experiment. The
review/comparison/report commands regenerate only BASELINE_002 analysis outputs.

BASELINE_002 has no test results. BASELINE_001's frozen test evaluation was neither modified nor used for tuning this experiment.
