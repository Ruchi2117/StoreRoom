"""Build the final augmentation report from saved experiment evidence."""
import json
from pathlib import Path
from src.nms_experiment import ROOT
from src.train_augmentation import verify_protected, AUGMENTATION
from src.preview_yolo import NAMES


def main():
    read=lambda n:json.loads((ROOT/'reports'/n).read_text())
    a,b=[read(f'augmentation_001_{t}.json') for t in ['a','b']]
    c=read('augmentation_001_comparison.json')
    s=read('augmentation_001_setup.json')
    training=read('augmentation_001_training.json')
    history=read('augmentation_001_training_summary.json')
    discussion=read('augmentation_001_discussion.json')
    protected=verify_protected()
    log=(ROOT/'reports/augmentation_001_tests.log').read_text()
    assert 'Ran 36 tests' in log and log.rstrip().endswith('OK')
    lines=['# AUGMENTATION_001: controlled training augmentation comparison','',discussion['summary'],'',
    '## 1. Experiment setup','',
    'A is the completed 30-epoch no-augmentation BASELINE_002 run and its frozen best checkpoint. Its training was not repeated; the specified checkpoint is reused and freshly evaluated. B is one new 30-epoch run from the identical original pretrained yolo11n.pt, not from A. No other training configuration was tried.',
    f"Initial weights SHA-256: `{training['initial_weights_sha256']}`.",
    f"Frozen dataset manifest SHA-256: `{training['dataset_manifest_sha256']}`.",
    'Same 123 training / 26 validation / 26 held-out test split, class mapping, seed 42, CPU, image size 320, batch 4, AdamW lr0=0.001, lrf=0.01, momentum=0.9, weight decay=0.0005, warmup 1 epoch, deterministic=true. Test data was not evaluated.',
    'Augmentation parameters were written before training to this report and the immutable-for-this-run configuration [augmentation_001.yaml](../configs/augmentation_001.yaml). The changed controls are:',
    '| Control | A | B | Interpretation |','| --- | ---: | ---: | --- |']
    meanings={'hsv_s':'Moderate saturation jitter; gain 0.10','hsv_v':'Moderate brightness jitter; gain 0.15','translate':'Translation up to 3%','scale':'Scale range about 0.90-1.10','degrees':'Rotation up to +/-3 degrees'}
    for k,v in AUGMENTATION.items():
        lines.append(f'| {k} | 0 | {v} | {meanings[k]} |')
    lines += ['', 'Hue jitter, horizontal/vertical flips, shear, perspective, mosaic, mixup, cutmix and copy-paste remain zero; close_mosaic=0. All other trainer settings remain identical apart from the separate output directory. Only stock Ultralytics augmentation controls are used; no custom augmentation code. This tests the bundle as one variable and cannot identify which constituent transform caused an effect.',
    'Model selection retains the baseline training-internal validation settings (conf=0.001, NMS IoU=0.70). Stock best-checkpoint fitness is mAP50-95; no counting-based epoch selection or augmentation tuning is performed. The final fixed-threshold comparison is separate from these training-internal metrics.',
    'Both final models use unchanged class-score gating before NMS: Red Bull confidence 0.15, all other classes 0.25, 320px, CPU, class-aware NMS IoU 0.50, rectangular preprocessing, batch=1, max_det=300, no inference augmentation. The frozen evaluator/counting functions are unchanged. A reproduces CLASS_CONFIDENCE_001 B predictions within the existing 1e-3-pixel / 1e-6-confidence tolerance.',
    'Final precision/recall are custom micro metrics at these fixed cutoffs, using confidence-ordered same-class one-to-one GT matching at IoU >=0.50. Counting MAE averages absolute errors over 26 x 5 cells. Exact accuracy requires the entire five-class vector. Duplicate candidates use the prior GT-overlap diagnostic; over/under-count sums positive/negative cell errors, so count errors can differ from FP/FN.',
    'Evidence: [training record](augmentation_001_training.json), [inference setup](augmentation_001_setup.json), [A predictions](augmentation_001_a.json), [B predictions](augmentation_001_b.json), [comparison](augmentation_001_comparison.json).','',
    '## 2. Training comparison','',
    '| Model | Duration (s) | Final epoch | Best epoch | Best training-internal mAP50 | Best training-internal mAP50-95 |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for tag,h in history.items():
        lines.append(f"| {tag} | {h['duration_seconds']:.3f} | {h['final_epoch']} | {h['best_epoch']} | {h['best']['metrics/mAP50(B)']:.6f} | {h['best']['metrics/mAP50-95(B)']:.6f} |")
    lines += ['', 'Best epoch is reconstructed from the last maximum validation fitness in results.csv and checked against the saved best checkpoint metric. Exported checkpoints have epoch=-1, so that field is not treated as the selected epoch.',
    '| Run/epoch | Train box | Train cls | Train DFL | Val box | Val cls | Val DFL |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for tag,h in history.items():
        for phase in ['best','final']:
            vals=[h[phase][k] for k in ['train/box_loss','train/cls_loss','train/dfl_loss','val/box_loss','val/cls_loss','val/dfl_loss']]
            lines.append(f"| {tag} {phase} ({int(h[phase]['epoch'])}) | "+' | '.join(f'{v:.6f}' for v in vals)+' |')
    for tag,h in history.items():
        lines += ['',f"{tag} checkpoint: `{h['checkpoint']}`; SHA-256 `{h['checkpoint_sha256']}`.",'']
    lines += ['![Training and validation loss curves](visuals/augmentation_001_loss_curves.png)',
    'Full epoch histories: [A results.csv](../runs/baseline_002/results.csv), [B results.csv](../runs/augmentation_001/results.csv). Training losses with augmented images and unaugmented images are not identically distributed; final fixed-inference metrics are the practical comparison.','',
    '## 3. Validation results','',
    '| Metric | A: no augmentation | B: moderate augmentation | B - A |','| --- | ---: | ---: | ---: |']
    pairs=[('Precision',a['detection']['micro_precision'],b['detection']['micro_precision']),('Recall',a['detection']['micro_recall'],b['detection']['micro_recall']),('Counting MAE',a['counting']['overall_cell_mae'],b['counting']['overall_cell_mae']),('Exact five-class accuracy',a['counting']['exact_five_class_accuracy'],b['counting']['exact_five_class_accuracy']),('Predicted instances',a['total_predicted_instances'],b['total_predicted_instances']),('Duplicate candidates',a['detection']['duplicate_candidates'],b['detection']['duplicate_candidates']),('Over-count items',a['overcount_items'],b['overcount_items']),('Under-count items',a['undercount_items'],b['undercount_items']),('TP',sum(a['detection']['tp']),sum(b['detection']['tp'])),('FP',sum(a['detection']['fp']),sum(b['detection']['fp'])),('FN',sum(a['detection']['fn']),sum(b['detection']['fn'])),('Total-item count MAE',a['counting']['total_count_mae'],b['counting']['total_count_mae'])]
    for name,x,y in pairs:
        lines.append(f'| {name} | {x:.6f} | {y:.6f} | {y-x:+.6f} |')
    lines += ['',f"B improves {c['improved']} images, leaves {c['unchanged']} unchanged, and worsens {c['worsened']} by summed absolute five-class errors. Always-zero MAE remains 1.576923 (1.577 rounded).",'',
    '## 4. Counting analysis','',discussion['counting'],'',
    '## 5. Per-class analysis','',
    '| Class | MAE A -> B | Precision A -> B | Recall A -> B | Over-count A -> B | Under-count A -> B |','| --- | --- | --- | --- | --- | --- |']
    for i,name in enumerate(NAMES):
        lines.append(f"| {name} | {a['counting']['per_class_mae'][i]:.6f} -> {b['counting']['per_class_mae'][i]:.6f} | {a['detection']['precision_per_class'][i]:.6f} -> {b['detection']['precision_per_class'][i]:.6f} | {a['detection']['recall_per_class'][i]:.6f} -> {b['detection']['recall_per_class'][i]:.6f} | {a['overcount_items_per_class'][i]} -> {b['overcount_items_per_class'][i]} | {a['undercount_items_per_class'][i]} -> {b['undercount_items_per_class'][i]} |")
    lines += ['',discussion['classes'],'','## 6. Failure analysis','',discussion['failures'],'',
    '| Subset | Images | MAE A -> B | Exact accuracy A -> B |','| --- | ---: | --- | --- |']
    for key in ['crowded_30plus_source_objects','multi_instance_2plus']:
        r=c['cohorts'][key]
        lines.append(f"| {key} | {len(r['images'])} | {r['A']['overall_cell_mae']:.6f} -> {r['B']['overall_cell_mae']:.6f} | {r['A']['exact_five_class_accuracy']:.6f} -> {r['B']['exact_five_class_accuracy']:.6f} |")
    lines += ['', 'Crowded means >=30 source objects including non-targets; multi-instance means >=2 of one selected class. These subset definitions are unchanged.',
    f"Small targets (GT area below 32x32 after scaling long side to 320): {c['small_targets']['A']['matched']}/{c['small_targets']['A']['targets']} matched in A versus {c['small_targets']['B']['matched']}/{c['small_targets']['B']['targets']} in B. This is a fixed descriptive grouping, not AP-small.",
    f"Identity candidates A -> B: selected-class confusion {c['identity_errors']['A']['wrong_class_candidates']} -> {c['identity_errors']['B']['wrong_class_candidates']}; Valser Classic/Still {c['identity_errors']['A']['valser_confusions']} -> {c['identity_errors']['B']['valser_confusions']}; regular Red Bull overlapping source light {c['identity_errors']['A']['regular_on_light']} -> {c['identity_errors']['B']['regular_on_light']}. Regular Red Bull sizes are merged by source labels, so size-specific accuracy cannot be measured.",
    f"GT matching identities: {c['gained_gt_matches']} gained, {c['lost_gt_matches']} lost. Count improvements alone can conceal localization/class errors.",
    '', 'Vectors use Red Bull / Knoppers / Classic / Still / Capri-Sun. All validation comparisons are linked:',
    '| Image | Truth | A | B | Absolute class error A -> B |','| --- | --- | --- | --- | --- |']
    for r in c['images']:
        lines.append(f"| [{r['image']}](visuals/augmentation_001_{Path(r['image']).stem}.jpg) | {r['truth']} | {r['a_counts']} | {r['b_counts']} | {r['a_sum_absolute_error']} -> {r['b_sum_absolute_error']} |")
    lines += ['', '## 7. Conclusion','',discussion['conclusion'],
    'This single-seed comparison on 26 development images across five scene groups does not establish robustness across seeds or unseen stores. No test-set result is used.',
    '', '## 8. One next controlled experiment (not run)','',discussion['next'],
    '', '## Validation and reproduction','',f'All **36 tests passed** (34 existing plus two augmentation checks). All **{protected} protected artifacts** and frozen dataset image/label/config hashes remain unchanged. BASELINE_002 and all previous experiment outputs remain unchanged. B is saved separately under runs/augmentation_001. No test-set evaluation occurred.',
    'The exact configuration and runtime versions are recorded before training; there was one augmented run, no parameter tuning and no inference threshold changes. B was trained separately. The archived completed A training provides the baseline training evidence.',
    'Evidence: [preservation](augmentation_001_preservation.json), [training log](augmentation_001_training.log), [tests](augmentation_001_tests.log).','',
    '```powershell', '.\\.venv\\Scripts\\python.exe -m src.train_augmentation', '.\\.venv\\Scripts\\python.exe -m src.evaluate_augmentation', '.\\.venv\\Scripts\\python.exe -m src.analyze_augmentation', '.\\.venv\\Scripts\\python.exe -m src.augmentation_001_training_summary', '.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v', '.\\.venv\\Scripts\\python.exe -m src.report_augmentation', '```',
    'Training/inference refuse to overwrite existing runs. The recorded configs support reproduction in a separate checkout/output directory. Analysis and report commands use saved outputs only.']
    formatted=[]
    for line in lines:
        if line.startswith('|') and formatted and formatted[-1] and not formatted[-1].startswith('|'):
            formatted.append('')
        formatted.append(line)
    (ROOT/'reports/AUGMENTATION_001_RESULTS.md').write_text('\n'.join(formatted)+'\n')
    verify_protected()


if __name__=='__main__':
    main()
