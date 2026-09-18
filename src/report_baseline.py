"""Render measured experiment results without editing the raw metric files."""
import json
import csv
from src.convert_smoke import ROOT, NAMES


def main():
    experiment = json.loads((ROOT / "reports/baseline_001_experiment.json").read_text())
    export = json.loads((ROOT / "reports/full_export_validation.json").read_text())
    args = experiment["actual_settings"]
    lines = ["# First five-class CPU baseline", "",
             "Full export: 175/175 images passed, 1,480 source/YOLO boxes preserved; split 123/26/26.",
             "Three empty-label images preserved. No class, split, or machine-group changes.",
             f"Maximum coordinate reconstruction error: {max(r['max_coordinate_error_px'] for r in export['images']):.6f} pixels.", "",
             "Dataset version: `holoselecta-five-v0.1`.",
             f"Manifest SHA-256: `{experiment['dataset_manifest_sha256']}`.",
             "Manifest: [dataset_v01_manifest.json](dataset_v01_manifest.json).", "",
             "## Fixed training configuration", "",
             f"Official yolo11n.pt pretrained weights; {args['epochs']} epochs, imgsz={args['imgsz']}, batch={args['batch']}, CPU, workers={args['workers']}, seed={args['seed']}.",
             f"Optimizer {args['optimizer']}, lr0={args['lr0']}, lrf={args['lrf']}, momentum/beta1={args['momentum']}, weight decay={args['weight_decay']}, warmup={args['warmup_epochs']} epoch.",
             f"Nominal batch size nbs={args['nbs']}: gradient accumulation reaches {max(round(args['nbs']/args['batch']),1)} batches after warmup.",
             "No augmentation, AMP, or hyperparameter search. Deterministic execution requested; reproducibility is scoped to this recorded environment.",
             f"End-to-end training call duration: **{experiment['duration_seconds']:.2f} seconds ({experiment['duration_seconds']/60:.2f} minutes)**, including setup and final built-in validation.",
             f"Checkpoint: `{experiment['checkpoint']}`.",
             f"Checkpoint SHA-256: `{experiment['checkpoint_sha256']}`.",
             "Checkpoint selected by Ultralytics validation fitness only. Raw losses, metrics and actual LR traces are in `runs/baseline_001/results.csv`; effective arguments are in `runs/baseline_001/args.yaml` and the experiment JSON.", ""]
    for split in ("val", "test"):
        path = ROOT / f"reports/baseline_001_{split}.json"
        if not path.exists():
            lines += ["## Test set", "", "Not evaluated. The fixed validation gate has not been passed; keep test predictions untouched.", ""]
            continue
        report = json.loads(path.read_text())
        if report["status"] != "completed":
            lines += [f"{split}: incomplete; inspect its JSON status."]
            continue
        d,c,z = report["detection"],report["counting"],report["zero_baseline"]
        lines += [f"## {'Validation: development' if split=='val' else 'Test: final frozen baseline evaluation'}", "",
                  f"Precision **{d['metrics/precision(B)']:.6f}**, recall **{d['metrics/recall(B)']:.6f}**, mAP50 **{d['metrics/mAP50(B)']:.6f}**, mAP50-95 **{d['metrics/mAP50-95(B)']:.6f}**.",
                  "These P/R values use Ultralytics' F1 operating point. AP uses confidence floor 0.001; they are separate from counting at confidence 0.25. NMS IoU is 0.70, class-aware, max_det=300.", "",
                  "| Class | Instances | Precision | Recall | AP50 | AP50-95 | Count MAE | Zero MAE |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        by_name = {r["Class"]:r for r in report["per_class_detection"]}
        for i,name in enumerate(NAMES):
            r = by_name[name]
            lines.append(f"| {name} | {r['Instances']} | {r['Box-P']:.6f} | {r['Box-R']:.6f} | {r['mAP50']:.6f} | {r['mAP50-95']:.6f} | {c['per_class_mae'][i]:.6f} | {z['per_class_mae'][i]:.6f} |")
        lines += ["", f"Overall counting MAE (mean across N x 5 cells): **{c['overall_cell_mae']:.6f}**; zero baseline **{z['overall_cell_mae']:.6f}**.",
                  f"Exact five-class count accuracy: **{c['exact_five_class_accuracy']:.6f}**; zero baseline **{z['exact_five_class_accuracy']:.6f}**.",
                  f"Total-item-count MAE: {c['total_count_mae']:.6f}. Mean sum of absolute class errors per image: {c['mean_sum_absolute_class_errors']:.6f}.", "",
                  "Over-count examples (true -> predicted; class order 0 through 4):"]
        over = sorted(report["images"],key=lambda r:sum(max(e,0) for e in r["error"]),reverse=True)
        under = sorted(report["images"],key=lambda r:sum(max(-e,0) for e in r["error"]),reverse=True)
        examples = [r for r in over[:3] if any(e>0 for e in r["error"])]
        lines += [f"- `{r['image']}`: {r['truth']} -> {r['predicted']}" for r in examples] or ["None at the frozen threshold."]
        lines += ["", "Under-count examples:"]
        examples = [r for r in under[:3] if any(e<0 for e in r["error"])]
        lines += [f"- `{r['image']}`: {r['truth']} -> {r['predicted']}" for r in examples] or ["None at the frozen threshold."]
        lines += [""]
    lines += ["## Interpretation", "", "See [BASELINE_001_REVIEW.md](BASELINE_001_REVIEW.md) for visual findings, limitations, test decision, and the next measured experiment. These results do not establish production readiness."]
    (ROOT / "reports/BASELINE_001_RESULTS.md").write_text("\n".join(lines)+"\n")
    # Plot the untouched training CSV; no smoothing or replacement of metrics.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with open(experiment["results_csv"], newline="") as stream:
        curve = list(csv.DictReader(stream))
    epochs = [int(r["epoch"]) for r in curve]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for key, label in [("metrics/mAP50(B)", "Validation mAP50"), ("metrics/mAP50-95(B)", "Validation mAP50-95")]:
        axes[0].plot(epochs, [float(r[key]) for r in curve], marker="o", label=label)
    for key, label in [("train/cls_loss", "Train classification loss"), ("val/cls_loss", "Validation classification loss")]:
        axes[1].plot(epochs, [float(r[key]) for r in curve], marker="o", label=label)
    for axis in axes:
        axis.set_xlabel("Epoch")
        axis.grid(alpha=.25)
        axis.legend()
    axes[0].set_ylim(0,1)
    fig.suptitle("baseline_001: fixed 10-epoch CPU experiment")
    fig.savefig(ROOT / "reports/visuals/baseline_001_learning_curve.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
