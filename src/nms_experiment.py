"""Two fixed-confidence validation inference runs. No training or test evaluation."""
import json
import time
from pathlib import Path
import numpy as np
from src.train_baseline import ROOT, verify_dataset
from src.convert_smoke import digest, NAMES
from src.counting import count_classes, counting_metrics
from src.review_baseline_002 import iou
from src.yolo_checks import read_yolo, decoded_boxes


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def protect():
    snapshot = json.loads((ROOT / "reports/nms_001_preservation.json").read_text())
    for path, expected in snapshot.items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Protected artifact changed: {path}")
    return len(snapshot)


def match_detections(detections, truth):
    """Confidence-ordered, same-class, one-to-one matching at IoU >= 0.5."""
    matched = set()
    decisions = []
    for index in sorted(range(len(detections)), key=lambda i:-detections[i]["confidence"]):
        pred = detections[index]
        overlaps = [iou(pred["xyxy"], g[1:]) for g in truth]
        candidates = [i for i,g in enumerate(truth) if i not in matched and g[0]==pred["class_id"] and overlaps[i]>=.5]
        if candidates:
            gt = max(candidates,key=lambda i:overlaps[i])
            matched.add(gt)
            kind = "tp"
        else:
            gt = int(np.argmax(overlaps)) if overlaps else None
            kind = "background_or_localization"
            if gt is not None and overlaps[gt]>=.5:
                kind = "duplicate_candidate" if truth[gt][0]==pred["class_id"] else "wrong_class_candidate"
        decisions.append({"prediction_index":index,"kind":kind,"gt_index":gt,
                          "best_iou":overlaps[gt] if gt is not None else 0.0})
    return {"predictions":decisions, "matched_gt_indices":sorted(matched),
            "missed_gt_indices":[i for i in range(len(truth)) if i not in matched]}


def summarize(rows):
    truth = np.array([r["truth"] for r in rows])
    predicted = np.array([r["predicted"] for r in rows])
    tp,fp,fn = np.zeros(5,dtype=int),np.zeros(5,dtype=int),np.zeros(5,dtype=int)
    duplicate_count = 0
    for row in rows:
        for decision in row["matching"]["predictions"]:
            c = row["detections"][decision["prediction_index"]]["class_id"]
            (tp if decision["kind"]=="tp" else fp)[c] += 1
            duplicate_count += decision["kind"]=="duplicate_candidate"
        for i in row["matching"]["missed_gt_indices"]:
            fn[row["gt_boxes"][i][0]] += 1
    error = predicted-truth
    detection = {"tp":tp.tolist(),"fp":fp.tolist(),"fn":fn.tolist(),
                 "precision_per_class":np.divide(tp,tp+fp,out=np.zeros(5),where=tp+fp>0).tolist(),
                 "recall_per_class":np.divide(tp,tp+fn,out=np.zeros(5),where=tp+fn>0).tolist(),
                 "micro_precision":float(tp.sum()/max((tp+fp).sum(),1)),
                 "micro_recall":float(tp.sum()/max((tp+fn).sum(),1)),
                 "duplicate_candidates":int(duplicate_count)}
    return {"detection":detection, "counting":counting_metrics(truth,predicted),
            "zero_baseline":counting_metrics(truth,np.zeros_like(truth)),
            "total_predicted_instances":int(predicted.sum()),"predicted_per_class":predicted.sum(axis=0).tolist(),
            "overcount_items_per_class":np.maximum(error,0).sum(axis=0).tolist(),
            "undercount_items_per_class":np.maximum(-error,0).sum(axis=0).tolist(),
            "overcount_items":int(np.maximum(error,0).sum()),"undercount_items":int(np.maximum(-error,0).sum()),
            "images_with_overcount":int(np.any(error>0,axis=1).sum()),
            "images_with_undercount":int(np.any(error<0,axis=1).sum())}


def main():
    from ultralytics import YOLO
    import ultralytics, torch
    protect()
    manifest_hash = verify_dataset()
    exp = json.loads((ROOT/"reports/baseline_002_experiment.json").read_text())
    checkpoint = Path(exp["checkpoint"])
    assert digest(checkpoint)==exp["checkpoint_sha256"]
    manifest = json.loads((ROOT/"reports/dataset_v01_manifest.json").read_text())
    rows = [r for r in manifest["images"] if r["split"]=="val"]
    assert len(rows)==26
    setup = {"checkpoint":str(checkpoint),"checkpoint_sha256":digest(checkpoint),
             "dataset_manifest_sha256":manifest_hash,"split":"val","images":[r["image"] for r in rows],
             "names":NAMES,"ultralytics":ultralytics.__version__,"torch":torch.__version__,
             "common_arguments":{"imgsz":320,"device":"cpu","conf":.25,"max_det":300,
                                 "agnostic_nms":False,"augment":False,"verbose":False,"rect":True,"batch":1},
             "runs":{"A":.70,"B":.50}, "standard_ultralytics_validation_run":False,
             "metric_protocol":"Custom fixed-threshold one-to-one detection matching at IoU >= 0.5. No full PR-curve AP; all inference keeps confidence 0.25."}
    setup_path = ROOT/"reports/nms_001_setup.json"
    if setup_path.exists():
        raise FileExistsError("NMS_001 already started; do not overwrite a controlled run")
    save(setup_path,setup)
    for name,nms_iou in setup["runs"].items():
        started=time.perf_counter()
        model=YOLO(str(checkpoint))
        results=[]
        for row in rows:
            path=ROOT/"data/yolo_v01/images/val"/row["image"]
            pred=model.predict(str(path),iou=nms_iou,**setup["common_arguments"])[0]
            boxes=pred.boxes
            detections=[{"class_id":int(c),"confidence":float(s),"xyxy":b}
                        for c,s,b in zip(boxes.cls.cpu().tolist(),boxes.conf.cpu().tolist(),boxes.xyxy.cpu().tolist())]
            labels=ROOT/"data/yolo_v01/labels/val"/Path(row["image"]).with_suffix(".txt")
            gt=decoded_boxes(read_yolo(labels),row["width"],row["height"])
            results.append({"image":row["image"],"scene_group":row["scene_group"],"truth":row["counts"],
                            "predicted":count_classes([d["class_id"] for d in detections]),
                            "gt_boxes":gt,"detections":detections,"matching":match_detections(detections,gt)})
        report={"status":"completed","run":name,"nms_iou":nms_iou,"confidence":.25,
                "checkpoint_sha256":digest(checkpoint),"duration_seconds":time.perf_counter()-started,
                "images":results,**summarize(results)}
        save(ROOT/f"reports/nms_001_{name.lower()}.json",report)
        print(json.dumps({k:v for k,v in report.items() if k!='images'},indent=2))
        protect()


if __name__ == "__main__":
    main()
