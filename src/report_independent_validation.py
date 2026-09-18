"""Write a blocked independent-evaluation report without invoking inference."""
import json
from src.independent_validation_001_audit import ROOT, verify_protected


def main():
    a=json.loads((ROOT/'reports/independent_validation_001_audit.json').read_text())
    assert a['status']=='blocked_no_verified_independent_groups' and not a['inference_performed']
    log=(ROOT/'reports/independent_validation_001_tests.log').read_text()
    assert 'Ran 36 tests' in log and log.rstrip().endswith('OK')
    protected=verify_protected()
    lines=['# INDEPENDENT_VALIDATION_001: independent-scene eligibility audit','',
    '**Stopped before inference: the existing dataset has no verified unused independent groups outside the frozen test set.** No independent evaluation set was created, no checkpoint was loaded for prediction, and no A/B model metrics were computed. The audit is complete; the requested generalization measurement is blocked by data availability.','',
    '## 1. Independent-set construction','',
    'The audit enumerated all source image files and cross-checked them against the archive inventory, paired annotation manifest, scene-group review, frozen split assignments and quarantine list. All 277 source image names match the archive and manifest, and every source image matches its recorded SHA-256. There are 295 XML files; 18 have no corresponding source image and cannot provide evaluation inputs.',
    'Grouping follows the existing machine-sticker identifiers, visually reviewed adjacent captures, cross-date revisit merges and near-duplicate review. Images were considered by whole group, not randomly sampled. The 33 sticker-supported group IDs are exactly the union of existing train, validation and test group IDs. No verified group is unassigned.',
    '', '| Pool | Verified groups | Images | Eligibility |','| --- | ---: | ---: | --- |',
    '| Existing training | 23 | 123 | Excluded: used to train both models |',
    '| Existing validation | 5 | 26 | Excluded: repeatedly used for selection/development |',
    '| Frozen test | 5 | 26 | Excluded: user explicitly forbids test evaluation or repurposing |',
    '| Quarantine | 0 verified; 25 unresolved components | 102 | Independence cannot be established |',
    '| Eligible independent set | 0 | 0 | Construction gate failed |','',
    'The 102 quarantine images include 98 excluded solely for unresolved cross-visit machine identity, one image/XML dimension mismatch, and three vending-screen product-icon images rather than physical products. All 102 occur in unresolved components. A component is a correlation grouping, **not proof of a distinct machine**. A different filename, date, view, or unmatched image hash does not establish that it is independent of train/validation/test.',
    'The unresolved pool contains 2,862 raw source object annotations, including 629 labels matching the five target classes. These counts include quarantined images and are an inventory audit only, not usable independent annotations or performance evidence.',
    '', '| Class | Raw labels in rejected quarantine pool | Selected independent annotations |','| --- | ---: | ---: |']
    for name,count in zip(a['class_names'],a['quarantine_selected_class_counts']):
        lines.append(f'| {name} | {count} | 0 |')
    lines += ['', '**Selected scene/group IDs: none. Selected images: 0. Selected annotations: 0.** No empty set is presented as a frozen benchmark. Membership and results were not selected after seeing predictions, because no predictions were run.',
    '**Overlap conclusion:** all verified candidate groups overlap an existing split. Excluding train and validation leaves only the five protected test groups; excluding those leaves zero. Independence for unresolved components is unknown, so no positive no-overlap claim is made for them.',
    '', '### Verified group allocation','', '| Existing split | Group IDs |','| --- | --- |']
    for split in ['train','val','test']:
        lines.append('| '+split+' | '+', '.join('`'+g+'`' for g in a['split_group_ids'][split])+' |')
    lines += ['', '### Unresolved components (rejected, not independent scene IDs)','',
    '| Component ID | Images | All raw annotations | Target labels (RB / Knoppers / Classic / Still / Capri) |','| --- | ---: | ---: | --- |']
    for g in a['groups']:
        if g['status']=='unresolved':
            lines.append(f"| {g['scene_group']} | {len(g['images'])} | {g['annotation_count_all_classes']} | {g['selected_class_counts']} |")
    lines += ['', 'Source evidence: [audit JSON with every group and image membership](independent_validation_001_audit.json), [original scene groups](scene_groups.json), [scene-review policy](../configs/scene_review.json), [frozen splits](../configs/splits.json), [quarantine](quarantine.json). No original grouping or exclusion was modified.',
    '', '## 2. Frozen model configurations','']
    for tag,name in [('A','BASELINE_002, no augmentation'),('B','AUGMENTATION_001, augmentation')]:
        lines += [f"**{tag}: {name}**. Checkpoint: `{a['models'][tag]}`. SHA-256: `{a['model_hashes'][tag]}`.",'']
    lines += ['The intended evaluation settings remain 320px, CPU, class-aware NMS IoU 0.50, Red Bull confidence 0.15 and all four other classes 0.25; same rectangular preprocessing, batch=1 and max_det=300. The class-specific pre-NMS gate, same-class one-to-one matching at IoU >=0.50, and counting evaluator remain unchanged. These settings were recorded, but inference was not executed.',
    '', '## 3. Results','', '**N/E = not evaluated because independence could not be established. It does not mean zero performance.**','',
    '| Requested metric | A | B |','| --- | --- | --- |']
    for metric in ['Precision','Recall','Counting MAE','Exact five-class count accuracy','Total predicted instances','Duplicate candidates','Over-counted items','Under-counted items','Per-class counting MAE (all five)','Per-class precision/recall (all five)','Images improved / unchanged / worsened','Performance by independent group']:
        lines.append(f'| {metric} | N/E | N/E |')
    lines += ['', '## 4. Generalization analysis','',
    'There is no new independent evidence about whether augmentation generalizes. The previously observed development-validation improvement (MAE 0.554 -> 0.423 and exact vectors 6/26 -> 11/26) remains a result on the same repeatedly inspected 26 images; it is not replicated by this audit. The lack of eligible data neither confirms nor refutes the augmentation benefit.',
    '', '## 5. Per-class analysis','',
    'No independent estimates exist for Red Bull, Knoppers, Valser Classic, Valser Still or Capri-Sun. In particular, the earlier water-class over-counting regressions remain unresolved; this audit cannot show that they persist or disappear on new scenes. Crowded shelves, small products, variants, duplicates and under-counting likewise remain unmeasured independently.',
    '', '## 6. Scene-level analysis','',
    'There are no eligible evaluated scenes, so no helped/hurt/similar examples can be identified honestly. Unresolved or test scenes were not scored for convenient examples. The candidate-component table above is evidence about data eligibility, not model behavior.',
    '', '## 7. Conclusion','',
    '**Independent generalization is not established.** The augmented model can remain the provisional development choice based on AUGMENTATION_001, but this audit provides no additional evidence for replacing or deploying it. The blocker is zero verified unused independent groups, not an inconclusive small numerical difference. No further use of the existing validation images can resolve this independence gap.',
    '', '## 8. One next experiment (not run)','',
    '**Collect, annotate and freeze a separate cohort from verifiably new machines/shelf scenes, then perform one paired evaluation of these exact frozen A/B models.** Record stable location/machine/capture identifiers, keep all correlated views together, exclude overlap and near-duplicates with every existing split, and freeze membership/labels before inference. Include the same five labeled classes, crowded scenes, neighboring products, and target-free images. Use both models on identical images with the recorded thresholds and evaluator; report group-level and aggregate outcomes. Keep the original frozen dataset and test set untouched. This new-data experiment has not been started.',
    '', '## Validation and integrity','',
    f'All **36 existing tests passed**. All **{protected} protected files** retain their SHA-256 hashes, including earlier experiment artifacts, both checkpoints, the frozen split/evaluator, and all 572 extracted raw image/XML files. Frozen exported dataset image/label/config hashes also remain unchanged. Source image hashes additionally match the original paired manifest.',
    'No retraining, fine-tuning, inference, model selection, test-set evaluation, dataset mutation or evaluator modification occurred. Reading split metadata/annotation inventory and hashing test files is an integrity audit, not model evaluation. No independent set was frozen because the eligibility gate failed.',
    'Evidence: [audit log](independent_validation_001_audit.log), [preservation snapshot](independent_validation_001_preservation.json), [full test log](independent_validation_001_tests.log).','',
    '```powershell', '.\\.venv\\Scripts\\python.exe -m src.independent_validation_001_audit', '.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v', '.\\.venv\\Scripts\\python.exe -m src.report_independent_validation', '```',
    'The audit entry point refuses to overwrite the recorded audit. The report reads saved audit evidence and never invokes a model.']
    (ROOT/'reports/INDEPENDENT_VALIDATION_001_RESULTS.md').write_text('\n'.join(lines)+'\n')
    verify_protected()


if __name__=='__main__':
    main()
