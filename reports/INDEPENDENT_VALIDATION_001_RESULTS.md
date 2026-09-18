# INDEPENDENT_VALIDATION_001: independent-scene eligibility audit

**Stopped before inference: the existing dataset has no verified unused independent groups outside the frozen test set.** No independent evaluation set was created, no checkpoint was loaded for prediction, and no A/B model metrics were computed. The audit is complete; the requested generalization measurement is blocked by data availability.

## 1. Independent-set construction

The audit enumerated all source image files and cross-checked them against the archive inventory, paired annotation manifest, scene-group review, frozen split assignments and quarantine list. All 277 source image names match the archive and manifest, and every source image matches its recorded SHA-256. There are 295 XML files; 18 have no corresponding source image and cannot provide evaluation inputs.
Grouping follows the existing machine-sticker identifiers, visually reviewed adjacent captures, cross-date revisit merges and near-duplicate review. Images were considered by whole group, not randomly sampled. The 33 sticker-supported group IDs are exactly the union of existing train, validation and test group IDs. No verified group is unassigned.

| Pool | Verified groups | Images | Eligibility |
| --- | ---: | ---: | --- |
| Existing training | 23 | 123 | Excluded: used to train both models |
| Existing validation | 5 | 26 | Excluded: repeatedly used for selection/development |
| Frozen test | 5 | 26 | Excluded: user explicitly forbids test evaluation or repurposing |
| Quarantine | 0 verified; 25 unresolved components | 102 | Independence cannot be established |
| Eligible independent set | 0 | 0 | Construction gate failed |

The 102 quarantine images include 98 excluded solely for unresolved cross-visit machine identity, one image/XML dimension mismatch, and three vending-screen product-icon images rather than physical products. All 102 occur in unresolved components. A component is a correlation grouping, **not proof of a distinct machine**. A different filename, date, view, or unmatched image hash does not establish that it is independent of train/validation/test.
The unresolved pool contains 2,862 raw source object annotations, including 629 labels matching the five target classes. These counts include quarantined images and are an inventory audit only, not usable independent annotations or performance evidence.

| Class | Raw labels in rejected quarantine pool | Selected independent annotations |
| --- | ---: | ---: |
| Red Bull (source class) | 252 | 0 |
| Knoppers (source class) | 90 | 0 |
| Valser Classic (source class) | 145 | 0 |
| Valser Still (source class) | 98 | 0 |
| Capri-Sun Multivitamin (source class) | 44 | 0 |

**Selected scene/group IDs: none. Selected images: 0. Selected annotations: 0.** No empty set is presented as a frozen benchmark. Membership and results were not selected after seeing predictions, because no predictions were run.
**Overlap conclusion:** all verified candidate groups overlap an existing split. Excluding train and validation leaves only the five protected test groups; excluding those leaves zero. Independence for unresolved components is unknown, so no positive no-overlap claim is made for them.

### Verified group allocation

| Existing split | Group IDs |
| --- | --- |
| train | `machine_b9dd5ca784c4`, `machine_0afdf2e120a1`, `machine_65d0be958c17`, `machine_39b4eccd47a2`, `machine_0808846669be`, `machine_555048df54d8`, `machine_cad58c8878fc`, `machine_c6004947c1d2`, `machine_6102f9410102`, `machine_4d293f534e70`, `machine_e1be96cf78b1`, `machine_e1e2930ccd46`, `machine_643b0aa1da5e`, `machine_c8f4eb3df42d`, `machine_a41778b7de32`, `machine_ef9ec98a5e0d`, `machine_f75228c14f5f`, `machine_934574a6522d`, `machine_2d60d7ebba2a`, `machine_897e4fa6ce47`, `machine_82d607ddcaca`, `machine_2d99255acb57`, `machine_7520467cbe23` |
| val | `machine_a9608332afdb`, `machine_009154991598`, `machine_bb3e4ae22b1d`, `machine_bf445d25f803`, `machine_4456752f715b` |
| test | `machine_89a4eeedccc7`, `machine_7a18e7d150bd`, `machine_3e8d6eb2ede6`, `machine_f37708d55f06`, `machine_28f06f073c6a` |

### Unresolved components (rejected, not independent scene IDs)

| Component ID | Images | All raw annotations | Target labels (RB / Knoppers / Classic / Still / Capri) |
| --- | ---: | ---: | --- |
| unresolved_000 | 51 | 1100 | [102, 35, 68, 34, 0] |
| unresolved_042 | 1 | 39 | [1, 3, 0, 0, 2] |
| unresolved_058 | 3 | 114 | [8, 6, 3, 3, 5] |
| unresolved_063 | 1 | 17 | [1, 0, 1, 0, 2] |
| unresolved_064 | 1 | 29 | [4, 0, 1, 0, 2] |
| unresolved_074 | 4 | 106 | [16, 0, 6, 12, 0] |
| unresolved_146 | 3 | 124 | [8, 9, 2, 2, 6] |
| unresolved_149 | 5 | 215 | [25, 11, 5, 5, 10] |
| unresolved_175 | 1 | 18 | [0, 0, 1, 4, 0] |
| unresolved_216 | 1 | 32 | [2, 1, 1, 1, 1] |
| unresolved_218 | 2 | 38 | [4, 2, 4, 0, 0] |
| unresolved_220 | 3 | 99 | [9, 3, 6, 3, 0] |
| unresolved_223 | 2 | 60 | [6, 2, 4, 2, 0] |
| unresolved_225 | 2 | 90 | [0, 0, 14, 14, 2] |
| unresolved_227 | 3 | 135 | [12, 3, 0, 0, 0] |
| unresolved_230 | 2 | 73 | [6, 2, 4, 2, 0] |
| unresolved_232 | 3 | 108 | [9, 3, 6, 3, 0] |
| unresolved_235 | 3 | 72 | [9, 0, 9, 9, 0] |
| unresolved_238 | 3 | 110 | [9, 3, 6, 3, 0] |
| unresolved_245 | 1 | 39 | [5, 1, 2, 1, 2] |
| unresolved_256 | 1 | 43 | [3, 1, 0, 0, 2] |
| unresolved_259 | 1 | 32 | [2, 1, 0, 0, 1] |
| unresolved_260 | 1 | 31 | [2, 1, 0, 0, 1] |
| unresolved_261 | 2 | 83 | [8, 2, 2, 0, 4] |
| unresolved_274 | 2 | 55 | [1, 1, 0, 0, 4] |

Source evidence: [audit JSON with every group and image membership](independent_validation_001_audit.json), [original scene groups](scene_groups.json), [scene-review policy](../configs/scene_review.json), [frozen splits](../configs/splits.json), [quarantine](quarantine.json). No original grouping or exclusion was modified.

## 2. Frozen model configurations

**A: BASELINE_002, no augmentation**. Checkpoint: `C:\Users\Lenovo\Documents\ChatGPT\StoreRoom\runs\baseline_002\weights\best.pt`. SHA-256: `7e048d48a3b80cf5cab1aafb30dfb63f7f20c94e12b26ded8aac35de5ecd0cbd`.

**B: AUGMENTATION_001, augmentation**. Checkpoint: `C:\Users\Lenovo\Documents\ChatGPT\StoreRoom\runs\augmentation_001\weights\best.pt`. SHA-256: `099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4`.

The intended evaluation settings remain 320px, CPU, class-aware NMS IoU 0.50, Red Bull confidence 0.15 and all four other classes 0.25; same rectangular preprocessing, batch=1 and max_det=300. The class-specific pre-NMS gate, same-class one-to-one matching at IoU >=0.50, and counting evaluator remain unchanged. These settings were recorded, but inference was not executed.

## 3. Results

**N/E = not evaluated because independence could not be established. It does not mean zero performance.**

| Requested metric | A | B |
| --- | --- | --- |
| Precision | N/E | N/E |
| Recall | N/E | N/E |
| Counting MAE | N/E | N/E |
| Exact five-class count accuracy | N/E | N/E |
| Total predicted instances | N/E | N/E |
| Duplicate candidates | N/E | N/E |
| Over-counted items | N/E | N/E |
| Under-counted items | N/E | N/E |
| Per-class counting MAE (all five) | N/E | N/E |
| Per-class precision/recall (all five) | N/E | N/E |
| Images improved / unchanged / worsened | N/E | N/E |
| Performance by independent group | N/E | N/E |

## 4. Generalization analysis

There is no new independent evidence about whether augmentation generalizes. The previously observed development-validation improvement (MAE 0.554 -> 0.423 and exact vectors 6/26 -> 11/26) remains a result on the same repeatedly inspected 26 images; it is not replicated by this audit. The lack of eligible data neither confirms nor refutes the augmentation benefit.

## 5. Per-class analysis

No independent estimates exist for Red Bull, Knoppers, Valser Classic, Valser Still or Capri-Sun. In particular, the earlier water-class over-counting regressions remain unresolved; this audit cannot show that they persist or disappear on new scenes. Crowded shelves, small products, variants, duplicates and under-counting likewise remain unmeasured independently.

## 6. Scene-level analysis

There are no eligible evaluated scenes, so no helped/hurt/similar examples can be identified honestly. Unresolved or test scenes were not scored for convenient examples. The candidate-component table above is evidence about data eligibility, not model behavior.

## 7. Conclusion

**Independent generalization is not established.** The augmented model can remain the provisional development choice based on AUGMENTATION_001, but this audit provides no additional evidence for replacing or deploying it. The blocker is zero verified unused independent groups, not an inconclusive small numerical difference. No further use of the existing validation images can resolve this independence gap.

## 8. One next experiment (not run)

**Collect, annotate and freeze a separate cohort from verifiably new machines/shelf scenes, then perform one paired evaluation of these exact frozen A/B models.** Record stable location/machine/capture identifiers, keep all correlated views together, exclude overlap and near-duplicates with every existing split, and freeze membership/labels before inference. Include the same five labeled classes, crowded scenes, neighboring products, and target-free images. Use both models on identical images with the recorded thresholds and evaluator; report group-level and aggregate outcomes. Keep the original frozen dataset and test set untouched. This new-data experiment has not been started.

## Validation and integrity

All **36 existing tests passed**. All **921 protected files** retain their SHA-256 hashes, including earlier experiment artifacts, both checkpoints, the frozen split/evaluator, and all 572 extracted raw image/XML files. Frozen exported dataset image/label/config hashes also remain unchanged. Source image hashes additionally match the original paired manifest.
No retraining, fine-tuning, inference, model selection, test-set evaluation, dataset mutation or evaluator modification occurred. Reading split metadata/annotation inventory and hashing test files is an integrity audit, not model evaluation. No independent set was frozen because the eligibility gate failed.
Evidence: [audit log](independent_validation_001_audit.log), [preservation snapshot](independent_validation_001_preservation.json), [full test log](independent_validation_001_tests.log).

```powershell
.\.venv\Scripts\python.exe -m src.independent_validation_001_audit
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.report_independent_validation
```
The audit entry point refuses to overwrite the recorded audit. The report reads saved audit evidence and never invokes a model.
