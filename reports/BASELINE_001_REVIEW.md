# Baseline interpretation and next experiment

The baseline learns useful detections but does not yet provide reliable inventory
counts. The full results, including per-class detection/counting metrics and
individual over/under-count examples, are in
[BASELINE_001_RESULTS.md](BASELINE_001_RESULTS.md).

## Dataset and experiment integrity

All 175 retained images passed independent source-to-YOLO checks; 1,480 boxes
were preserved. The 123/26/26 split, 33 machine groups, five class IDs, and raw
annotations did not change. The manifest contains image, source-XML and exported
label SHA-256 hashes, dimensions, group membership and per-class counts.
Re-export refuses to overwrite the immutable v0.1 version. There was no
augmentation, threshold search, extra dataset, or second training run.

Training used Python 3.14.4, PyTorch 2.14.0+cpu, Ultralytics 8.4.154 and an Intel
Core i5-10210U CPU with 7 PyTorch threads. The training call took 455.53 seconds;
the epoch CSV records 427.617 seconds through epoch 10. The difference includes
initialization and the built-in final validation. Exact effective settings and
checkpoint hashes are in `baseline_001_experiment.json`. A byte-for-byte copy of
the training CSV is retained as `baseline_001_learning_curve.csv`.

The final training-log validation mAP50 is 0.68509. The separate, consistently
configured evaluation reports 0.667646. These are distinct measurements: the
trainer uses validation batch 8 (twice training batch 4), whereas the standalone
evaluation uses batch 4. Rectangular validation padding can depend on batch
composition. Both raw results are retained; the results table consistently uses
the standalone evaluation, not the larger number. No metric was manually edited.

## Counting at the frozen confidence 0.25

Validation counting MAE is 0.992308 per image/class versus 1.576923 for always
zero. Exact five-class accuracy is only 2/26, equal to always zero. Both exact
images are zero-target images; no positive validation image has a completely
correct five-class count vector.

Diagnostic one-to-one matching at IoU >= 0.5 gives the following operating-point
counts. This is a simple confidence-ordered diagnostic matcher; it is separate
from Ultralytics AP integration and its reported F1-point P/R.

| Class | True positives | False positives | Missed instances |
| --- | ---: | ---: | ---: |
| Red Bull | 44 | 18 | 40 |
| Knoppers | 26 | 1 | 12 |
| Valser Classic | 1 | 0 | 18 |
| Valser Still | 9 | 1 | 22 |
| Capri-Sun Multivitamin | 2 | 0 | 31 |

Classic and Capri-Sun counting barely outperform always zero. Higher AP than
fixed-threshold recall suggests that some useful detections remain below the
chosen confidence threshold; no threshold was changed to improve this run.

## Visual and annotation-backed failure cases

Inspected the validation comparison sheet and the Classic/Still example at larger
size. See [comparison sheet](visuals/baseline_001_validation.jpg). Left panels show
source ground truth; right panels show predictions at confidence 0.25.

- **Missed whole shelf section:** `IMG_20181218_165652.jpg` contains counts
  `[6,0,2,4,0]`, but the model predicts all zero. Different-size regular Red Bull
  cans are visible here. This demonstrates missed products, not a measurable size
  classifier failure: sizes are merged in the source class.
- **Duplicate/partial detections:** `DSC01659.png` predicts five Red Bulls where
  only two selected regular Red Bulls are annotated. One duplicate candidate
  overlaps an already-matched regular can at IoU >= 0.5; other false positives
  require distinguishing lookalike non-target products.
- **Non-target variants:** eight false predictions overlap source boxes labeled
  `redbull_light__33__90162800` at IoU >= 0.5. This is a concrete regular-versus-light
  confusion, not a reason to silently merge classes. Another false prediction
  overlaps an Oreo source box. Raw label evidence is retained in
  `baseline_001_failure_analysis.json`.
- **Classic versus Still:** `IMG_20181218_171607.jpg` has an extra Still detection
  overlapping a Classic box at IoU about 0.831. The image also shows partial or
  overlapping Red Bull predictions. Class-aware NMS does not remove boxes merely
  because another class covers the same product.
- **Crowded scenes:** the reviewed DSC01658/DSC01659 shelves combine small packets,
  reflections and adjacent lookalike cans. The model detects Knoppers more often
  than Capri-Sun and water variants. Visual review supports these failure patterns
  but does not certify every source label or explain every miss causally.

Machine-readable diagnostics contain 20 unmatched validation predictions: one
duplicate candidate, one class-confusion candidate, and 18 localization/background
candidates. These categories depend on the stated matching rule; excluded-source
overlap evidence refines the background candidates rather than replacing labels.

## Test decision and result

The predeclared gate required nonzero validation mAP50 and counting MAE better
than always zero. It passed. That qualifies this as a useful **scientific baseline
to measure**, not an operational inventory system.

Before test inference, `baseline_001_frozen.json` recorded the checkpoint,
configuration, dataset and validation-report hashes, fixed confidence/NMS values,
and freeze time. One final evaluation was run: an AP pass at confidence floor
0.001 and a counting pass at confidence 0.25, both with the frozen checkpoint and
NMS IoU 0.70. No settings were selected or changed from test results. The evaluator
refuses another run even if only a partial test-start record exists.

Test mAP50 is 0.648399, mAP50-95 is 0.401825, counting MAE is 1.030769 versus
1.692308 for always zero, and exact counts are 3/26 versus 1/26 for always zero.
Validation and test each contain only five independent machine groups, so these
are small exploratory evaluations of vending-machine images, not evidence of
performance in Indian shops. The selected checkpoint and baseline remain frozen.

## Next recommended experiment — not run

Run a **30-epoch budget comparison at the same 320-pixel resolution**, starting
from the original official pretrained weights with the same split, seed, batch,
optimizer parameters, augmentation policy and counting threshold. Use a new
experiment ID; do not overwrite or resume into baseline_001.

This recommendation uses validation evidence only: mAP50 rose from 0.49260 at
epoch 6 to 0.68509 at epoch 10, classification losses were still decreasing, and
fixed-threshold misses dominate. A longer budget tests whether additional
optimization improves recall before introducing resolution or augmentation
changes. Retain the same epoch-relative LR schedule parameters; stretching the
schedule is part of this budget comparison. Compare on validation only, especially
Classic/Capri-Sun recall, count MAE and positive-image exact-count accuracy. Do not
use this already-opened baseline test set to select the next settings.

All 23 tests passed, including original preflight checks, all-image export checks,
counting edge cases, evaluation membership and the frozen-test binding. No claim
of production readiness is supported by this baseline.
