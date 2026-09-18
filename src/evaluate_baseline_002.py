"""Development validation or a guarded, one-time frozen test evaluation."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from src.train_baseline import ROOT, verify_dataset
from src.baseline_002_checks import verify_preservation, verify_configuration
from src.convert_smoke import digest
from src.counting import count_classes, counting_metrics


def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=lambda x: x.item()) + "\n")


def main(split="val"):
    if split != "val":
        raise ValueError("BASELINE_002 is validation-only; test evaluation is forbidden")
    from ultralytics import YOLO
    verify_preservation()
    verify_configuration()
    verify_dataset()
    protocol = json.loads((ROOT / "configs/baseline_002_protocol.json").read_text())
    experiment = json.loads((ROOT / "reports/baseline_002_experiment.json").read_text())
    assert experiment["status"] == "completed"
    assert digest(ROOT / "configs/baseline_002_protocol.json") == experiment["protocol_sha256"]
    assert digest(ROOT / "configs/baseline_002.yaml") == experiment["configuration_sha256"]
    checkpoint = Path(experiment["checkpoint"])
    assert digest(checkpoint) == experiment["checkpoint_sha256"]
    output = ROOT / f"reports/baseline_002_{split}.json"
    if output.exists():
        raise FileExistsError(f"Evaluation already recorded: {output}")
    # A started marker prevents accidental repeat of a partially completed test.
    save(output, {"status": "started", "split": split, "started_at_utc":datetime.now(timezone.utc).isoformat()})
    model = YOLO(str(checkpoint))
    metrics = model.val(data=str(ROOT / "configs/yolo_v01.yaml"), split=split,
                        imgsz=320, batch=4, device="cpu", workers=0, plots=False,
                        conf=protocol["ap_confidence_floor"], iou=protocol["nms_iou"],
                        max_det=300, augment=False, project=str(ROOT / "runs"),
                        name=f"baseline_002_{split}", verbose=False)
    manifest = json.loads((ROOT / "reports/dataset_v01_manifest.json").read_text())
    images = [r for r in manifest["images"] if r["split"] == split]
    rows = []
    for item in images:
        source = ROOT / "data/yolo_v01/images" / split / item["image"]
        result = model.predict(str(source), imgsz=320, device="cpu",
                               conf=protocol["counting_confidence"], iou=protocol["nms_iou"],
                               max_det=300, agnostic_nms=False, augment=False, verbose=False)[0]
        boxes = result.boxes
        prediction = count_classes(boxes.cls.cpu().numpy())
        truth = item["counts"]
        rows.append({"image": item["image"], "scene_group": item["scene_group"],
                     "width": item["width"], "height": item["height"],
                     "truth": truth, "predicted": prediction,
                     "error": [p-t for p,t in zip(prediction, truth)],
                     "detections": [{"class_id":int(c), "confidence":float(s), "xyxy":b}
                                    for c,s,b in zip(boxes.cls.cpu().tolist(), boxes.conf.cpu().tolist(), boxes.xyxy.cpu().tolist())]})
    truth = [r["truth"] for r in rows]
    predictions = [r["predicted"] for r in rows]
    report = {"status": "completed", "split": split,
              "role": "development" if split == "val" else "final frozen baseline evaluation",
              "checkpoint_sha256": digest(checkpoint), "protocol": protocol,
              "detection": metrics.results_dict, "per_class_detection": metrics.summary(decimals=10),
              "precision_recall_note": "Ultralytics P/R at its validation F1 operating point; not necessarily confidence 0.25. AP uses the 0.001 confidence floor.",
              "counting": counting_metrics(truth, predictions),
              "zero_baseline": counting_metrics(truth, np.zeros_like(truth)),
              "images": rows}
    verify_preservation()
    save(output, report)
    print(json.dumps({"split": split, "detection": report["detection"], "counting":report["counting"], "zero_baseline": report["zero_baseline"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["val"], default="val")
    main(parser.parse_args().split)
