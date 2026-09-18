"""Analyze stored validation predictions only; no inference or threshold tuning."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from src.preview_yolo import panel
from src.convert_smoke import ROOT
from src.yolo_checks import read_yolo, decoded_boxes


def iou(box, other):
    a, b = np.array(box), np.array(other)
    intersect = np.maximum(0, np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2])).prod()
    union = np.maximum(0, a[2:]-a[:2]).prod() + np.maximum(0, b[2:]-b[:2]).prod() - intersect
    return float(intersect / union) if union else 0.0


def main():
    report = json.loads((ROOT / "reports/baseline_001_val.json").read_text())
    rows = report["images"]
    source_manifest = {r["image"]:r for r in json.loads((ROOT / "reports/image_manifest.json").read_text())}
    selected_labels = {r["source_label"] for r in json.loads((ROOT / "configs/class_map.json").read_text())["classes"]}
    tp, fp, fn = np.zeros(5, int), np.zeros(5, int), np.zeros(5, int)
    diagnostics = []
    for row in rows:
        labels = ROOT / "data/yolo_v01/labels/val" / Path(row["image"]).with_suffix(".txt")
        truth = decoded_boxes(read_yolo(labels), row["width"], row["height"])
        matched = set()
        flags = []
        for pred in sorted(row["detections"], key=lambda p:-p["confidence"]):
            overlaps = [iou(pred["xyxy"], box[1:]) for box in truth]
            candidates = [i for i,g in enumerate(truth) if i not in matched and g[0] == pred["class_id"] and overlaps[i] >= .5]
            if candidates:
                best = max(candidates, key=lambda i: overlaps[i])
                matched.add(best)
                tp[pred["class_id"]] += 1
            else:
                fp[pred["class_id"]] += 1
                best = int(np.argmax(overlaps)) if overlaps else None
                if best is not None and overlaps[best] >= .5:
                    kind = "duplicate_candidate" if truth[best][0] == pred["class_id"] else "class_confusion_candidate"
                else:
                    kind = "unmatched_prediction_localization_or_background"
                flag = {"kind":kind, "prediction": pred,
                              "nearest_gt_class":truth[best][0] if best is not None else None,
                              "best_iou":overlaps[best] if best is not None else 0}
                excluded = [(o["label"], iou(pred["xyxy"], [v-1 for v in o["box"]]))
                            for o in source_manifest[row["image"]]["objects"] if o["label"] not in selected_labels]
                if excluded:
                    label, overlap = max(excluded,key=lambda pair:pair[1])
                    if overlap >= .5:
                        flag["overlapping_excluded_source_label"] = label
                        flag["excluded_iou"] = overlap
                flags.append(flag)
        missed = [g for i,g in enumerate(truth) if i not in matched]
        for g in missed:
            fn[g[0]] += 1
        diagnostics.append({"image":row["image"], "truth":row["truth"], "predicted":row["predicted"],
                            "error":row["error"], "missed_boxes":missed, "flags":flags})
    analysis = {"split":"val", "confidence":0.25, "matching_iou":0.5,
                "matching":"confidence-ordered, one-to-one, same-class greedy IoU matching",
                "tp":tp.tolist(), "fp":fp.tolist(), "fn":fn.tolist(),
                "precision":np.divide(tp,tp+fp,out=np.zeros(5),where=tp+fp>0).tolist(),
                "recall":np.divide(tp,tp+fn,out=np.zeros(5),where=tp+fn>0).tolist(),
                "images":diagnostics}
    (ROOT / "reports/baseline_001_failure_analysis.json").write_text(json.dumps(analysis,indent=2)+"\n")
    under = sorted(rows, key=lambda r:sum(max(-e,0) for e in r["error"]), reverse=True)
    over = sorted(rows, key=lambda r:sum(max(e,0) for e in r["error"]), reverse=True)
    crowded = max(rows,key=lambda r:sum(r["truth"]))
    candidates = [*under[:2], *over[:2], crowded, *[r for r in rows if sum(r["truth"])==0]]
    flagged_names = {d["image"] for d in diagnostics
                     if any(f["kind"] == "class_confusion_candidate" for f in d["flags"])}
    candidates.extend(r for r in rows if r["image"] in flagged_names)
    selected = list({r["image"]:r for r in candidates}.values())
    directory = ROOT / "reports/visuals"
    pairs = []
    for row in selected:
        image = ROOT / "data/yolo_v01/images/val" / row["image"]
        labels = ROOT / "data/yolo_v01/labels/val" / Path(row["image"]).with_suffix(".txt")
        truth = decoded_boxes(read_yolo(labels), row["width"], row["height"])
        preds = [(p["class_id"], *p["xyxy"]) for p in row["detections"]]
        pair = Image.new("RGB",(1240,680),"#171c25")
        pair.paste(panel(image,truth,"Ground truth | "+row["image"]),(0,0))
        pair.paste(panel(image,preds,"Predictions | confidence 0.25"),(620,0))
        ImageDraw.Draw(pair).text((12,640),f"True: {row['truth']}    Predicted: {row['predicted']}    Error: {row['error']}",fill="white",font=ImageFont.load_default(size=18))
        pair.save(directory / f"baseline_001_val_{Path(row['image']).stem}.jpg",quality=92)
        pairs.append(ImageOps.contain(pair,(930,510)))
    sheet = Image.new("RGB", (1860,510*((len(pairs)+1)//2)),"#171c25")
    for i,pair in enumerate(pairs):
        sheet.paste(pair,((i%2)*930,(i//2)*510))
    sheet.save(directory / "baseline_001_validation.jpg",quality=92)
    print(json.dumps({"tp":tp.tolist(),"fp":fp.tolist(),"fn":fn.tolist(),"review_images":[r['image'] for r in selected]}))


if __name__ == "__main__":
    main()
