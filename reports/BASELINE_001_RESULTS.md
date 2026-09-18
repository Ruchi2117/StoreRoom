# First five-class CPU baseline

Full export: 175/175 images passed, 1,480 source/YOLO boxes preserved; split 123/26/26.
Three empty-label images preserved. No class, split, or machine-group changes.
Maximum coordinate reconstruction error: 0.034400 pixels.

Dataset version: `holoselecta-five-v0.1`.
Manifest SHA-256: `878424031a9ab66bb64a89ac4dfbb5bebc889d67ef5e295d5e3ee494edae5513`.
Manifest: [dataset_v01_manifest.json](dataset_v01_manifest.json).

## Fixed training configuration

Official yolo11n.pt pretrained weights; 10 epochs, imgsz=320, batch=4, CPU, workers=0, seed=42.
Optimizer AdamW, lr0=0.001, lrf=0.01, momentum/beta1=0.9, weight decay=0.0005, warmup=1.0 epoch.
Nominal batch size nbs=64: gradient accumulation reaches 16 batches after warmup.
No augmentation, AMP, or hyperparameter search. Deterministic execution requested; reproducibility is scoped to this recorded environment.
End-to-end training call duration: **455.53 seconds (7.59 minutes)**, including setup and final built-in validation.
Checkpoint: `C:\Users\Lenovo\Documents\ChatGPT\StoreRoom\runs\baseline_001\weights\best.pt`.
Checkpoint SHA-256: `028251faf221362ac14d09f6e9150966678270b32d8b71b9152e9e1897850b3a`.
Checkpoint selected by Ultralytics validation fitness only. Raw losses, metrics and actual LR traces are in `runs/baseline_001/results.csv`; effective arguments are in `runs/baseline_001/args.yaml` and the experiment JSON.

## Validation: development

Precision **0.697250**, recall **0.532644**, mAP50 **0.667646**, mAP50-95 **0.422553**.
These P/R values use Ultralytics' F1 operating point. AP uses confidence floor 0.001; they are separate from counting at confidence 0.25. NMS IoU is 0.70, class-aware, max_det=300.

| Class | Instances | Precision | Recall | AP50 | AP50-95 | Count MAE | Zero MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Red Bull | 84 | 0.666074 | 0.738095 | 0.682588 | 0.418753 | 1.692308 | 3.230769 |
| Knoppers | 38 | 0.796311 | 0.823176 | 0.885262 | 0.458221 | 0.500000 | 1.461538 |
| Valser Classic | 19 | 0.704632 | 0.252488 | 0.535664 | 0.418236 | 0.692308 | 0.730769 |
| Valser Still | 31 | 0.512219 | 0.516129 | 0.511280 | 0.351250 | 0.884615 | 1.192308 |
| Capri-Sun Multivitamin | 33 | 0.807014 | 0.333333 | 0.723435 | 0.466305 | 1.192308 | 1.269231 |

Overall counting MAE (mean across N x 5 cells): **0.992308**; zero baseline **1.576923**.
Exact five-class count accuracy: **0.076923**; zero baseline **0.076923**.
Total-item-count MAE: 4.192308. Mean sum of absolute class errors per image: 4.961538.

Over-count examples (true -> predicted; class order 0 through 4):
- `DSC01659.png`: [2, 3, 0, 0, 2] -> [5, 4, 0, 0, 0]
- `DSC01658.png`: [0, 3, 1, 1, 2] -> [3, 3, 0, 0, 0]
- `IMG_20181218_171607.jpg`: [5, 0, 1, 1, 2] -> [7, 0, 1, 2, 0]

Under-count examples:
- `IMG_20181218_165652.jpg`: [6, 0, 2, 4, 0] -> [0, 0, 0, 0, 0]
- `IMG_20181218_165646.jpg`: [5, 0, 2, 4, 0] -> [1, 0, 0, 1, 0]
- `IMG_20190206_170714.jpg`: [5, 0, 0, 4, 0] -> [0, 0, 0, 0, 0]

## Test: final frozen baseline evaluation

Precision **0.732195**, recall **0.561802**, mAP50 **0.648399**, mAP50-95 **0.401825**.
These P/R values use Ultralytics' F1 operating point. AP uses confidence floor 0.001; they are separate from counting at confidence 0.25. NMS IoU is 0.70, class-aware, max_det=300.

| Class | Instances | Precision | Recall | AP50 | AP50-95 | Count MAE | Zero MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Red Bull | 86 | 0.587658 | 0.720930 | 0.626888 | 0.383300 | 1.576923 | 3.307692 |
| Knoppers | 38 | 0.786886 | 0.894737 | 0.896434 | 0.493539 | 0.269231 | 1.461538 |
| Valser Classic | 25 | 0.913065 | 0.420983 | 0.538805 | 0.382515 | 0.961538 | 0.961538 |
| Valser Still | 33 | 0.515491 | 0.454545 | 0.459674 | 0.290117 | 1.000000 | 1.269231 |
| Capri-Sun Multivitamin | 38 | 0.857875 | 0.317812 | 0.720195 | 0.459653 | 1.346154 | 1.461538 |

Overall counting MAE (mean across N x 5 cells): **1.030769**; zero baseline **1.692308**.
Exact five-class count accuracy: **0.115385**; zero baseline **0.038462**.
Total-item-count MAE: 3.538462. Mean sum of absolute class errors per image: 5.153846.

Over-count examples (true -> predicted; class order 0 through 4):
- `IMG_20181218_172440.jpg`: [3, 1, 1, 1, 2] -> [6, 1, 0, 2, 0]
- `IMG_20190206_170619.jpg`: [4, 1, 1, 1, 2] -> [6, 1, 0, 2, 1]
- `DSC01644.png`: [3, 3, 1, 1, 2] -> [5, 3, 0, 1, 0]

Under-count examples:
- `DSC01639.png`: [6, 0, 2, 4, 0] -> [0, 0, 0, 0, 0]
- `DSC01641.png`: [6, 0, 2, 4, 0] -> [0, 0, 0, 0, 0]
- `DSC01642.png`: [6, 0, 2, 4, 0] -> [0, 0, 0, 0, 0]

## Interpretation

See [BASELINE_001_REVIEW.md](BASELINE_001_REVIEW.md) for visual findings, limitations, test decision, and the next measured experiment. These results do not establish production readiness.
