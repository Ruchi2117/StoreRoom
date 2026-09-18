"""Generate CLASS_CONFIDENCE_001 report from stored validation outputs only."""
import json
from pathlib import Path
from src.nms_experiment import ROOT
from src.class_confidence_experiment import verify_protected
from src.preview_yolo import NAMES


def main():
    read=lambda n:json.loads((ROOT/'reports'/n).read_text())
    a,b=[read(f'class_confidence_001_{t}.json') for t in ['a','b']]
    c=read('class_confidence_001_comparison.json')
    s=read('class_confidence_001_setup.json')
    protected=verify_protected()
    testlog=(ROOT/'reports/class_confidence_001_tests.log').read_text()
    assert 'Ran 34 tests' in testlog and testlog.rstrip().endswith('OK')
    lines=['# CLASS_CONFIDENCE_001: Red Bull-only confidence reduction','',
    '**Decision: retain the class-specific policy as a provisional development candidate, with a mixed-results qualification.** Overall class-count MAE improves 4%, Red Bull MAE improves, and the other four classes remain unchanged. Exact counts do not improve, precision falls, duplicates increase, and crowded-subset counting worsens. This is not a robust across-scene win.','',
    '## 1. Experiment setup','',
    'A: all five classes use confidence 0.25. B: Red Bull uses 0.15; Knoppers, Valser Classic, Valser Still and Capri-Sun Multivitamin remain at 0.25. Only the Red Bull cutoff changes.',
    f"Checkpoint: `{s['checkpoint']}`.",f"Checkpoint SHA-256: `{s['checkpoint_sha256']}`.",f"Dataset manifest SHA-256: `{s['dataset_manifest_sha256']}`.",
    'Same frozen BASELINE_002 weights from the 30-epoch run, same 26 validation images and five-class mapping, CPU, 320px, class-aware NMS IoU 0.50, rectangular preprocessing, batch=1, max_det=300, no augmentation. No retraining, test evaluation or extra model.',
    f"Common arguments: `{json.dumps(s['common_arguments'],sort_keys=True)}`. Runtime: Ultralytics {s['ultralytics']}, PyTorch {s['torch']}.",
    '**Implementation:** a DetectionPredictor subclass reads the raw five class scores for each candidate, takes the original highest-scoring class (the existing single-label semantics), then requires its score to be strictly greater than that class cutoff. Rejected candidates have all class scores zeroed on a cloned tensor **before stock NMS**, candidate limits and result construction. Accepted coordinates, identities and scores are unchanged. A rejected non-Red-Bull candidate cannot fall back to a second-best Red Bull label. The stock NMS confidence floor equals the minimum policy cutoff, but all candidates have already passed the appropriate class gate. This is not global 0.15 inference followed by post-NMS class filtering.',
    'Both A and B use this same adapter. Before full validation, synthetic checks passed for stock-baseline equivalence, Red Bull-only admission, rejection of low-confidence other classes, no runner-up relabeling, strict threshold boundaries and duplicate suppression. The fresh A outputs also reproduce CONFIDENCE_001 A boxes/scores within 1e-3 pixels / 1e-6 confidence.',
    'Evaluation/counting functions are imported unchanged from NMS_001/CONFIDENCE_001. Precision/recall are custom fixed-threshold micro metrics: confidence-ordered same-class one-to-one GT matching at IoU >=0.50. They are not Ultralytics F1-selected validation metrics. Counting MAE is mean absolute error over 26 x 5 cells; exact accuracy requires all five counts correct. Over/under-counts sum positive/negative cell errors. Duplicate candidates use the same GT-overlap diagnostic. No AP or model.val() pass was run.',
    f"Elapsed run durations including loading/diagnostics: A {a['duration_seconds']:.3f}s, B {b['duration_seconds']:.3f}s; not a controlled latency benchmark.",
    'Evidence: [setup](class_confidence_001_setup.json), [preflight sanity](class_confidence_001_sanity.json), [A outputs](class_confidence_001_a.json), [B outputs](class_confidence_001_b.json), [comparison](class_confidence_001_comparison.json).','',
    '## 2. Results','',
    '| Metric | A: global 0.25 | B: Red Bull 0.15 only | B - A |','| --- | ---: | ---: | ---: |']
    metrics=[('Precision',a['detection']['micro_precision'],b['detection']['micro_precision']),('Recall',a['detection']['micro_recall'],b['detection']['micro_recall']),('Counting MAE',a['counting']['overall_cell_mae'],b['counting']['overall_cell_mae']),('Exact five-class accuracy',a['counting']['exact_five_class_accuracy'],b['counting']['exact_five_class_accuracy']),('Predicted instances',a['total_predicted_instances'],b['total_predicted_instances']),('Duplicate candidates',a['detection']['duplicate_candidates'],b['detection']['duplicate_candidates']),('Over-counted items',a['overcount_items'],b['overcount_items']),('Under-counted items',a['undercount_items'],b['undercount_items']),('True positives',sum(a['detection']['tp']),sum(b['detection']['tp'])),('False positives',sum(a['detection']['fp']),sum(b['detection']['fp'])),('False negatives',sum(a['detection']['fn']),sum(b['detection']['fn'])),('Total-item count MAE',a['counting']['total_count_mae'],b['counting']['total_count_mae'])]
    for name,x,y in metrics:
        fmt=lambda v:str(v) if isinstance(v,int) else f'{v:.6f}'
        lines.append(f'| {name} | {fmt(x)} | {fmt(y)} | {y-x:+.6f} |')
    lines += ['', '**Exact vectors stay 6/26 (23.08%). Always-zero MAE stays 1.576923 (1.577 rounded).** B improves 4 images, leaves 17 unchanged and worsens 5, by summed absolute five-class errors. A is correspondingly better on 5, equal on 17 and worse on 4. All 17 unchanged cases have identical raw detections.',
    '**Red Bull targets recovered: 7. Additional Red Bull false positives: 6.** All 194 baseline predictions retain their matching status; none is removed or changes from TP to FP.','',
    '## 3. Per-class analysis','',
    '| Class | Count MAE A -> B | Precision A -> B | Recall A -> B | Predicted A -> B | Over-count A -> B | Under-count A -> B |','| --- | --- | --- | --- | --- | --- | --- |']
    for i,name in enumerate(NAMES):
        lines.append(f"| {name} | {a['counting']['per_class_mae'][i]:.6f} -> {b['counting']['per_class_mae'][i]:.6f} | {a['detection']['precision_per_class'][i]:.6f} -> {b['detection']['precision_per_class'][i]:.6f} | {a['detection']['recall_per_class'][i]:.6f} -> {b['detection']['recall_per_class'][i]:.6f} | {a['predicted_per_class'][i]} -> {b['predicted_per_class'][i]} | {a['overcount_items_per_class'][i]} -> {b['overcount_items_per_class'][i]} | {a['undercount_items_per_class'][i]} -> {b['undercount_items_per_class'][i]} |")
    lines += ['', '**The four non-Red-Bull classes are unchanged at the prediction level**, not merely in their aggregate counts: class IDs, boxes and confidence scores match in every image within the established numerical tolerance. Their per-class TP/FP/FN, precision/recall and counting MAE also match.',
    'The global-0.15 errors previously added to water classes and Capri-Sun are excluded here. Knoppers remains unchanged. Valser Classic/Still confusion candidates stay 4; selected-class wrong-class candidates stay 8.','',
    '## 4. Counting analysis','',
    'Absolute image/class errors fall 75 -> 72, so overall MAE falls 0.576923 -> 0.553846 (4.0%). Under-count items improve 43 -> 35, while over-count items worsen 32 -> 37. Exact count vectors remain the same six images; no exact vector is lost or gained.',
    'Total-item MAE worsens 1.961538 -> 2.076923. This metric permits cross-class cancellations and therefore can move differently from five-class MAE. The practical gain is small and specific to class-aware counting, not every counting metric.',
    'Duplicate candidates increase 1 -> 2; the additional candidate is Red Bull. Four improved images offset five one-item regressions, producing a net reduction of three absolute cell errors.',
    'Both target-free images remain empty. IMG_20181218_165652.jpg still misses all twelve selected targets with the same false Capri-Sun; class-specific confidence does not resolve that hard scene.','',
    '## 5. Red Bull analysis','',
    'Red Bull TP rises 58 -> 65 of 84 targets; recall 0.690476 -> 0.773810. FP rises 14 -> 20 and precision falls 0.805556 -> 0.764706. Red Bull MAE improves 1.461538 -> 1.346154 (7.9%). Predicted Red Bulls rise 72 -> 85, close to the dataset total of 84, but that aggregate masks image-level over/under-counting.',
    'The thirteen added Red Bull boxes consist of seven TP, one duplicate candidate and five background/localization candidates. The latter category also includes overlap with excluded source variants because evaluation GT contains only the five selected classes. Regular-on-light source-overlap candidates increase 6 -> 7. Red Bull duplicate candidates increase 1 -> 2. Regular pack sizes are merged in source labels, so separate size discrimination cannot be measured.',
    'Red Bull under-count falls 25 -> 17 (eight items), even though only seven actual targets are recovered: a localization false positive also fills a numerical deficit. Do not equate count recovery with object recovery.',
    'For the same small-target grouping used previously (area <32x32 after scaling long side to 320), matched targets increase 146/174 -> 149/174. This diagnostic does not change the evaluator.',
    '**Crowded-subset MAE worsens 0.400000 -> 0.457143** across 14 images with >=30 source objects. All targets in the four improving images were outside this crowded subset; gains therefore do not establish an advantage for dense shelves. The 24-image multi-instance subset improves 0.625000 -> 0.600000.','',
    '## 6. Image-level examples','',
    'Vectors use Red Bull / Knoppers / Valser Classic / Valser Still / Capri-Sun. Representative images were inspected alongside the stored match audit:',
    '- **IMG_20181218_170247.jpg:** Red Bull 0 -> 3 against four targets; error 6 -> 3. Three missed Red Bulls are recovered. Unlike global 0.15, no additional water-class false positives are admitted. The existing water errors remain.',
    '- **IMG_20181218_165646.jpg:** Red Bull 2 -> 4 against five; two genuine recoveries, error 7 -> 5. The three wrong-class water/Capri-Sun additions seen with global 0.15 are not accepted.',
    '- **IMG_20181218_171802.jpg:** Red Bull 1 -> 2 against five, error 5 -> 4; one target recovered without the additional Classic false positive seen at global 0.15.',
    '- **IMG_20190206_170716.jpg:** Red Bull 3 -> 5 against five, error 5 -> 3. One added Red Bull is a TP, the other a localization/background FP, so the now-correct count still hides a missed target. Existing water/Capri errors remain unchanged.',
    '- **DSC01659.png:** crowded shelf; Red Bull 4 -> 5 against two, due to a new duplicate at confidence 0.179. Error worsens 5 -> 6.',
    '- **IMG_20181218_171805.jpg:** no regular Red Bull targets, but B adds one false Red Bull; error 1 -> 2. Class-specific filtering cannot avoid errors within the lowered class.',
    '- **IMG_20181218_170243.jpg:** the formerly exact vector remains exact. The extra Capri-Sun admitted by global 0.15 is absent.',
    '', 'Every validation image is linked below. Panels show ground truth / A / B. Error is sum of absolute five-class count errors.','',
    '| Image | Truth | A | B | Error A -> B |','| --- | --- | --- | --- | --- |']
    for r in c['images']:
        lines.append(f"| [{r['image']}](visuals/class_confidence_001_{Path(r['image']).stem}.jpg) | {r['truth']} | {r['a_counts']} | {r['b_counts']} | {r['a_sum_absolute_error']} -> {r['b_sum_absolute_error']} |")
    lines += ['', '## 7. Conclusion','',
    '**Retain B provisionally for further development when optimizing five-class MAE**, while preserving A as the comparison baseline. The Red Bull-only policy captures seven recoveries without changing other classes, modestly improves overall MAE, and preserves exact vectors. It avoids thirteen non-Red-Bull false positives introduced by the earlier global 0.15 policy, but also does not recover its one additional Still TP.',
    'This is a mixed result: five images regress versus four improving, precision falls, duplicates and variant confusion increase, crowded-scene MAE and total-item MAE worsen, and exact accuracy stays low. The three-cell net improvement on 26 repeatedly inspected validation images is insufficient evidence for an unconditional deployment choice. No existing frozen baseline configuration has been changed.',
    '## 8. Single next controlled experiment (proposal only)','',
    '**Compare these exact A/B policies on an additional, independently annotated validation cohort from previously unseen machines/scenes**, with representation of crowded Red Bull shelves and target-free images. Freeze the cohort before scoring; exclude near-duplicates of existing scenes. Keep weights, both policies, resolution, NMS, preprocessing and evaluator fixed, and compare paired class-count errors, exact counts, variant errors and duplicates. This checks whether the small aggregate gain and crowded-scene regression generalize, rather than continuing threshold tuning on the same 26 images. Store the additional cohort separately; do not alter the existing frozen dataset/split or touch its test set. No such data collection or evaluation has been performed in this task.','',
    '## Validation and reproducibility','',
    f'**34 tests passed**: all 32 existing tests plus two class-confidence tests. All **{protected} protected artifacts** retain their hashes; all frozen dataset image/label/config hashes also match. Earlier experiment outputs and evaluator source remain unchanged.',
    'No retraining, checkpoint changes, dataset/split changes or test-set evaluation occurred. Exactly two validation inference passes followed the synthetic sanity check. Dataset hash verification includes file integrity checks across splits, not test inference or metric evaluation.',
    'Evidence: [preservation hashes](class_confidence_001_preservation.json), [inference log](class_confidence_001_inference.log), [analysis log](class_confidence_001_analysis.log), [test log](class_confidence_001_tests.log).','',
    '```powershell', '.\\.venv\\Scripts\\python.exe -m src.class_confidence_experiment', '.\\.venv\\Scripts\\python.exe -m src.analyze_class_confidence', '.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v', '.\\.venv\\Scripts\\python.exe -m src.report_class_confidence', '```',
    'The inference entry point refuses to overwrite the completed experiment. Analysis/report commands regenerate only this experiment from saved predictions.']
    (ROOT/'reports/CLASS_CONFIDENCE_001_RESULTS.md').write_text('\n'.join(lines)+'\n')
    verify_protected()


if __name__=='__main__':
    main()
