# RESOLUTION_001: frozen-model inference at 320 vs 640

**Decision: retain 320px for further development.** At fixed confidence 0.25 and NMS IoU 0.50, 640px worsened counting MAE, precision, recall and exact counts on the same 26 validation images. This is a substantial regression, not a mixed aggregate result.

## 1. Experiment setup

Inference only. Both runs loaded the same frozen BASELINE_002 checkpoint from the completed 30-epoch training run. No retraining or test-set evaluation occurred. Only the requested inference image size changed: A=320, B=640.
Checkpoint: `C:\Users\Lenovo\Documents\ChatGPT\StoreRoom\runs\baseline_002\weights\best.pt`.
Checkpoint SHA-256: `7e048d48a3b80cf5cab1aafb30dfb63f7f20c94e12b26ded8aac35de5ecd0cbd`.
Dataset manifest SHA-256: `878424031a9ab66bb64a89ac4dfbb5bebc889d67ef5e295d5e3ee494edae5513`.
Same frozen 123/26/26 dataset split; only the 26 validation images were inferred on. Five-class mapping is unchanged: Red Bull, Knoppers, Valser Classic, Valser Still, Capri-Sun Multivitamin.
Common prediction arguments: `{"agnostic_nms": false, "augment": false, "batch": 1, "conf": 0.25, "device": "cpu", "iou": 0.5, "max_det": 300, "rect": true, "verbose": false}`.
Runtime: Ultralytics 8.4.154, PyTorch 2.14.0+cpu. Fresh model load for each run; identical single-image ordering. Same rectangular resize/letterbox preprocessing algorithm, with its target size set by imgsz. No cropping, augmentation, alternative model, threshold tuning or additional inference experiments.
Counting and matching directly import the unchanged NMS_001 functions: `count_classes`, `match_detections` and `summarize`. The 320px run reproduces NMS_001 Run B counts and raw predictions within 1e-3 pixels / 1e-6 confidence. Evaluation source hashes are recorded in the setup.
Precision/recall are **custom micro-averaged fixed-confidence metrics**, with confidence-ordered, same-class one-to-one matching at evaluation IoU >= 0.50. They are not standard Ultralytics validation metrics at an F1-selected threshold. No model.val() or AP pass was run.
Counting MAE averages absolute errors over 26 x 5 image/class cells. Exact accuracy requires all five counts correct. Over-counted and under-counted items are summed positive/negative image/class count errors; they are not FP/FN because errors can cancel within counts. Duplicate candidates use the unchanged annotation-overlap diagnostic from NMS_001, not every visually overlapping or partial box.
Elapsed run time including loading and diagnostics: 320=8.116s, 640=7.424s. Sequential runs without repeated timing or controlled warm-up are not a speed benchmark; no latency conclusion is drawn.
Artifacts: [setup](resolution_001_setup.json), [320 predictions](resolution_001_a.json), [640 predictions](resolution_001_b.json), [comparison](resolution_001_comparison.json).

## 2. Results

| Metric | 320 | 640 | 640 - 320 |
| --- | ---: | ---: | ---: |
| Precision | 0.824742 | 0.544944 | -0.279798 |
| Recall | 0.780488 | 0.473171 | -0.307317 |
| Counting MAE | 0.576923 | 1.115385 | +0.538462 |
| Exact five-class accuracy | 0.230769 | 0.038462 | -0.192308 |
| Total predicted instances | 194.000000 | 178.000000 | -16.000000 |
| Duplicate candidates | 1.000000 | 1.000000 | +0.000000 |
| Over-counted items | 32.000000 | 59.000000 | +27.000000 |
| Under-counted items | 43.000000 | 86.000000 | +43.000000 |
| TP | 160.000000 | 97.000000 | -63.000000 |
| FP | 34.000000 | 81.000000 | +47.000000 |
| FN | 45.000000 | 108.000000 | +63.000000 |
| Total-item count MAE | 1.961538 | 3.653846 | +1.692308 |
| Images with over-counts | 17.000000 | 21.000000 | +4.000000 |
| Images with under-counts | 11.000000 | 18.000000 | +7.000000 |

**Exact vectors: 6/26 (23.08%) at 320, 1/26 (3.85%) at 640.** Always-zero counting MAE remains **1.576923 (1.577 rounded)**, with 2/26 exact vectors. Both resolutions beat zero on MAE; 640 is worse than zero on exact-vector accuracy.
Relative to 320: **2 images improved / 3 unchanged / 21 worsened**, using the sum of five absolute class-count errors per image. Unchanged error does not imply unchanged predictions.

## 3. Counting and neighboring-product analysis

640 did not reduce under-counting (43 -> 86), over-counting (32 -> 59), or duplicates (1 -> 1). MAE rose by 93.3%. Five previously exact vectors became incorrect; no previously incorrect vector became exact. The sole remaining exact vector is a target-free image. All four previously exact target-containing images became incorrect.
Ground-truth identity matching lost 67 previously matched targets and gained 4, yielding 160 -> 97 true positives. These are changes in post-NMS outputs; this experiment cannot attribute individual losses to NMS versus confidence, localization or class changes.
Neighboring identical products regress visibly: IMG_20181218_171607.jpg loses all five regular Red Bulls and both Capri-Suns, while IMG_20181218_171805.jpg loses all three Knoppers and both Capri-Suns. At 640, some small partial boxes cluster around products without meeting the duplicate-candidate IoU criterion; unchanged duplicate counts do not establish equally good localization.
Correct-to-incorrect vectors: `IMG_20181218_165648.jpg`, `IMG_20181218_170243.jpg`, `IMG_20181218_171555.jpg`, `IMG_20181218_171604.jpg`, `IMG_20181218_171607.jpg`.

| Subset | Images | Counting MAE 320 | Counting MAE 640 | Exact accuracy 320 | Exact accuracy 640 |
| --- | ---: | ---: | ---: | ---: | ---: |
| crowded_30plus_source_objects | 14 | 0.400000 | 1.028571 | 0.142857 | 0.000000 |
| multi_instance_2plus | 24 | 0.625000 | 1.183333 | 0.166667 | 0.000000 |

Crowded means >=30 source-annotated objects including non-targets, as in NMS_001. Multi-instance means >=2 objects of at least one selected class; this is not a geometric adjacency metric.
Small-target diagnostic (descriptive, not a new evaluation rule): GT box area below 32x32 pixels after scaling the long image side to 320, fixed for both runs. Of 174 such targets, matched counts fall from 146 to 97 (recall 0.839080 -> 0.557471). This is a task-specific size grouping, not COCO AP-small. Increased inference resolution did not improve this subset.

## 4. Per-class analysis

| Class | MAE 320 -> 640 | Precision 320 -> 640 | Recall 320 -> 640 | Predicted 320 -> 640 | Over-count 320 -> 640 | Under-count 320 -> 640 |
| --- | --- | --- | --- | --- | --- | --- |
| Red Bull | 1.461538 -> 2.461538 | 0.805556 -> 0.529412 | 0.690476 -> 0.428571 | 72 -> 68 | 13 -> 24 | 25 -> 40 |
| Knoppers | 0.230769 -> 0.769231 | 0.968750 -> 1.000000 | 0.815789 -> 0.473684 | 32 -> 18 | 0 -> 0 | 6 -> 20 |
| Valser Classic | 0.423077 -> 0.653846 | 0.681818 -> 0.366667 | 0.789474 -> 0.578947 | 22 -> 30 | 7 -> 14 | 4 -> 3 |
| Valser Still | 0.423077 -> 0.884615 | 0.884615 -> 0.500000 | 0.741935 -> 0.322581 | 26 -> 20 | 3 -> 6 | 8 -> 17 |
| Capri-Sun Multivitamin | 0.346154 -> 0.807692 | 0.785714 -> 0.523810 | 1.000000 -> 0.666667 | 42 -> 42 | 9 -> 15 | 0 -> 6 |

- **Red Bull:** MAE worsens by 1.000; recall drops from 58/84 to 36/84. Regular predictions overlapping source-labeled light variants rise from 6 to 9. Source labels merge regular pack sizes, so separate size accuracy cannot be measured.
- **Knoppers:** precision rises to 1.000 because the remaining 18 predictions are correct, but 20/38 targets are missed. Higher precision does not compensate for worse counting.
- **Valser Classic / Still:** both MAEs worsen. Cross-variant candidates increase from 4 to 6. Classic under-count items fall slightly (4 -> 3), but over-counts double (7 -> 14); this is not an overall improvement.
- **Capri-Sun:** predicted total stays 42, yet MAE more than doubles and recall falls from 33/33 to 22/33. Equal aggregate totals hide new misses and false positives on different images.
All selected-class wrong-class candidates: 8 -> 9. Variant diagnostics use the same source-label overlap rule as NMS_001.

## 5. Image-level comparisons

Count vectors below use Red Bull / Knoppers / Valser Classic / Valser Still / Capri-Sun. Error is the sum of absolute errors across the five classes. Panels show ground truth, 320 and 640.
| Image | Truth | 320 counts | 640 counts | Error 320 -> 640 |
| --- | --- | --- | --- | --- |
| [DSC01657.png](visuals/resolution_001_DSC01657.jpg) | [2, 3, 1, 1, 2] | [4, 3, 1, 1, 2] | [5, 2, 2, 1, 3] | 2 -> 6 |
| [DSC01658.png](visuals/resolution_001_DSC01658.jpg) | [0, 3, 1, 1, 2] | [3, 3, 1, 1, 2] | [3, 3, 2, 1, 3] | 3 -> 5 |
| [DSC01659.png](visuals/resolution_001_DSC01659.jpg) | [2, 3, 0, 0, 2] | [4, 1, 1, 0, 2] | [6, 1, 0, 1, 1] | 5 -> 8 |
| [IMG_20181218_165646.jpg](visuals/resolution_001_IMG_20181218_165646.jpg) | [5, 0, 2, 4, 0] | [2, 0, 0, 2, 0] | [0, 0, 0, 1, 0] | 7 -> 10 |
| [IMG_20181218_165648.jpg](visuals/resolution_001_IMG_20181218_165648.jpg) | [0, 0, 0, 0, 0] | [0, 0, 0, 0, 0] | [2, 0, 0, 0, 1] | 0 -> 3 |
| [IMG_20181218_165652.jpg](visuals/resolution_001_IMG_20181218_165652.jpg) | [6, 0, 2, 4, 0] | [0, 0, 0, 0, 1] | [0, 0, 1, 0, 0] | 13 -> 11 |
| [IMG_20181218_165657.jpg](visuals/resolution_001_IMG_20181218_165657.jpg) | [0, 0, 0, 0, 0] | [0, 0, 0, 0, 0] | [0, 0, 0, 0, 0] | 0 -> 0 |
| [IMG_20181218_170238.jpg](visuals/resolution_001_IMG_20181218_170238.jpg) | [3, 3, 1, 1, 2] | [5, 3, 1, 1, 2] | [5, 3, 2, 1, 2] | 2 -> 3 |
| [IMG_20181218_170243.jpg](visuals/resolution_001_IMG_20181218_170243.jpg) | [0, 3, 0, 0, 2] | [0, 3, 0, 0, 2] | [1, 0, 0, 0, 2] | 0 -> 4 |
| [IMG_20181218_170247.jpg](visuals/resolution_001_IMG_20181218_170247.jpg) | [4, 0, 1, 1, 0] | [0, 0, 2, 2, 0] | [0, 0, 2, 0, 0] | 6 -> 6 |
| [IMG_20181218_171555.jpg](visuals/resolution_001_IMG_20181218_171555.jpg) | [5, 3, 1, 1, 2] | [5, 3, 1, 1, 2] | [6, 1, 2, 1, 2] | 0 -> 4 |
| [IMG_20181218_171604.jpg](visuals/resolution_001_IMG_20181218_171604.jpg) | [0, 3, 0, 0, 2] | [0, 3, 0, 0, 2] | [1, 0, 0, 0, 3] | 0 -> 5 |
| [IMG_20181218_171607.jpg](visuals/resolution_001_IMG_20181218_171607.jpg) | [5, 0, 1, 1, 2] | [5, 0, 1, 1, 2] | [0, 0, 3, 0, 0] | 0 -> 10 |
| [IMG_20181218_171749.jpg](visuals/resolution_001_IMG_20181218_171749.jpg) | [5, 3, 1, 1, 2] | [5, 2, 1, 1, 2] | [5, 3, 2, 1, 3] | 1 -> 2 |
| [IMG_20181218_171753.jpg](visuals/resolution_001_IMG_20181218_171753.jpg) | [5, 3, 1, 1, 2] | [5, 2, 1, 1, 2] | [4, 0, 2, 1, 4] | 1 -> 7 |
| [IMG_20181218_171755.jpg](visuals/resolution_001_IMG_20181218_171755.jpg) | [5, 3, 1, 1, 2] | [5, 1, 1, 1, 3] | [7, 0, 2, 0, 3] | 3 -> 8 |
| [IMG_20181218_171800.jpg](visuals/resolution_001_IMG_20181218_171800.jpg) | [5, 0, 1, 1, 0] | [5, 0, 1, 2, 3] | [0, 0, 2, 0, 1] | 4 -> 8 |
| [IMG_20181218_171802.jpg](visuals/resolution_001_IMG_20181218_171802.jpg) | [5, 0, 1, 0, 0] | [1, 0, 1, 1, 0] | [1, 0, 1, 0, 0] | 5 -> 4 |
| [IMG_20181218_171805.jpg](visuals/resolution_001_IMG_20181218_171805.jpg) | [0, 3, 0, 0, 2] | [0, 3, 0, 0, 3] | [0, 0, 0, 0, 0] | 1 -> 5 |
| [IMG_20190206_170714.jpg](visuals/resolution_001_IMG_20190206_170714.jpg) | [5, 0, 0, 4, 0] | [2, 0, 2, 3, 0] | [0, 0, 1, 2, 0] | 6 -> 8 |
| [IMG_20190206_170716.jpg](visuals/resolution_001_IMG_20190206_170716.jpg) | [5, 0, 0, 4, 0] | [3, 0, 2, 4, 1] | [0, 0, 0, 1, 1] | 5 -> 9 |
| [IMG_20190206_174852.jpg](visuals/resolution_001_IMG_20190206_174852.jpg) | [3, 1, 1, 1, 2] | [4, 1, 1, 1, 2] | [3, 1, 1, 1, 5] | 1 -> 3 |
| [IMG_20190206_174855.jpg](visuals/resolution_001_IMG_20190206_174855.jpg) | [4, 1, 1, 1, 2] | [5, 1, 1, 1, 2] | [6, 1, 1, 0, 3] | 1 -> 4 |
| [IMG_20190402_110254.jpg](visuals/resolution_001_IMG_20190402_110254.jpg) | [4, 1, 1, 1, 1] | [1, 1, 1, 0, 2] | [5, 1, 2, 3, 2] | 5 -> 5 |
| [IMG_20190430_111818.jpg](visuals/resolution_001_IMG_20190430_111818.jpg) | [3, 1, 1, 1, 2] | [4, 1, 1, 1, 2] | [4, 1, 1, 2, 2] | 1 -> 2 |
| [IMG_20190430_111949.jpg](visuals/resolution_001_IMG_20190430_111949.jpg) | [3, 1, 0, 1, 2] | [4, 1, 1, 1, 3] | [4, 1, 1, 3, 1] | 3 -> 5 |

Representative panels inspected visually:
- **IMG_20181218_171607.jpg:** crowded shelf, exact counts at 320 become [0,0,3,0,0] at 640 against [5,0,1,1,2]. Red Bull/Capri rows disappear; partial Classic boxes replace the water detections.
- **IMG_20181218_171755.jpg:** neighboring Red Bulls rise from the correct five to seven, Knoppers goes from one to zero against three, and Still is replaced by an extra Classic prediction. Count error increases 3 -> 8.
- **IMG_20190206_174852.jpg:** distant crowded shelf; Red Bull count improves 4 -> 3, but Capri-Sun predictions rise 2 -> 5 against two. Overall error worsens 1 -> 3. A local class improvement is not an image-level win.
- **IMG_20181218_171805.jpg:** 640 returns no detections despite five targets. At 320 all five are matched plus one false Capri-Sun; count error rises 1 -> 5.
- **IMG_20181218_165652.jpg:** the only positive image with zero true positives at 320 still has zero true positives at 640. A false Capri-Sun is replaced by a poorly localized Classic box on a Still bottle (best GT IoU 0.2553). Count error improves 13 -> 11 through count cancellation, not a recovered target.
- **IMG_20181218_171802.jpg:** the other improved image loses one false Still count; error falls 5 -> 4 while four Red Bulls remain under-counted.
- **IMG_20181218_165648.jpg:** target-free image changes from no predictions to two false regular Red Bulls and one false Capri-Sun. This is a new false-positive failure.
- **IMG_20181218_170247.jpg:** unchanged total class-count error hides a change: Still count 2 -> 0 around a true count of one swaps over-counting for under-counting.
**Zero-output distinction:** there are no 320px images with both zero predictions and positive target counts. The two zero-output images at 320 have no targets. The hard positive image above has zero correct detections but one false prediction. 640 introduces a genuinely empty prediction result on a positive image (171805).

## 6. Conclusion

**Use 320px, confidence 0.25 and NMS IoU 0.50 for further development of this frozen checkpoint.** The 640px resolution is worse across every class MAE, overall counting MAE, recall and exact count accuracy, including crowded and small-product subsets. The two improved images do not outweigh the 21 regressions.
The checkpoint was trained at 320; sensitivity to a different inference scale is a plausible explanation, not a demonstrated cause. These results do not establish that a separately trained 640 model would perform worse. Conclusions are limited to this checkpoint and these 26 validation images across five scene groups.

## 7. Single next controlled experiment (proposal only)

**Compare confidence 0.25 versus 0.15 at 320px**, with the identical frozen BASELINE_002 checkpoint, NMS IoU 0.50, validation split, preprocessing and evaluator. This tests whether the remaining 45 unmatched targets at the preferred resolution can be recovered at an acceptable false-positive/counting cost. The 34 existing false positives make this a trade-off, not a predicted improvement. Judge per-class/counting MAE, exact counts, recall, over/under-counts and duplicate candidates together; do not choose solely by recall. No confidence sweep, retraining or test-set evaluation. This experiment has **not** been run.

## Validation and reproducibility

**31 tests passed** (the complete existing 30-test suite plus one resolution-protocol/artifact test). All **178 protected artifacts** retain their SHA-256 hashes, including the earlier 72-artifact baseline snapshot, NMS_001 artifacts, and existing evaluation code. All frozen dataset image/label/config hashes were also verified. Hashing test files for integrity is not test inference or test metric evaluation.
No model retraining, checkpoint modification, dataset/split/class-map modification, or test-set evaluation occurred. Exactly two validation inference runs were performed; image analysis only read saved predictions. Existing BASELINE_002 and NMS_001 artifacts were not modified.
Evidence: [preservation hashes](resolution_001_preservation.json), [inference log](resolution_001_inference.log), [analysis log](resolution_001_analysis.log), [test log](resolution_001_tests.log).

```powershell
.\.venv\Scripts\python.exe -m src.resolution_experiment
.\.venv\Scripts\python.exe -m src.analyze_resolution
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.report_resolution
```
The inference command refuses to overwrite this completed experiment. Analysis/report commands read saved results and regenerate only RESOLUTION_001 outputs.
