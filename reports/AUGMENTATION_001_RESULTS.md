# AUGMENTATION_001: controlled training augmentation comparison

**Use the augmented checkpoint as the next development model, with explicit Valser regressions.** Overall five-class counting MAE improves 23.6%, exact vectors increase from 6/26 to 11/26, recall improves and duplicate candidates disappear. Both water classes have worse counting MAE, and total false positives rise. This is a measured validation gain, not a production-readiness claim.

## 1. Experiment setup

A is the completed 30-epoch no-augmentation BASELINE_002 run and its frozen best checkpoint. Its training was not repeated; the specified checkpoint is reused and freshly evaluated. B is one new 30-epoch run from the identical original pretrained yolo11n.pt, not from A. No other training configuration was tried.
Initial weights SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.
Frozen dataset manifest SHA-256: `878424031a9ab66bb64a89ac4dfbb5bebc889d67ef5e295d5e3ee494edae5513`.
Same 123 training / 26 validation / 26 held-out test split, class mapping, seed 42, CPU, image size 320, batch 4, AdamW lr0=0.001, lrf=0.01, momentum=0.9, weight decay=0.0005, warmup 1 epoch, deterministic=true. Test data was not evaluated.
Augmentation parameters were written before training to this report and the immutable-for-this-run configuration [augmentation_001.yaml](../configs/augmentation_001.yaml). The changed controls are:

| Control | A | B | Interpretation |
| --- | ---: | ---: | --- |
| hsv_s | 0 | 0.1 | Moderate saturation jitter; gain 0.10 |
| hsv_v | 0 | 0.15 | Moderate brightness jitter; gain 0.15 |
| translate | 0 | 0.03 | Translation up to 3% |
| scale | 0 | 0.1 | Scale range about 0.90-1.10 |
| degrees | 0 | 3.0 | Rotation up to +/-3 degrees |

Hue jitter, horizontal/vertical flips, shear, perspective, mosaic, mixup, cutmix and copy-paste remain zero; close_mosaic=0. All other trainer settings remain identical apart from the separate output directory. Only stock Ultralytics augmentation controls are used; no custom augmentation code. This tests the bundle as one variable and cannot identify which constituent transform caused an effect.
Model selection retains the baseline training-internal validation settings (conf=0.001, NMS IoU=0.70). Stock best-checkpoint fitness is mAP50-95; no counting-based epoch selection or augmentation tuning is performed. The final fixed-threshold comparison is separate from these training-internal metrics.
Both final models use unchanged class-score gating before NMS: Red Bull confidence 0.15, all other classes 0.25, 320px, CPU, class-aware NMS IoU 0.50, rectangular preprocessing, batch=1, max_det=300, no inference augmentation. The frozen evaluator/counting functions are unchanged. A reproduces CLASS_CONFIDENCE_001 B predictions within the existing 1e-3-pixel / 1e-6-confidence tolerance.
Final precision/recall are custom micro metrics at these fixed cutoffs, using confidence-ordered same-class one-to-one GT matching at IoU >=0.50. Counting MAE averages absolute errors over 26 x 5 cells. Exact accuracy requires the entire five-class vector. Duplicate candidates use the prior GT-overlap diagnostic; over/under-count sums positive/negative cell errors, so count errors can differ from FP/FN.
Evidence: [training record](augmentation_001_training.json), [inference setup](augmentation_001_setup.json), [A predictions](augmentation_001_a.json), [B predictions](augmentation_001_b.json), [comparison](augmentation_001_comparison.json).

## 2. Training comparison

| Model | Duration (s) | Final epoch | Best epoch | Best training-internal mAP50 | Best training-internal mAP50-95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 1747.677 | 30 | 23 | 0.833720 | 0.549420 |
| B | 1641.027 | 30 | 30 | 0.928470 | 0.615070 |

Best epoch is reconstructed from the last maximum validation fitness in results.csv and checked against the saved best checkpoint metric. Exported checkpoints have epoch=-1, so that field is not treated as the selected epoch.

| Run/epoch | Train box | Train cls | Train DFL | Val box | Val cls | Val DFL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A best (23) | 0.646580 | 0.591060 | 0.814350 | 1.314510 | 1.123700 | 0.911150 |
| A final (30) | 0.526620 | 0.538980 | 0.804890 | 1.321340 | 1.084260 | 0.907560 |
| B best (30) | 0.995690 | 0.682070 | 0.855690 | 1.220050 | 0.884940 | 0.892910 |
| B final (30) | 0.995690 | 0.682070 | 0.855690 | 1.220050 | 0.884940 | 0.892910 |

A checkpoint: `C:\Users\Lenovo\Documents\ChatGPT\StoreRoom\runs\baseline_002\weights\best.pt`; SHA-256 `7e048d48a3b80cf5cab1aafb30dfb63f7f20c94e12b26ded8aac35de5ecd0cbd`.


B checkpoint: `C:\Users\Lenovo\Documents\ChatGPT\StoreRoom\runs\augmentation_001\weights\best.pt`; SHA-256 `099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4`.

![Training and validation loss curves](visuals/augmentation_001_loss_curves.png)
Full epoch histories: [A results.csv](../runs/baseline_002/results.csv), [B results.csv](../runs/augmentation_001/results.csv). Training losses with augmented images and unaugmented images are not identically distributed; final fixed-inference metrics are the practical comparison.

## 3. Validation results

| Metric | A: no augmentation | B: moderate augmentation | B - A |
| --- | ---: | ---: | ---: |
| Precision | 0.806763 | 0.791304 | -0.015459 |
| Recall | 0.814634 | 0.887805 | +0.073171 |
| Counting MAE | 0.553846 | 0.423077 | -0.130769 |
| Exact five-class accuracy | 0.230769 | 0.423077 | +0.192308 |
| Predicted instances | 207.000000 | 230.000000 | +23.000000 |
| Duplicate candidates | 2.000000 | 0.000000 | -2.000000 |
| Over-count items | 37.000000 | 40.000000 | +3.000000 |
| Under-count items | 35.000000 | 15.000000 | -20.000000 |
| TP | 167.000000 | 182.000000 | +15.000000 |
| FP | 40.000000 | 48.000000 | +8.000000 |
| FN | 38.000000 | 23.000000 | -15.000000 |
| Total-item count MAE | 2.076923 | 0.961538 | -1.115385 |

B improves 12 images, leaves 10 unchanged, and worsens 4 by summed absolute five-class errors. Always-zero MAE remains 1.576923 (1.577 rounded).

## 4. Counting analysis

Overall MAE falls 0.553846 -> 0.423077, corresponding to 72 -> 55 absolute image/class count errors (23.6% reduction). Exact five-class counts rise 6/26 -> 11/26; all six previously exact images remain exact. Under-counted items fall 35 -> 15, while over-counted items rise 37 -> 40. Duplicate candidates fall 2 -> 0. Total-item count MAE also improves 2.076923 -> 0.961538. Twelve images improve, ten have unchanged error and four worsen. Both target-free images stay prediction-free. Gains outweigh the regressions for the stated class-count objective, but zero duplicate candidates does not mean all boxes are correct: the matching rule does not classify every overlapping, partial or wrong-class box as a duplicate.

## 5. Per-class analysis

| Class | MAE A -> B | Precision A -> B | Recall A -> B | Over-count A -> B | Under-count A -> B |
| --- | --- | --- | --- | --- | --- |
| Red Bull | 1.346154 -> 0.884615 | 0.764706 -> 0.800000 | 0.773810 -> 0.809524 | 18 -> 12 | 17 -> 11 |
| Knoppers | 0.230769 -> 0.115385 | 0.968750 -> 1.000000 | 0.815789 -> 0.921053 | 0 -> 0 | 6 -> 3 |
| Valser Classic | 0.423077 -> 0.461538 | 0.681818 -> 0.548387 | 0.789474 -> 0.894737 | 7 -> 12 | 4 -> 0 |
| Valser Still | 0.423077 -> 0.538462 | 0.884615 -> 0.674419 | 0.741935 -> 0.935484 | 3 -> 13 | 8 -> 1 |
| Capri-Sun Multivitamin | 0.346154 -> 0.115385 | 0.785714 -> 0.916667 | 1.000000 -> 1.000000 | 9 -> 3 | 0 -> 0 |

- **Red Bull:** MAE 1.346154 -> 0.884615, TP 65 -> 68, FP 20 -> 17. Regular-on-light candidates remain seven; augmentation does not solve that variant distinction.
- **Knoppers:** MAE halves, 0.230769 -> 0.115385; TP 31 -> 35 of 38 and FP 1 -> 0.
- **Valser Classic:** recall improves (15 -> 17 TP), but FP doubles 7 -> 14; MAE worsens 0.423077 -> 0.461538.
- **Valser Still:** TP 23 -> 29 of 31, but FP rises 3 -> 14; MAE worsens 0.423077 -> 0.538462. Improved recall does not compensate for over-counting.
- **Capri-Sun:** all 33 targets remain matched; FP falls 9 -> 3 and MAE 0.346154 -> 0.115385. No Capri-Sun target misses occur in either model at these settings.

## 6. Failure analysis

Visually inspected examples and matching diagnostics:

- **IMG_20181218_170247.jpg:** neighboring products improve from five to six matched targets; the missing Red Bull is recovered and water-class extras disappear. Vector [3,0,2,2,0] becomes exact [4,0,1,1,0], reducing error 3 -> 0.
- **DSC01659.png:** crowded shelf; a Red Bull duplicate candidate disappears and one Knoppers is recovered. Matched targets rise 5 -> 6, error falls 6 -> 4. Two Red Bull false positives remain, so duplicate removal is not full variant recognition.
- **IMG_20181218_165652.jpg:** the previously all-missed hard positive improves from zero to four matched targets, but B predicts [2,0,3,8,0] against [6,0,2,4,0]. Error falls 13 -> 9 while substantial Red Bull/water confusion remains. This is not a reliable inventory result.
- **IMG_20181218_165646.jpg:** largest regression; error 5 -> 11. B labels multiple cans as Classic/Still and adds a false Red Bull box on another beverage. Vector [4,0,0,2,0] becomes [1,0,6,7,0] against [5,0,2,4,0]. B actually matches six targets versus five in A, illustrating why recall alone misses severe count/identity harm.
- **IMG_20181218_171753.jpg:** crowded scene worsens 1 -> 2 count error. B adds a Still prediction on a Classic bottle, despite recovering another correctly matched item elsewhere in the image.
- **IMG_20181218_171802.jpg:** error 4 -> 0; matched targets rise 3 -> 6, recovering three adjacent Red Bulls and removing a false Still prediction.
- **IMG_20181218_171800.jpg:** three false Capri-Suns and an extra Still count disappear, producing an exact vector.

The four count regressions are DSC01658.png, IMG_20181218_165646.jpg, IMG_20181218_171753.jpg and IMG_20190206_170714.jpg. Two are in the crowded subset. Aggregate crowded MAE nevertheless improves 0.457143 -> 0.342857. Wrong selected-class candidates double 8 -> 16, while Classic-vs-Still candidates alone remain four: the new errors include cross-category confusion, not just swapping the two water labels.

| Subset | Images | MAE A -> B | Exact accuracy A -> B |
| --- | ---: | --- | --- |
| crowded_30plus_source_objects | 14 | 0.457143 -> 0.342857 | 0.142857 -> 0.214286 |
| multi_instance_2plus | 24 | 0.600000 -> 0.458333 | 0.166667 -> 0.375000 |

Crowded means >=30 source objects including non-targets; multi-instance means >=2 of one selected class. These subset definitions are unchanged.
Small targets (GT area below 32x32 after scaling long side to 320): 149/174 matched in A versus 157/174 in B. This is a fixed descriptive grouping, not AP-small.
Identity candidates A -> B: selected-class confusion 8 -> 16; Valser Classic/Still 4 -> 4; regular Red Bull overlapping source light 7 -> 7. Regular Red Bull sizes are merged by source labels, so size-specific accuracy cannot be measured.
GT matching identities: 21 gained, 6 lost. Count improvements alone can conceal localization/class errors.

Vectors use Red Bull / Knoppers / Classic / Still / Capri-Sun. All validation comparisons are linked:

| Image | Truth | A | B | Absolute class error A -> B |
| --- | --- | --- | --- | --- |
| [DSC01657.png](visuals/augmentation_001_DSC01657.jpg) | [2, 3, 1, 1, 2] | [5, 3, 1, 1, 2] | [4, 3, 1, 1, 2] | 3 -> 2 |
| [DSC01658.png](visuals/augmentation_001_DSC01658.jpg) | [0, 3, 1, 1, 2] | [3, 3, 1, 1, 2] | [2, 3, 1, 3, 2] | 3 -> 4 |
| [DSC01659.png](visuals/augmentation_001_DSC01659.jpg) | [2, 3, 0, 0, 2] | [5, 1, 1, 0, 2] | [4, 2, 1, 0, 2] | 6 -> 4 |
| [IMG_20181218_165646.jpg](visuals/augmentation_001_IMG_20181218_165646.jpg) | [5, 0, 2, 4, 0] | [4, 0, 0, 2, 0] | [1, 0, 6, 7, 0] | 5 -> 11 |
| [IMG_20181218_165648.jpg](visuals/augmentation_001_IMG_20181218_165648.jpg) | [0, 0, 0, 0, 0] | [0, 0, 0, 0, 0] | [0, 0, 0, 0, 0] | 0 -> 0 |
| [IMG_20181218_165652.jpg](visuals/augmentation_001_IMG_20181218_165652.jpg) | [6, 0, 2, 4, 0] | [0, 0, 0, 0, 1] | [2, 0, 3, 8, 0] | 13 -> 9 |
| [IMG_20181218_165657.jpg](visuals/augmentation_001_IMG_20181218_165657.jpg) | [0, 0, 0, 0, 0] | [0, 0, 0, 0, 0] | [0, 0, 0, 0, 0] | 0 -> 0 |
| [IMG_20181218_170238.jpg](visuals/augmentation_001_IMG_20181218_170238.jpg) | [3, 3, 1, 1, 2] | [6, 3, 1, 1, 2] | [5, 3, 1, 1, 2] | 3 -> 2 |
| [IMG_20181218_170243.jpg](visuals/augmentation_001_IMG_20181218_170243.jpg) | [0, 3, 0, 0, 2] | [0, 3, 0, 0, 2] | [0, 3, 0, 0, 2] | 0 -> 0 |
| [IMG_20181218_170247.jpg](visuals/augmentation_001_IMG_20181218_170247.jpg) | [4, 0, 1, 1, 0] | [3, 0, 2, 2, 0] | [4, 0, 1, 1, 0] | 3 -> 0 |
| [IMG_20181218_171555.jpg](visuals/augmentation_001_IMG_20181218_171555.jpg) | [5, 3, 1, 1, 2] | [5, 3, 1, 1, 2] | [5, 3, 1, 1, 2] | 0 -> 0 |
| [IMG_20181218_171604.jpg](visuals/augmentation_001_IMG_20181218_171604.jpg) | [0, 3, 0, 0, 2] | [0, 3, 0, 0, 2] | [0, 3, 0, 0, 2] | 0 -> 0 |
| [IMG_20181218_171607.jpg](visuals/augmentation_001_IMG_20181218_171607.jpg) | [5, 0, 1, 1, 2] | [5, 0, 1, 1, 2] | [5, 0, 1, 1, 2] | 0 -> 0 |
| [IMG_20181218_171749.jpg](visuals/augmentation_001_IMG_20181218_171749.jpg) | [5, 3, 1, 1, 2] | [5, 2, 1, 1, 2] | [5, 3, 1, 1, 2] | 1 -> 0 |
| [IMG_20181218_171753.jpg](visuals/augmentation_001_IMG_20181218_171753.jpg) | [5, 3, 1, 1, 2] | [5, 2, 1, 1, 2] | [5, 2, 1, 2, 2] | 1 -> 2 |
| [IMG_20181218_171755.jpg](visuals/augmentation_001_IMG_20181218_171755.jpg) | [5, 3, 1, 1, 2] | [5, 1, 1, 1, 3] | [5, 2, 1, 1, 3] | 3 -> 2 |
| [IMG_20181218_171800.jpg](visuals/augmentation_001_IMG_20181218_171800.jpg) | [5, 0, 1, 1, 0] | [5, 0, 1, 2, 3] | [5, 0, 1, 1, 0] | 4 -> 0 |
| [IMG_20181218_171802.jpg](visuals/augmentation_001_IMG_20181218_171802.jpg) | [5, 0, 1, 0, 0] | [2, 0, 1, 1, 0] | [5, 0, 1, 0, 0] | 4 -> 0 |
| [IMG_20181218_171805.jpg](visuals/augmentation_001_IMG_20181218_171805.jpg) | [0, 3, 0, 0, 2] | [1, 3, 0, 0, 3] | [0, 3, 0, 0, 2] | 2 -> 0 |
| [IMG_20190206_170714.jpg](visuals/augmentation_001_IMG_20190206_170714.jpg) | [5, 0, 0, 4, 0] | [2, 0, 2, 3, 0] | [2, 0, 4, 5, 0] | 6 -> 8 |
| [IMG_20190206_170716.jpg](visuals/augmentation_001_IMG_20190206_170716.jpg) | [5, 0, 0, 4, 0] | [5, 0, 2, 4, 1] | [5, 0, 2, 5, 0] | 3 -> 3 |
| [IMG_20190206_174852.jpg](visuals/augmentation_001_IMG_20190206_174852.jpg) | [3, 1, 1, 1, 2] | [4, 1, 1, 1, 2] | [4, 1, 1, 1, 2] | 1 -> 1 |
| [IMG_20190206_174855.jpg](visuals/augmentation_001_IMG_20190206_174855.jpg) | [4, 1, 1, 1, 2] | [5, 1, 1, 1, 2] | [5, 1, 1, 1, 2] | 1 -> 1 |
| [IMG_20190402_110254.jpg](visuals/augmentation_001_IMG_20190402_110254.jpg) | [4, 1, 1, 1, 1] | [1, 1, 1, 0, 2] | [4, 1, 1, 2, 2] | 5 -> 2 |
| [IMG_20190430_111818.jpg](visuals/augmentation_001_IMG_20190430_111818.jpg) | [3, 1, 1, 1, 2] | [4, 1, 1, 1, 2] | [4, 1, 1, 1, 2] | 1 -> 1 |
| [IMG_20190430_111949.jpg](visuals/augmentation_001_IMG_20190430_111949.jpg) | [3, 1, 0, 1, 2] | [5, 1, 1, 1, 3] | [4, 1, 0, 0, 3] | 4 -> 3 |

## 7. Conclusion

**The observed validation evidence supports replacing A with B as the working development checkpoint**, keeping the inference configuration unchanged. Counting MAE, exact vectors, recall, crowded/multi-instance performance, small-target recall and duplicate diagnostics improve together. Precision declines slightly (0.806763 -> 0.791304), and both Valser MAEs worsen, so the replacement comes with a specific unresolved identity/over-counting weakness. Preserve both frozen checkpoints and do not describe the model as production-ready. The best augmented epoch is 30; no additional epochs or alternative augmentations were tested.
This single-seed comparison on 26 development images across five scene groups does not establish robustness across seeds or unseen stores. No test-set result is used.

## 8. One next controlled experiment (not run)

**Run one paired A/B evaluation on a separately collected and annotated validation cohort from previously unseen machines/scenes**, using these two frozen checkpoints and the unchanged inference/evaluator settings. Include crowded shelves, neighboring water bottles/Red Bull cans and target-free scenes; fix membership and labels before scoring and exclude near-duplicates of the existing scenes. The objective is to check whether the overall gain and water-class regressions generalize beyond this repeatedly inspected validation split. Store the new cohort separately; do not change the existing frozen split or evaluate its test set. No data collection or additional evaluation has been performed here.

## Validation and reproduction

All **36 tests passed** (34 existing plus two augmentation checks). All **297 protected artifacts** and frozen dataset image/label/config hashes remain unchanged. BASELINE_002 and all previous experiment outputs remain unchanged. B is saved separately under runs/augmentation_001. No test-set evaluation occurred.
The exact configuration and runtime versions are recorded before training; there was one augmented run, no parameter tuning and no inference threshold changes. B was trained separately. The archived completed A training provides the baseline training evidence.
Evidence: [preservation](augmentation_001_preservation.json), [training log](augmentation_001_training.log), [tests](augmentation_001_tests.log).

```powershell
.\.venv\Scripts\python.exe -m src.train_augmentation
.\.venv\Scripts\python.exe -m src.evaluate_augmentation
.\.venv\Scripts\python.exe -m src.analyze_augmentation
.\.venv\Scripts\python.exe -m src.augmentation_001_training_summary
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.report_augmentation
```
Training/inference refuse to overwrite existing runs. The recorded configs support reproduction in a separate checkout/output directory. Analysis and report commands use saved outputs only.
