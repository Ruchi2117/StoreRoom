"""Load official COCO weights and predict two images on CPU. Never trains."""
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "data" / "ultralytics_settings"))
Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)


def main():
    import torch
    import torchvision
    from ultralytics import YOLO

    assert not torch.cuda.is_available(), "This smoke run is for the CPU environment"
    classes = json.loads((ROOT / "configs/class_map.json").read_text())
    splits = json.loads((ROOT / "configs/splits.json").read_text())
    subset = json.loads((ROOT / "configs/smoke_subset.json").read_text())
    model_path = ROOT / "data" / "models" / "yolo11n.pt"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    # Ultralytics resolves this official model basename to its release asset.
    model = YOLO(str(model_path))
    source = ROOT / "data/raw/holoselecta/FinalDataset"
    outputs = []
    for name in subset["images"]["train"][:2]:
        result = model.predict(str(source / name), device="cpu", imgsz=640,
                               augment=False, save=False, verbose=False)[0]
        boxes = result.boxes
        detections = [{"coco_class_id": int(c), "coco_name": result.names[int(c)],
                       "confidence": float(conf), "xyxy": xyxy}
                      for xyxy, conf, c in zip(boxes.xyxy.cpu().tolist(),
                                              boxes.conf.cpu().tolist(), boxes.cls.cpu().tolist())]
        outputs.append({"image": name, "original_shape_hw": list(result.orig_shape),
                        "box_shape": list(boxes.xyxy.shape), "detections": detections,
                        "speed_ms": result.speed})
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    report = {"purpose": "COCO CPU inference only; not product recognition or accuracy measurement",
              "python": platform.python_version(), "os": platform.platform(), "device": "cpu",
              "cuda_available": torch.cuda.is_available(), "torch_cuda_build": torch.version.cuda,
              "torchvision": torchvision.__version__, "packages": dict(sorted(packages.items())),
              "dataset": {"doi": "10.17632/gz39ggf35n.1", "version": 1,
                          "archive_sha256": splits["source_archive_sha256"]},
              "selected_classes": classes["classes"],
              "conversion_method": "supervision.DetectionDataset.from_pascal_voc -> as_yolo",
              "frozen_config_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                       for p in ("configs/class_map.json", "configs/splits.json")},
              "model": {"filename": model_path.name, "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                        "source_url": "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt",
                        "class_names": model.names, "device": str(next(model.model.parameters()).device)},
              "results": outputs, "trained": False}
    path = ROOT / "reports/runtime_smoke.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(path), "torch": torch.__version__,
                      "cuda": torch.cuda.is_available(), "images": len(outputs),
                      "detections": [len(r["detections"]) for r in outputs]}, indent=2))


if __name__ == "__main__":
    main()
