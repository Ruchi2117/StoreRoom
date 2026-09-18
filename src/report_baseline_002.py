"""Write the numeric, validation-only report from saved artifacts."""
import csv
import json
from src.convert_smoke import ROOT, NAMES
from src.baseline_002_checks import verify_preservation


def read(path):
    return json.loads((ROOT/path).read_text())


def main():
    verify_preservation()
    old = read("reports/baseline_001_val.json")
    new = read("reports/baseline_002_val.json")
    exp = read("reports/baseline_002_experiment.json")
    comparison = read("reports/baseline_002_comparison.json")
    cfg = exp["actual_settings"]
    with (ROOT / "runs/baseline_002/results.csv").open(newline="") as stream:
        curve = list(csv.DictReader(stream))
    best = max(curve,key=lambda r:float(r["metrics/mAP50-95(B)"]))
    lines = ["# BASELINE_002: controlled training-budget comparison", "",
             "Validation-only development experiment. BASELINE_001 artifacts remain unchanged. No test evaluation was run for BASELINE_002.", "",
             "## Exact configuration", "",
             "The configuration diff is exactly `epochs: 10 -> 30`. A fresh model was initialized from the same official `yolo11n.pt`, not from BASELINE_001's checkpoint.",
             f"Frozen dataset manifest SHA-256: `{exp['dataset_manifest_sha256']}`.",
             "Same 175 images, 123/26/26 machine-group split and five classes. No labels, files or assignments changed.", "",
             f"CPU; imgsz={cfg['imgsz']}; batch={cfg['batch']}; workers={cfg['workers']}; seed={cfg['seed']}; deterministic={cfg['deterministic']}; optimizer={cfg['optimizer']}.",
             f"lr0={cfg['lr0']}; lrf={cfg['lrf']}; momentum/beta1={cfg['momentum']}; weight_decay={cfg['weight_decay']}; warmup_epochs={cfg['warmup_epochs']}; warmup_bias_lr={cfg['warmup_bias_lr']}; patience={cfg['patience']}; nbs={cfg['nbs']}.",
             "All augmentation disabled, AMP=False, cache=False, no threshold tuning. Counting confidence=0.25, class-aware NMS IoU=0.70, max_det=300. AP confidence floor=0.001.",
             f"Python {exp['python']}; PyTorch {exp['torch']}; Ultralytics {exp['ultralytics']}; PyTorch CPU threads={exp['cpu_threads']}.",
             f"Actual settings: [experiment JSON](baseline_002_experiment.json); requested settings: [YAML](../configs/baseline_002.yaml).", "",
             "## Training duration and learning curve", "",
             f"Completed **{len(curve)} epochs**. Training call duration **{exp['duration_seconds']:.2f} seconds ({exp['duration_seconds']/60:.2f} minutes)**, including setup and built-in final validation.",
             f"Highest recorded training-time validation mAP50-95: epoch {best['epoch']} ({float(best['metrics/mAP50-95(B)']):.6f}). The evaluated checkpoint is Ultralytics best.pt, selected only from validation fitness, as in BASELINE_001.",
             f"Checkpoint: `{exp['checkpoint']}`. SHA-256: `{exp['checkpoint_sha256']}`.",
             "Raw metrics and actual LR traces: [CSV](baseline_002_learning_curve.csv). No metric values were manually edited or smoothed.", "",
             "![Validation learning curves and classification losses](visuals/baseline_002_learning_curve.png)", "",
             "The epoch-relative LR schedule retains its parameters but stretches over 30 epochs. Thus this measures the larger training budget with the same scheduling policy; it is not 20 additional epochs appended to the old LR trajectory. Training-time validation uses batch 8; standalone evaluation below uses batch 4 consistently for both experiments.", "",
             "| Epoch | Precision | Recall | mAP50 | mAP50-95 |",
             "| ---: | ---: | ---: | ---: | ---: |"]
    for r in curve:
        if int(r["epoch"]) in {1,5,10,15,20,25,30,int(best["epoch"])}:
            lines.append(f"| {r['epoch']} | {float(r['metrics/precision(B)']):.6f} | {float(r['metrics/recall(B)']):.6f} | {float(r['metrics/mAP50(B)']):.6f} | {float(r['metrics/mAP50-95(B)']):.6f} |")
    lines += ["", "## Final standalone validation comparison", "",
              "P/R in this table use Ultralytics' F1 operating point. Counting uses the unchanged fixed confidence threshold. No metric or threshold is selected from the test set.", "",
              "| Metric | BASELINE_001 | BASELINE_002 | Change (002 - 001) |", "| --- | ---: | ---: | ---: |"]
    for key in ["metrics/precision(B)","metrics/recall(B)","metrics/mAP50(B)","metrics/mAP50-95(B)"]:
        a,b = old["detection"][key],new["detection"][key]
        lines.append(f"| {key} | {a:.6f} | {b:.6f} | {b-a:+.6f} |")
    for key in ["overall_cell_mae","total_count_mae","mean_sum_absolute_class_errors","exact_five_class_accuracy"]:
        a,b = old["counting"][key],new["counting"][key]
        lines.append(f"| {key} | {a:.6f} | {b:.6f} | {b-a:+.6f} |")
    lines += ["",f"Always-zero counting MAE: **{new['zero_baseline']['overall_cell_mae']:.6f}** for both. Always-zero exact-vector accuracy: **{new['zero_baseline']['exact_five_class_accuracy']:.6f}**.",
              "Overall cell MAE averages absolute errors over 26 images x 5 classes. Mean sum absolute class errors is five times cell MAE; total-count MAE can hide swaps between classes. Exact accuracy requires all five counts to match.", "",
              "## Per-class validation changes", "",
              "| Class | Instances | P 001 -> 002 | R 001 -> 002 | AP50 001 -> 002 | AP50-95 001 -> 002 | Count MAE 001 -> 002 | Zero MAE |",
              "| --- | ---: | ---: | ---: | --- | --- | --- | ---: |"]
    before = {r["Class"]:r for r in old["per_class_detection"]}
    after = {r["Class"]:r for r in new["per_class_detection"]}
    for i,name in enumerate(NAMES):
        a,b = before[name],after[name]
        lines.append(f"| {name} | {b['Instances']} | {a['Box-P']:.6f} -> {b['Box-P']:.6f} | {a['Box-R']:.6f} -> {b['Box-R']:.6f} | {a['mAP50']:.6f} -> {b['mAP50']:.6f} | {a['mAP50-95']:.6f} -> {b['mAP50-95']:.6f} | {old['counting']['per_class_mae'][i]:.6f} -> {new['counting']['per_class_mae'][i]:.6f} | {new['zero_baseline']['per_class_mae'][i]:.6f} |")
    lines += ["", "## Fixed-threshold error analysis", "",
              "Diagnostic TP/FP/FN use identical confidence-ordered, same-class, one-to-one matching at IoU >= 0.5. Candidate duplicate/confusion counts are diagnostic labels, not an exhaustive visual ground truth.", "",
              "| Class | TP 001 -> 002 | FP 001 -> 002 | Misses 001 -> 002 |", "| --- | --- | --- | --- |"]
    a,b = comparison["baseline_001"],comparison["baseline_002"]
    for i,name in enumerate(NAMES):
        lines.append(f"| {name} | {a['tp'][i]} -> {b['tp'][i]} | {a['fp'][i]} -> {b['fp'][i]} | {a['fn'][i]} -> {b['fn'][i]} |")
    lines += ["",f"Image-level summed class error: {comparison['improved_images']} improved, {comparison['worsened_images']} worsened, {comparison['unchanged_images']} unchanged.",
              f"Positive images with zero predictions: {len(a['positive_zero_predictions'])} -> {len(b['positive_zero_predictions'])}.",
              f"Exact positive-image count vectors: {len(a['exact_positive_images'])} -> {len(b['exact_positive_images'])} (out of 24 positive validation images).",
              f"Valser Classic/Still confusion candidates: {a['valser_confusion_candidates']} -> {b['valser_confusion_candidates']}.",
              f"Duplicate candidates: {a['flag_counts'].get('duplicate_candidate',0)} -> {b['flag_counts'].get('duplicate_candidate',0)}.",
              f"Regular Red Bull predictions overlapping source Red Bull light at IoU >= 0.5: {a['regular_on_light_candidates']} -> {b['regular_on_light_candidates']}.",
              "Red Bull size accuracy cannot be measured: the selected regular class merges sizes. Regular/light overlap can be measured using the original excluded-class labels, without relabeling training data.", "",
              "### Representative image comparisons", "",
              "Count vectors use Red Bull / Knoppers / Valser Classic / Valser Still / Capri-Sun order.", "",
              "| Image | Truth | 001 | 002 | Sum absolute error change |", "| --- | --- | --- | --- | ---: |"]
    selected = {"IMG_20181218_165652.jpg","DSC01659.png","DSC01658.png","IMG_20181218_171607.jpg","IMG_20190206_170714.jpg"}
    ranked = sorted(comparison["image_changes"],key=lambda r:r["error_delta"])
    selected.update(r["image"] for r in ranked[:2]+ranked[-2:])
    for r in comparison["image_changes"]:
        if r["image"] in selected:
            lines.append(f"| {r['image']} | {r['truth']} | {r['baseline_001']} | {r['baseline_002']} | {r['error_delta']:+d} |")
    lines += ["", "All 26 paired count vectors and diagnostic summaries are in [comparison JSON](baseline_002_comparison.json).", "",
              "Visual comparisons (ground truth / 001 / 002):"]
    for p in sorted((ROOT / "reports/visuals").glob("baseline_002_comparison_page_*.jpg")):
        lines.append(f"- [{p.stem}](visuals/{p.name})")
    lines += ["", "### Crowded and multi-instance subsets", "",
              "Definitions were fixed before final evaluation: crowded means at least 30 source-annotated objects including non-target classes; multi-instance means at least two instances of any selected class.", "",
              "| Validation subset | Images | Cell MAE 001 -> 002 | Exact-vector accuracy 001 -> 002 |",
              "| --- | ---: | --- | --- |"]
    for label,cohort in comparison["cohorts"].items():
        a,b = cohort["baseline_001"],cohort["baseline_002"]
        lines.append(f"| {label} | {cohort['size']} | {a['overall_cell_mae']:.6f} -> {b['overall_cell_mae']:.6f} | {a['exact_five_class_accuracy']:.6f} -> {b['exact_five_class_accuracy']:.6f} |")
    lines += ["", "## Interpretation and the next experiment", "",
              "The following interpretation is based on validation evidence and inspected image comparisons.", ""]
    review_path = ROOT / "reports/BASELINE_002_REVIEW.md"
    if review_path.exists():
        lines.append(review_path.read_text().partition("\n")[2].strip())
    else:
        lines.append("Visual review and conclusions are pending; this numeric draft is not the final report.")
    lines += ["",
              "BASELINE_002 has no test results. BASELINE_001's frozen test evaluation was neither modified nor used for tuning this experiment."]
    (ROOT / "reports/BASELINE_002_RESULTS.md").write_text("\n".join(lines)+"\n")
    verify_preservation()


if __name__ == "__main__":
    main()
