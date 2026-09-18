"""Compare validation artifacts only; never invokes training or prediction."""
import csv
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from src.convert_smoke import ROOT, NAMES
from src.baseline_002_checks import verify_preservation
from src.preview_yolo import panel
from src.yolo_checks import read_yolo, decoded_boxes
from src.counting import counting_metrics
from src.review_baseline_002 import iou


def load(relative):
    return json.loads((ROOT / relative).read_text())


def summarize_errors(report, analysis):
    images = report["images"]
    flags = [f for r in analysis["images"] for f in r["flags"]]
    lookup = {r["image"]:r for r in images}
    duplicate_overlaps = []
    for row in analysis["images"]:
        for flag in row["flags"]:
            if flag["kind"] != "duplicate_candidate":
                continue
            prediction = flag["prediction"]
            others = [d for d in lookup[row["image"]]["detections"]
                      if d["class_id"] == prediction["class_id"] and d["xyxy"] != prediction["xyxy"]]
            duplicate_overlaps.append({"image":row["image"], "class_id":prediction["class_id"],
                                       "maximum_same_class_prediction_iou":max((iou(prediction["xyxy"],d["xyxy"]) for d in others),default=0)})
    return {"tp": analysis["tp"], "fp": analysis["fp"], "fn": analysis["fn"],
            "duplicate_prediction_overlaps":duplicate_overlaps,
            "flag_counts": dict(Counter(f["kind"] for f in flags)),
            "excluded_label_overlaps": dict(Counter(f["overlapping_excluded_source_label"] for f in flags if "overlapping_excluded_source_label" in f)),
            "regular_on_light_candidates": sum(f["prediction"]["class_id"] == 0 and f.get("overlapping_excluded_source_label") == "redbull_light__33__90162800" for f in flags),
            "valser_confusion_candidates": sum(f["kind"] == "class_confusion_candidate" and {f["prediction"]["class_id"], f["nearest_gt_class"]} == {2,3} for f in flags),
            "zero_predictions": [r["image"] for r in images if not any(r["predicted"])],
            "positive_zero_predictions": [r["image"] for r in images if any(r["truth"]) and not any(r["predicted"])],
            "exact_positive_images": [r["image"] for r in images if any(r["truth"]) and r["truth"] == r["predicted"]]}


def main():
    verify_preservation()
    old = load("reports/baseline_001_val.json")
    new = load("reports/baseline_002_val.json")
    old_analysis = load("reports/baseline_001_failure_analysis.json")
    new_analysis = load("reports/baseline_002_failure_analysis.json")
    old_rows = {r["image"]:r for r in old["images"]}
    new_rows = {r["image"]:r for r in new["images"]}
    assert old_rows.keys() == new_rows.keys()
    changes = []
    for name, row in new_rows.items():
        before = old_rows[name]
        assert row["truth"] == before["truth"]
        mae1 = sum(abs(e) for e in before["error"])
        mae2 = sum(abs(e) for e in row["error"])
        changes.append({"image": name, "truth":row["truth"], "baseline_001":before["predicted"],
                        "baseline_002":row["predicted"], "old_sum_absolute_error":mae1,
                        "new_sum_absolute_error":mae2, "error_delta":mae2-mae1})
    summary = {"split":"val", "baseline_001":summarize_errors(old,old_analysis),
               "baseline_002":summarize_errors(new,new_analysis), "image_changes":changes,
               "improved_images":sum(r["error_delta"]<0 for r in changes),
               "worsened_images":sum(r["error_delta"]>0 for r in changes),
               "unchanged_images":sum(r["error_delta"]==0 for r in changes)}
    source_rows = {r["image"]:r for r in load("reports/image_manifest.json")}
    cohorts = {"crowded_30plus_source_objects": [name for name in old_rows if len(source_rows[name]["objects"]) >= 30],
               "multi_instance_any_class_2plus": [name for name,r in old_rows.items() if max(r["truth"]) >= 2]}
    summary["cohorts"] = {}
    for label,names in cohorts.items():
        summary["cohorts"][label] = {"images":names, "size":len(names)}
        for key,rows in [("baseline_001",old_rows),("baseline_002",new_rows)]:
            summary["cohorts"][label][key] = counting_metrics([rows[n]["truth"] for n in names],[rows[n]["predicted"] for n in names])
    (ROOT / "reports/baseline_002_comparison.json").write_text(json.dumps(summary,indent=2)+"\n")
    # Preserve original failure cases, and add strongest new improvements/regressions.
    fixed = ["IMG_20181218_165652.jpg", "IMG_20181218_165646.jpg", "DSC01659.png",
             "DSC01658.png", "IMG_20181218_171607.jpg", "IMG_20190206_170714.jpg"]
    ranked = sorted(changes,key=lambda r:r["error_delta"])
    names = list(dict.fromkeys(fixed + [r["image"] for r in ranked[:2]+ranked[-2:]]))
    sheets = []
    for name in names:
        row = new_rows[name]
        source = ROOT / "data/yolo_v01/images/val" / name
        labels = ROOT / "data/yolo_v01/labels/val" / Path(name).with_suffix(".txt")
        truth = decoded_boxes(read_yolo(labels),row["width"],row["height"])
        canvas = Image.new("RGB", (1860,690), "#171c25")
        canvas.paste(panel(source,truth,"Ground truth | "+name),(0,0))
        for index,(label,data) in enumerate([("001",old_rows[name]),("002",row)],1):
            boxes = [(d["class_id"],*d["xyxy"]) for d in data["detections"]]
            canvas.paste(panel(source,boxes,f"BASELINE_{label} | conf=0.25"),(620*index,0))
        ImageDraw.Draw(canvas).text((12,642),f"True {row['truth']}     001 {old_rows[name]['predicted']}     002 {row['predicted']}     Order: Red Bull / Knoppers / Classic / Still / Capri-Sun",fill="white",font=ImageFont.load_default(size=18))
        canvas.save(ROOT / "reports/visuals" / f"baseline_002_comparison_{Path(name).stem}.jpg",quality=92)
        sheets.append(ImageOps.contain(canvas,(1395,518)))
    for page in range(0,len(sheets),3):
        sheet = Image.new("RGB",(1395,518*len(sheets[page:page+3])),"#171c25")
        for i,img in enumerate(sheets[page:page+3]):
            sheet.paste(img,(0,518*i))
        sheet.save(ROOT / "reports/visuals" / f"baseline_002_comparison_page_{page//3+1}.jpg",quality=92)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes = plt.subplots(2,3,figsize=(14,8),layout="constrained")
    keys = ["metrics/precision(B)","metrics/recall(B)","metrics/mAP50(B)","metrics/mAP50-95(B)","train/cls_loss","val/cls_loss"]
    for baseline in ("001","002"):
        with (ROOT/f"runs/baseline_{baseline}/results.csv").open(newline="") as stream:
            curve = list(csv.DictReader(stream))
        for axis,key in zip(axes.flat,keys):
            axis.plot([int(r["epoch"]) for r in curve],[float(r[key]) for r in curve],label=f"BASELINE_{baseline}")
            axis.set_title(key)
            axis.set_xlabel("Epoch")
            axis.grid(alpha=.25)
            axis.legend()
    fig.suptitle("Training-budget comparison: unchanged data and settings, epoch-relative LR schedules")
    fig.savefig(ROOT / "reports/visuals/baseline_002_learning_curve.png",dpi=150)
    plt.close(fig)
    verify_preservation()
    print(json.dumps({k:v for k,v in summary.items() if k!='image_changes'},indent=2))


if __name__ == "__main__":
    main()
