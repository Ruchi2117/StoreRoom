"""Render measured NMS comparison, with AP limitations and explicit absence of harms."""
import json
from src.nms_experiment import ROOT, NAMES, protect


def read(name):
    return json.loads((ROOT/'reports'/name).read_text())


def main():
    setup=read('nms_001_setup.json')
    a,b=read('nms_001_a.json'),read('nms_001_b.json')
    comparison=read('nms_001_comparison.json')
    protected=protect()
    lines=['# NMS_001: controlled fixed-confidence post-processing experiment','',
           '**Result:** NMS IoU 0.50 improves counting on these validation images without losing any previously matched annotated target. The evidence supports a post-processing cause for most observed duplicate candidates; substantial non-duplicate errors remain.','',
           '## Exact experimental setup','',
           f"Frozen BASELINE_002 checkpoint: `{setup['checkpoint']}`.",
           f"Checkpoint SHA-256: `{setup['checkpoint_sha256']}`.",
           f"Dataset manifest SHA-256: `{setup['dataset_manifest_sha256']}`.",
           'Same 26 validation images, five classes, CPU, image size 320, one image per prediction call, rectangular preprocessing, confidence 0.25, class-aware NMS, max_det=300, no augmentation. Run A uses NMS IoU 0.70; Run B uses 0.50. Each run loaded the identical frozen weights and performed fresh inference on all validation images.',
           'No training, weight changes, threshold sweep, dataset changes or test evaluation occurred. Run A reproduces BASELINE_002 validation detections, confidence scores and boxes within the recorded numerical tolerance (1e-3 pixels and 1e-6 confidence).',
           f"Inference-run durations, including loading and diagnostics: A {a['duration_seconds']:.3f}s; B {b['duration_seconds']:.3f}s. These sequential timings are not a controlled speed benchmark.",
           'Setup and outputs: [setup JSON](nms_001_setup.json), [Run A](nms_001_a.json), [Run B](nms_001_b.json), [image comparison JSON](nms_001_comparison.json).','',
           '## Metric definitions and AP decision','',
           'Detection P/R below are **custom micro-averaged fixed-threshold metrics**, not standard Ultralytics validation P/R at its F1-optimal operating point. Predictions are matched in confidence order, same class, one-to-one, at evaluation IoU >= 0.50. Evaluation matching IoU and NMS IoU are separate concepts. Per-class P/R use the same matching rule.',
           'A duplicate candidate is an unmatched prediction overlapping an already-matched same-class ground-truth box at IoU >= 0.50. Wrong-class candidates overlap a different selected class at that threshold. These are annotation-based diagnostic categories; images were also inspected.',
           '**mAP50 and mAP50-95: not reported.** Full-curve AP is not directly comparable to the earlier confidence-floor-0.001 validation after deliberately discarding predictions below 0.25. Computing confidence-truncated AP is possible but is unnecessary for this fixed-operating-point counting decision. No standard Ultralytics `model.val()` call or lower-confidence pass was made in this experiment.',
           'Counting MAE averages absolute errors over 26 x 5 image/class cells. Exact count accuracy requires the entire five-class vector to match. Over-count items sum positive image/class count errors; under-count items sum their negative magnitudes. These count errors can differ from FP/FN because mistakes can cancel within a class count.','',
           '## Overall results','',
           '| Metric | A: IoU 0.70 | B: IoU 0.50 | B - A |','| --- | ---: | ---: | ---: |']
    values=[('Fixed-threshold micro precision',a['detection']['micro_precision'],b['detection']['micro_precision']),
            ('Fixed-threshold micro recall',a['detection']['micro_recall'],b['detection']['micro_recall']),
            ('True positives',sum(a['detection']['tp']),sum(b['detection']['tp'])),
            ('False positives',sum(a['detection']['fp']),sum(b['detection']['fp'])),
            ('False negatives',sum(a['detection']['fn']),sum(b['detection']['fn'])),
            ('Overall counting MAE',a['counting']['overall_cell_mae'],b['counting']['overall_cell_mae']),
            ('Total-item counting MAE',a['counting']['total_count_mae'],b['counting']['total_count_mae']),
            ('Exact five-class count accuracy',a['counting']['exact_five_class_accuracy'],b['counting']['exact_five_class_accuracy']),
            ('Total predicted instances',a['total_predicted_instances'],b['total_predicted_instances']),
            ('Duplicate candidates',a['detection']['duplicate_candidates'],b['detection']['duplicate_candidates']),
            ('Over-count items',a['overcount_items'],b['overcount_items']),
            ('Under-count items',a['undercount_items'],b['undercount_items']),
            ('Images with any over-count',a['images_with_overcount'],b['images_with_overcount']),
            ('Images with any under-count',a['images_with_undercount'],b['images_with_undercount'])]
    for name,x,y in values:
        lines.append(f'| {name} | {x:.6f} | {y:.6f} | {y-x:+.6f} |')
    lines += ['',f"Always-zero MAE remains **{a['zero_baseline']['overall_cell_mae']:.6f} (1.577 rounded)**. Exact vectors remain **6/26** for both runs; the always-zero baseline is 2/26.",
              'Cell MAE improves by about 10.7%. Six images improve, none worsen, and twenty retain the same count error. Nineteen images have identical raw predictions.','',
              '## Per-class detection and counting','',
              '| Class | Precision A -> B | Recall A -> B | Count MAE A -> B | Predicted A -> B | Over-count items A -> B | Under-count items A -> B |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for i,name in enumerate(NAMES):
        lines.append(f"| {name} | {a['detection']['precision_per_class'][i]:.6f} -> {b['detection']['precision_per_class'][i]:.6f} | {a['detection']['recall_per_class'][i]:.6f} -> {b['detection']['recall_per_class'][i]:.6f} | {a['counting']['per_class_mae'][i]:.6f} -> {b['counting']['per_class_mae'][i]:.6f} | {a['predicted_per_class'][i]} -> {b['predicted_per_class'][i]} | {a['overcount_items_per_class'][i]} -> {b['overcount_items_per_class'][i]} | {a['undercount_items_per_class'][i]} -> {b['undercount_items_per_class'][i]} |")
    lines += ['', 'Knoppers is unchanged. Red Bull, both Valser variants and Capri-Sun have less over-counting, with no per-class increase in under-counting.','',
              '## Duplicate and legitimate-neighbor analysis','',
              'Eight of nine duplicate candidates are eliminated. One additional localization/background false positive is removed. A tenth removed box is a true-positive box replaced by a different true-positive box for the same target; therefore net predictions decrease by nine, not ten.','',
              'For every image, the set of matched ground-truth indices is unchanged. No previously matched legitimate neighboring product becomes unmatched. This is supported by the same-class matching audit and inspected side-by-side images; it is evidence for these 26 images, not a guarantee for all dense shelves.','',
              'The non-monotonic case is `IMG_20190430_111949.jpg`: Run B removes an A true-positive Red Bull box and admits another Red Bull box matching the same ground-truth item. Counts and recall stay unchanged. Greedy NMS at a lower threshold can alter a suppression chain, so B need not be a strict subset of A.','',
              '| Requested case | Observed result |','| --- | --- |',
              '| Correct duplicate removal | Five images lose duplicate candidates without losing any GT match. In IMG_20181218_170247.jpg, Classic/Still predictions fall from 4/3 to 2/2 against truth 1/1; three duplicates are removed, but extra wrong-class/localization errors remain. |',
              '| Incorrect suppression of legitimate neighboring products | None observed: no image loses a GT match, and under-count errors do not increase. The box-replacement case above was checked rather than counted as a lost neighbor. |',
              '| No meaningful effect | Nineteen images have identical predictions; DSC01658.png still predicts three regular Red Bulls when the selected regular class count is zero. IMG_20181218_165652.jpg still misses all twelve targets and predicts one false Capri-Sun. |',
              '| Changed wrong-class detection | No selected-class confusion candidate was removed or added. Retained boxes are not relabeled by class-aware NMS. Valser Classic/Still and regular/light mistakes remain. |',
              '| Correct count becomes incorrect | None observed, either for the entire five-class vector or for an individual image/class count that was correct in A. |','',
              'Changed images (vectors use Red Bull / Knoppers / Classic / Still / Capri-Sun):','',
              '| Image | Truth | A | B | Sum absolute count error A -> B |','| --- | --- | --- | --- | --- |']
    for r in comparison['images']:
        if not r['raw_predictions_unchanged']:
            lines.append(f"| {r['image']} | {r['truth']} | {r['a_counts']} | {r['b_counts']} | {r['a_sum_absolute_error']} -> {r['b_sum_absolute_error']} |")
    lines += ['', '### Crowded and multi-instance subsets','',
              '| Subset | Images | Cell MAE A -> B | Exact-vector accuracy A -> B |','| --- | ---: | --- | --- |']
    for name,c in comparison['cohorts'].items():
        lines.append(f"| {name} | {len(c['images'])} | {c['A']['overall_cell_mae']:.6f} -> {c['B']['overall_cell_mae']:.6f} | {c['A']['exact_five_class_accuracy']:.6f} -> {c['B']['exact_five_class_accuracy']:.6f} |")
    lines += ['', 'Crowded means at least 30 original source-annotated objects, including non-target classes. Multi-instance means at least two items of any selected class. These definitions match the previous comparison.',
              f"Selected-class confusion candidates: {comparison['identity_errors']['A']['wrong_class_candidates']} -> {comparison['identity_errors']['B']['wrong_class_candidates']}; Classic/Still candidates: {comparison['identity_errors']['A']['valser_classic_still_candidates']} -> {comparison['identity_errors']['B']['valser_classic_still_candidates']}; regular predictions overlapping source Red Bull light: {comparison['identity_errors']['A']['regular_on_light_candidates']} -> {comparison['identity_errors']['B']['regular_on_light_candidates']}.",
              'Regular Red Bull pack sizes are merged in the source labels, so size discrimination cannot be evaluated separately.','',
              '## Inspected image comparisons','',
              'Ground truth / Run A / Run B panels were inspected for duplicate removal, persistent identity errors and the TP replacement.']
    for p in sorted((ROOT/'reports/visuals').glob('nms_001_page_*.jpg')):
        lines.append(f'- [{p.stem}](visuals/{p.name})')
    lines += ['', '## Decision and next experiment','',
              '**Prefer 0.50 as the validation-supported NMS setting for further development.** This decision is based on fewer duplicates and over-counted items, lower counting MAE, unchanged matched-target recall, no lost legitimate-neighbor matches and no count regressions—not mAP. BASELINE_002 artifacts and its saved settings remain unchanged.',
              'The removal of eight of nine duplicate candidates supports that most measured duplicates are sensitive to post-processing. However, only nine net false positives disappear; 34 false positives and 45 missed annotated instances remain. Exact count accuracy stays at 6/26. Stronger suppression did not solve recognition or missed-product errors.',
              '**Single next experiment, proposed only:** compare inference image size 320 versus 640 using the same frozen BASELINE_002 weights, confidence 0.25 and NMS IoU 0.50, on validation only. The unchanged Red Bull variant mistakes, water-class confusions and 45 misses justify testing whether more image detail improves these errors. Keep all other settings fixed; measure per-class recall, counting MAE, identity confusions, duplicates and CPU latency. This is a resolution hypothesis, not a claim that resolution will fix the errors. No retraining, additional model, threshold sweep or test evaluation is part of this proposal.',
              'The conclusion is limited to 26 validation images across five machine groups; it does not establish production reliability.','',
              '## Verification and reproduction','',
              f'All {protected} protected BASELINE_001/002 and shared frozen artifacts retain their hashes. The existing suite plus NMS-specific tests passed 30 tests. Raw predictions and matching decisions are retained for every image. No BASELINE_002 artifact was modified.',
              '```powershell',
              '.\\.venv\\Scripts\\python.exe -m src.nms_experiment',
              '.\\.venv\\Scripts\\python.exe -m src.analyze_nms',
              '.\\.venv\\Scripts\\python.exe -m src.report_nms',
              '.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v',
              '```','',
              'The inference command refuses to overwrite NMS_001. Analysis and reporting regenerate only NMS_001 outputs. The preservation snapshot and hashes are in `nms_001_preservation.json`; test output is in `nms_001_tests.log`.']
    (ROOT/'reports/NMS_001_RESULTS.md').write_text('\n'.join(lines)+'\n')
    protect()


if __name__=='__main__':
    main()
