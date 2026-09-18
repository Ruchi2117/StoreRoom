# v0.1 results: five-class shelf detection and counting

v0.1 successfully demonstrates a reproducible product detection/counting pipeline
on the selected HoloSelecta validation set, but independent-scene generalization
remains unverified. The experimentation phase is closed; no new ML run is part of
the repository milestone.

## Dataset and scope

HoloSelecta V1 (CC BY 4.0), frozen export `holoselecta-five-v0.1`.
Five source classes: Red Bull, Knoppers, Valser Classic, Valser Still and Capri-Sun
Multivitamin; IDs 0-4 are fixed by [class_map.json](../configs/class_map.json).
175 images / 1,480 target boxes: 123 training, 26 validation, 26 test, in respectively
23, 5 and 5 verified machine groups. Correlated captures stay together.

The source contains 277 paired images and 295 XML files. 102 images are quarantined
for unresolved scene identity or annotation/content issues. Labels primarily describe
visible front packages in vending machines, not total stock or verified catalog SKUs.
Red Bull pack sizes are merged. This is not evidence of Indian shop generalization.
See [preflight](PREFLIGHT_REPORT.md) and [label review](LABEL_REVIEW.md).

## Experiment sequence

| Experiment | Change / selected result | Precision | Recall | Count MAE | Exact vectors |
| --- | --- | ---: | ---: | ---: | ---: |
| [BASELINE_001](BASELINE_001_RESULTS.md) | 10 epochs, no augmentation | 0.697* | 0.533* | 0.992 | 2/26 |
| [BASELINE_002](BASELINE_002_RESULTS.md) | 30 epochs, no augmentation | 0.772* | 0.795* | 0.646 | 6/26 |
| [NMS_001](NMS_001_RESULTS.md) | NMS 0.70 -> 0.50 | 0.825 | 0.780 | 0.577 | 6/26 |
| [RESOLUTION_001](RESOLUTION_001_RESULTS.md) | 640 rejected; retain 320 | 0.825 | 0.780 | 0.577 | 6/26 |
| [CONFIDENCE_001](CONFIDENCE_001_RESULTS.md) | Global 0.15 rejected; retain 0.25 | 0.825 | 0.780 | 0.577 | 6/26 |
| [CLASS_CONFIDENCE_001](CLASS_CONFIDENCE_001_RESULTS.md) | Red Bull 0.15 / others 0.25 | 0.807 | 0.815 | 0.554 | 6/26 |
| [AUGMENTATION_001](AUGMENTATION_001_RESULTS.md) | Moderate augmentation, 30 epochs | 0.791 | 0.888 | 0.423 | 11/26 |
| [INDEPENDENT_VALIDATION_001](INDEPENDENT_VALIDATION_001_RESULTS.md) | Stopped: no eligible independent groups | N/E | N/E | N/E | N/E |

*Baseline P/R are standard Ultralytics validation operating-point metrics. Later
rows use custom micro-averaged fixed-cutoff matching at IoU >=0.50; these P/R
columns must not be interpreted as one identical evaluation protocol. Baseline
mAP50/mAP50-95 were 0.668/0.423 and 0.838/0.552 respectively. Counting always uses
absolute image/class errors and exact five-class vectors; the always-zero MAE is
1.577. N/E means not evaluated, not zero performance.

## Current validation-best configuration

- Augmented YOLO11n: `runs/augmentation_001/weights/best.pt` (best epoch 30).
- Same original pretrained initialization; CPU, seed 42, 30 epochs, 320px, batch 4,
  AdamW learning rate 0.001. Exact controls: [augmentation_001.yaml](../configs/augmentation_001.yaml).
- Augmentation: hsv_s=0.10, hsv_v=0.15, translate=0.03, scale=0.10, degrees=3;
  flips, hue, mosaic, mixing, shear and perspective remain disabled.
- Inference: CPU, 320px, class-aware NMS IoU 0.50; Red Bull cutoff 0.15,
  other classes 0.25. Apply cutoffs to original best-class scores **before NMS**.
- Relative to the preceding configuration: MAE 0.554 -> 0.423 (23.6% reduction),
  exact vectors 6 -> 11, duplicates 2 -> 0, under-count items 35 -> 15.
  Twelve images improved, ten were unchanged, four worsened.

This is a **provisional v0.1 model**, not independently validated or production-ready.
Both Valser classes worsened; over-counted items rose 37 -> 40, and false positives
40 -> 48. Red Bull variant confusion persists. Correct aggregate counts can hide
incorrect localization or identity. Zero duplicate candidates does not imply perfect
boxes. Full class/scene failure analysis remains in the detailed report.

## Independent validation and protected test set

All 33 verified groups are already assigned to training, validation or protected
test. The 102 quarantined images cannot be claimed independent. The independent
audit stopped before inference; no favorable scenes or replacement split were invented.

**Independent-scene generalization has not yet been verified because no eligible
independent scene groups remain in the current dataset.** The test set was not used
for model selection/tuning. Historically, BASELINE_001 had one explicitly frozen
final test evaluation; all subsequent model experiments left it untouched. No test
inference was performed during independent validation or this closure milestone.

## Next phase

Move from experiment scripts to a reusable image-to-detections/counts component,
then a thin upload API. Reuse existing class-score gating and counting; keep the
source-class/visible-item limitations in the output contract. Do not add a frontend
or deployment infrastructure yet. Independent-scene evaluation requires separately
collected, annotated and frozen data; it remains outstanding rather than silently
reusing the test set.

See [reproducibility](../docs/REPRODUCIBILITY.md) for hashes, runtime, artifact
restoration requirements and limitations of a fresh clone.
