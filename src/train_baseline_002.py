"""Run one pinned CPU experiment after checking every frozen dataset hash."""
import json
import os
import platform
import time
from pathlib import Path

from src.convert_smoke import digest
from src.baseline_002_checks import verify_configuration, verify_preservation

ROOT = Path(__file__).resolve().parents[1]
os.environ["YOLO_CONFIG_DIR"] = str(ROOT / "data/ultralytics_settings")
Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
os.environ["YOLO_OFFLINE"] = "true"


def verify_dataset():
    report = json.loads((ROOT / "reports/full_export_validation.json").read_text())
    manifest_path = ROOT / "reports/dataset_v01_manifest.json"
    assert report["status"] == "passed" and report["full_export_completed"]
    assert digest(manifest_path) == report["manifest_sha256"]
    manifest = json.loads(manifest_path.read_text())
    for path, expected in manifest["frozen_config_sha256"].items():
        assert digest(ROOT / path) == expected, f"Changed frozen config: {path}"
    for row in manifest["images"]:
        base = ROOT / "data/yolo_v01"
        assert digest(base / "images" / row["split"] / row["image"]) == row["image_sha256"]
        assert digest(base / "labels" / row["split"] / Path(row["image"]).with_suffix(".txt")) == row["label_sha256"]
    return report["manifest_sha256"]


def main():
    import torch
    import ultralytics
    import yaml
    from ultralytics import YOLO

    verify_preservation()
    changes = verify_configuration()
    manifest_hash = verify_dataset()
    old = json.loads((ROOT / "reports/baseline_001_experiment.json").read_text())
    assert manifest_hash == old["dataset_manifest_sha256"]
    assert platform.python_version() == old["python"]
    assert torch.__version__ == old["torch"] and ultralytics.__version__ == old["ultralytics"]
    assert digest(ROOT / "data/models/yolo11n.pt") == old["initial_weights_sha256"]
    run = ROOT / "runs/baseline_002"
    if run.exists():
        raise FileExistsError("baseline_002 already exists; do not silently overwrite or repeat an experiment")
    args = yaml.safe_load((ROOT / "configs/baseline_002.yaml").read_text())
    args.update(data=str(ROOT / "configs/yolo_v01.yaml"), project=str(ROOT / "runs"), name="baseline_002")
    record_path = ROOT / "reports/baseline_002_experiment.json"
    record = {"status": "running", "controlled_changes": changes, "dataset_version": "holoselecta-five-v0.1",
              "dataset_manifest_sha256": manifest_hash, "python": platform.python_version(),
              "ultralytics": ultralytics.__version__, "torch": torch.__version__, "device": "cpu",
              "model": "yolo11n.pt", "initial_weights_sha256": digest(ROOT / "data/models/yolo11n.pt"),
              "protocol_sha256": digest(ROOT / "configs/baseline_002_protocol.json"),
              "configuration_sha256": digest(ROOT / "configs/baseline_002.yaml"), "requested_settings": args}
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    started = time.perf_counter()
    try:
        model = YOLO(str(ROOT / "data/models/yolo11n.pt"))
        model.train(**args)
        record.update(status="completed", duration_seconds=time.perf_counter() - started,
                      actual_settings=yaml.safe_load((run / "args.yaml").read_text()),
                      cpu_threads=torch.get_num_threads(),
                      checkpoint=str(run / "weights/best.pt"),
                      checkpoint_sha256=digest(run / "weights/best.pt"),
                      results_csv=str(run / "results.csv"))
    except Exception as error:
        record.update(status="failed", duration_seconds=time.perf_counter() - started, error=repr(error))
        raise
    finally:
        record_path.write_text(json.dumps(record, indent=2, default=str) + "\n")
        verify_preservation()


if __name__ == "__main__":
    main()
