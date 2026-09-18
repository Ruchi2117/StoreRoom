"""Integration checks of real smoke artifacts. No network or training during tests."""
import hashlib
import json
import math
from pathlib import Path
import unittest

import yaml
from src.yolo_checks import validate_example, validate_pairs

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["Red Bull", "Knoppers", "Valser Classic", "Valser Still", "Capri-Sun Multivitamin"]


class RuntimeArtifacts(unittest.TestCase):
    def test_real_conversion_preserves_counts_coordinates_and_splits(self):
        subset = json.loads((ROOT / "configs/smoke_subset.json").read_text())["images"]
        frozen = json.loads((ROOT / "configs/splits.json").read_text())["images"]
        classes = json.loads((ROOT / "configs/class_map.json").read_text())["classes"]
        self.assertEqual([c["class_id"] for c in classes], list(range(5)))
        raw = ROOT / "data/raw/holoselecta/FinalDataset"
        totals = [0] * 5
        negatives = 0
        for split, names in subset.items():
            self.assertTrue(set(names) <= set(frozen[split]))
            images = ROOT / "data/yolo_smoke/images" / split
            labels = ROOT / "data/yolo_smoke/labels" / split
            validate_pairs(images, labels, names)
            for name in names:
                row = validate_example(raw / name, raw / Path(name).with_suffix(".xml"),
                                       images / name, labels / Path(name).with_suffix(".txt"), classes)
                self.assertEqual(hashlib.sha256((raw / name).read_bytes()).digest(),
                                 hashlib.sha256((images / name).read_bytes()).digest())
                totals = [a + b for a, b in zip(totals, row["counts"])]
                negatives += row["yolo_boxes"] == 0
        self.assertTrue(all(n > 0 for n in totals))
        self.assertGreaterEqual(negatives, 1)
        report = json.loads((ROOT / "reports/conversion_smoke.json").read_text())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["counts_by_class"], totals)
        self.assertEqual(report["total_boxes"], sum(totals))

    def test_yaml_has_exact_names_and_frozen_split_paths(self):
        for filename, directory in [("yolo_smoke.yaml", "yolo_smoke"), ("yolo_v01.yaml", "yolo_v01")]:
            config = yaml.safe_load((ROOT / "configs" / filename).read_text())
            self.assertEqual(config["names"], dict(enumerate(NAMES)))
            self.assertEqual(Path(config["path"]), ROOT / "data" / directory)
            self.assertEqual({s: config[s] for s in ("train", "val", "test")},
                             {s: f"images/{s}" for s in ("train", "val", "test")})

    def test_cpu_prediction_output_structure_and_frozen_inputs(self):
        report = json.loads((ROOT / "reports/runtime_smoke.json").read_text())
        self.assertFalse(report["trained"])
        self.assertFalse(report["cuda_available"])
        self.assertIsNone(report["torch_cuda_build"])
        self.assertEqual(report["device"], "cpu")
        self.assertEqual(report["model"]["device"], "cpu")
        self.assertEqual(report["model"]["filename"], "yolo11n.pt")
        self.assertEqual(len(report["model"]["class_names"]), 80)
        self.assertEqual(len(report["results"]), 2)
        for path, digest in report["frozen_config_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)
        for result in report["results"]:
            height, width = result["original_shape_hw"]
            self.assertEqual(result["box_shape"], [len(result["detections"]), 4])
            for item in result["detections"]:
                self.assertTrue(0 <= item["coco_class_id"] < 80)
                self.assertEqual(item["coco_name"], report["model"]["class_names"][str(item["coco_class_id"])])
                self.assertTrue(0 <= item["confidence"] <= 1)
                self.assertTrue(all(math.isfinite(x) for x in item["xyxy"]))
                x1, y1, x2, y2 = item["xyxy"]
                self.assertTrue(0 <= x1 < x2 <= width)
                self.assertTrue(0 <= y1 < y2 <= height)


if __name__ == "__main__":
    unittest.main()
