"""Report saved confidence experiment results; no inference or training."""
import json
from pathlib import Path
from src.nms_experiment import ROOT
from src.confidence_experiment import verify_protected
from src.preview_yolo import NAMES


def main():
    read=lambda n:json.loads((ROOT/'reports'/n).read_text())
    a,b=read('confidence_001_a.json'),read('confidence_001_b.json')
    c,s=read('confidence_001_comparison.json'),read('confidence_001_setup.json')
    protected=verify_protected()
    tests=(ROOT/'reports/confidence_001_tests.log').read_text()
    assert 'Ran 32 tests' in tests and tests.rstrip().endswith('OK')
    lines=['# CONFIDENCE_001: confidence 0.25 vs 0.15','',
    '**Decision: retain confidence 0.25 for general five-class counting.** Lowering confidence recovers targets and improves Red Bull MAE, but increases overall per-class counting error, false positives and duplicates, and reduces exact counts. The recall/counting tradeoff is real; 0.15 is not an overall improvement.','',
    '## 1. Experiment setup','',
    'Only confidence changes: A=0.25, B=0.15. Both runs use the frozen BASELINE_002 checkpoint from the completed 30-epoch training, the same 26 validation images, five-class mapping, CPU, resolution 320 and class-aware NMS IoU 0.50. No training, dataset changes, test evaluation, extra model or additional inference experiment.',
    f"Checkpoint: `{s['checkpoint']}`.",f"Checkpoint SHA-256: `{s['checkpoint_sha256']}`.",f"Dataset manifest SHA-256: `{s['dataset_manifest_sha256']}`.",
    f"Common prediction arguments: `{json.dumps(s['common_arguments'],sort_keys=True)}`.",
    f"Runtime: Ultralytics {s['ultralytics']}; PyTorch {s['torch']}. Each run loads the same weights and predicts the same validation images in the same order. Rectangular resizing/letterboxing, one image per call, max_det=300, no augmentation.",
    'Evaluation directly imports the unchanged NMS_001 `match_detections` and `summarize` functions and shared `count_classes`. The fresh 0.25 run reproduces RESOLUTION_001 A predictions within the established tolerance (1e-3 pixels / 1e-6 confidence). No threshold sweep or class-specific filtering was performed.',
    'Detection precision/recall are **custom micro-averaged fixed-threshold metrics**, with confidence-ordered, same-class, one-to-one GT matching at evaluation IoU >=0.50. They are not standard Ultralytics F1-selected validation metrics. No model.val() or AP pass was run.',
    'Counting MAE averages absolute errors over 26 x 5 image/class cells. Exact accuracy requires all five counts to match. Over/under-count items sum positive/negative count errors per image/class; they differ from FP/FN because errors can cancel. Duplicate candidates retain the NMS_001 annotation-overlap diagnostic, rather than counting every overlapping prediction.',
    f"Run durations including loading and diagnostics: A {a['duration_seconds']:.3f}s, B {b['duration_seconds']:.3f}s. These are not controlled latency benchmarks.",
    'Evidence: [setup](confidence_001_setup.json), [0.25 predictions](confidence_001_a.json), [0.15 predictions](confidence_001_b.json), [comparison](confidence_001_comparison.json).','',
    '## 2. Results','',
    '| Metric | Confidence 0.25 | Confidence 0.15 | B - A |','| --- | ---: | ---: | ---: |']
    values=[('Precision',a['detection']['micro_precision'],b['detection']['micro_precision']),('Recall',a['detection']['micro_recall'],b['detection']['micro_recall']),('Counting MAE',a['counting']['overall_cell_mae'],b['counting']['overall_cell_mae']),('Exact five-class accuracy',a['counting']['exact_five_class_accuracy'],b['counting']['exact_five_class_accuracy']),('Predicted instances',a['total_predicted_instances'],b['total_predicted_instances']),('Duplicate candidates',a['detection']['duplicate_candidates'],b['detection']['duplicate_candidates']),('Over-counted items',a['overcount_items'],b['overcount_items']),('Under-counted items',a['undercount_items'],b['undercount_items']),('TP',sum(a['detection']['tp']),sum(b['detection']['tp'])),('FP',sum(a['detection']['fp']),sum(b['detection']['fp'])),('FN',sum(a['detection']['fn']),sum(b['detection']['fn'])),('Total-item count MAE',a['counting']['total_count_mae'],b['counting']['total_count_mae'])]
    for name,x,y in values:
        fmt=lambda v:str(v) if isinstance(v,int) else f'{v:.6f}'
        lines.append(f'| {name} | {fmt(x)} | {fmt(y)} | {y-x:+.6f} |')
    lines += ['', '**Exact counts: 6/26 (23.08%) -> 5/26 (19.23%).** Always-zero MAE stays **1.576923 (1.577 rounded)**; always-zero exact accuracy is 2/26.',
    '**Relative to 0.25, 0.15 improves 2 images, leaves 16 unchanged and worsens 8**, measured by sum of absolute five-class count errors. Conversely, 0.25 is better on 8, equal on 16 and worse on 2. Only 13 images have identical raw predictions; three more retain the same count error despite changed predictions.','',
    '## 3. Counting analysis','',
    'All 194 predictions from A remain in B with unchanged matching status. There are **27 newly admitted predictions: 8 true positives and 19 false positives** (11 background/localization, 7 wrong-class candidates, 1 duplicate candidate). All 160 previously matched targets remain matched; 8 previously missed targets are recovered, leaving 37 misses.',
    'Under-counted items fall 43 -> 32, but over-counted items rise 32 -> 48. Absolute image/class errors rise 75 -> 80, producing MAE 0.576923 -> 0.615385 (+6.7%). Under-count reduction exceeds newly matched targets because some false positives fill a numerical count deficit. Do not interpret every lower count error as a recovered product.',
    'Duplicates rise 1 -> 2. The new duplicate is a regular Red Bull candidate in DSC01659.png. One formerly exact vector becomes incorrect (IMG_20181218_170243.jpg); no previously incorrect vector becomes exact. Total-item MAE improves slightly (1.961538 -> 1.923077), but this permits cross-class error cancellation and does not outweigh worse five-class counts.',
    '**No correct detection becomes a false positive.** The retained-box matching audit finds zero status changes and zero removed predictions. The observed harm is newly admitted false positives, including on an image whose counts were previously correct.',
    'The two target-free images (IMG_20181218_165648.jpg and IMG_20181218_165657.jpg) remain prediction-free. There are no positive images with zero predictions at 0.25. The hard positive IMG_20181218_165652.jpg still misses all 12 targets and returns the same false Capri-Sun at both thresholds.','',
    '## 4. Per-class analysis','',
    '| Class | MAE A -> B | Precision A -> B | Recall A -> B | Predicted A -> B | Over-count A -> B | Under-count A -> B |','| --- | --- | --- | --- | --- | --- | --- |']
    for i,name in enumerate(NAMES):
        lines.append(f"| {name} | {a['counting']['per_class_mae'][i]:.6f} -> {b['counting']['per_class_mae'][i]:.6f} | {a['detection']['precision_per_class'][i]:.6f} -> {b['detection']['precision_per_class'][i]:.6f} | {a['detection']['recall_per_class'][i]:.6f} -> {b['detection']['recall_per_class'][i]:.6f} | {a['predicted_per_class'][i]} -> {b['predicted_per_class'][i]} | {a['overcount_items_per_class'][i]} -> {b['overcount_items_per_class'][i]} | {a['undercount_items_per_class'][i]} -> {b['undercount_items_per_class'][i]} |")
    lines += ['', '- **Red Bull:** seven extra true positives and six extra false positives. MAE improves 1.461538 -> 1.346154, but source-light overlap candidates rise 6 -> 7 and one duplicate is added. Source labels merge regular pack sizes; size discrimination cannot be evaluated separately.',
    '- **Knoppers:** unchanged predictions, recall and counting error; lowering confidence does not recover its seven missed targets.',
    '- **Valser Classic:** no new true positives, four new false positives; MAE worsens. A smaller numeric under-count does not mean improved recognition.',
    '- **Valser Still:** one new true positive, four new false positives; recall improves slightly but MAE worsens.',
    '- **Capri-Sun:** recall already equals 1.000 at 0.25. Lower confidence adds five false positives and no true positives, increasing MAE 0.346154 -> 0.538462.',
    'Selected-class wrong-class candidates increase 8 -> 15; Classic/Still confusion candidates 4 -> 5; regular predictions overlapping source-labeled light variants 6 -> 7. These diagnostic counts may overlap other categories and are not additive totals.','',
    '## 5. Image-level and subset analysis','',
    '| Subset | Images | MAE 0.25 | MAE 0.15 | Exact accuracy 0.25 | Exact accuracy 0.15 |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for key in ['crowded_30plus_source_objects','multi_instance_2plus']:
        r=c['cohorts'][key]
        lines.append(f"| {key} | {len(r['images'])} | {r['A']['overall_cell_mae']:.6f} | {r['B']['overall_cell_mae']:.6f} | {r['A']['exact_five_class_accuracy']:.6f} | {r['B']['exact_five_class_accuracy']:.6f} |")
    lines += ['', 'Crowded means >=30 source objects including non-targets; multi-instance means >=2 of one selected class. Definitions match previous experiments.',
    'For the unchanged small-target diagnostic (GT area <32x32 after scaling the long image side to 320), 146/174 -> 150/174 targets are matched (recall 0.839080 -> 0.862069). Four small targets are recovered, but crowded-subset MAE worsens 0.400000 -> 0.471429. This grouping is not COCO AP-small.',
    'Representative changes; vectors use Red Bull / Knoppers / Classic / Still / Capri-Sun:',
    '- **IMG_20181218_170247.jpg (visually inspected):** three of four missed Red Bulls are recovered at confidence 0.232, 0.204 and 0.189. Counts change [0,0,2,2,0] -> [3,0,3,3,0] against [4,0,1,1,0]. Extra water-class false positives limit the net error improvement to 6 -> 5.',
    '- **IMG_20181218_165646.jpg (visually inspected):** two regular Red Bulls are recovered; three additional wrong-class predictions label Red Bull-region objects as water/Capri-Sun. Error improves 7 -> 4, partly through count cancellation. The water count gains do not represent recovered water targets.',
    '- **DSC01659.png (visually inspected):** a new Red Bull duplicate at confidence 0.179 increases the count 4 -> 5 against two. A crowded-scene regression, error 5 -> 6.',
    '- **IMG_20181218_170243.jpg (visually inspected):** an added Capri-Sun false positive at 0.164 turns the exact vector [0,3,0,0,2] into [0,3,0,0,3]. Existing correct detections remain correct.',
    '- **IMG_20181218_171802.jpg:** a recovered Red Bull is offset by a false Classic detection; total class-count error remains five.',
    '- **IMG_20190402_110254.jpg:** one missed Still is recovered, accompanied by an extra Still false positive; Still count 0 -> 2 around truth one leaves the image error unchanged.',
    '- **IMG_20190206_170714.jpg:** two added false Capri-Suns overlap other selected products; error worsens 6 -> 8.',
    '- **IMG_20181218_171805.jpg:** a five-target image gains a false Red Bull on top of its existing false Capri-Sun; error 1 -> 2. Both target-free images remain clean.',
    '', 'All 26 comparisons are linked below. Each panel shows ground truth / 0.25 / 0.15. Error is summed absolute class-count error.','',
    '| Image | Truth | A counts | B counts | Error A -> B |','| --- | --- | --- | --- | --- |']
    for r in c['images']:
        lines.append(f"| [{r['image']}](visuals/confidence_001_{Path(r['image']).stem}.jpg) | {r['truth']} | {r['a_counts']} | {r['b_counts']} | {r['a_sum_absolute_error']} -> {r['b_sum_absolute_error']} |")
    lines += ['', '## 6. Conclusion','',
    '**Retain confidence 0.25 at 320px and NMS IoU 0.50 for further development.** For the stated objective of five-class visible-item counting, lower overall MAE, fewer false positives/duplicates and more exact vectors favor 0.25. Confidence 0.15 offers higher recall and better Red Bull MAE, but worsens three other class MAEs and eight images while improving only two.',
    'This is a modest aggregate counting difference and a clear recall/precision tradeoff, not proof that 0.15 is universally inferior. The validation set is only 26 images across five scene groups, and repeated development comparisons do not provide independent generalization evidence. No test result is consulted.','',
    '## 7. Single next controlled experiment (not run)','',
    '**Compare uniform confidence 0.25 against Red Bull-only confidence 0.15, with all other classes held at 0.25.** Keep the same frozen weights, 320px, class-aware NMS 0.50, validation images and evaluator. This isolates the only class whose counting MAE improved here, while avoiding the measured water/Capri-Sun false-positive additions. The class-specific cutoff is the sole changed factor; do not sweep cutoffs or retrain. Measure overall MAE, exact vectors, Red Bull variant errors and duplicates before deciding whether the modest class gain justifies the extra configuration. This policy has not been evaluated in this task.','',
    '## Validation and reproducibility','',
    f'**32 tests passed:** the complete existing 31-test suite plus a confidence-protocol/artifact test. All **{protected} protected artifacts** retain their SHA-256 hashes, including BASELINE_001/002, NMS_001, RESOLUTION_001, and existing evaluation code. All frozen dataset image/label/config hashes were verified unchanged.',
    'Exactly two validation inference passes were performed. No retraining, checkpoint mutation, dataset/split/mapping change or test-set evaluation occurred. Dataset integrity verification hashes files in all splits; it performs no test inference or test metric evaluation.',
    'Evidence: [preservation snapshot](confidence_001_preservation.json), [inference log](confidence_001_inference.log), [analysis log](confidence_001_analysis.log), [tests](confidence_001_tests.log).','',
    '```powershell', '.\\.venv\\Scripts\\python.exe -m src.confidence_experiment', '.\\.venv\\Scripts\\python.exe -m src.analyze_confidence', '.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v', '.\\.venv\\Scripts\\python.exe -m src.report_confidence', '```',
    'The inference command refuses to overwrite this completed experiment. Analysis and reporting read saved predictions and regenerate only CONFIDENCE_001 artifacts.']
    (ROOT/'reports/CONFIDENCE_001_RESULTS.md').write_text('\n'.join(lines)+'\n')
    verify_protected()


if __name__=='__main__':
    main()
