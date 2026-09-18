import json
from pathlib import Path
import unittest
from src.counting import count_classes, counting_metrics

ROOT = Path(__file__).resolve().parents[1]


class BaselineEvaluationTests(unittest.TestCase):
    def test_validation_predictions_counts_and_membership(self):
        report = json.loads((ROOT / "reports/baseline_001_val.json").read_text())
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["role"], "development")
        splits = json.loads((ROOT / "configs/splits.json").read_text())["images"]
        names = [r["image"] for r in report["images"]]
        self.assertEqual(set(names),set(splits["val"]))
        self.assertEqual(len(names),26)
        self.assertFalse(set(names)&set(splits["test"]))
        for row in report["images"]:
            self.assertEqual(count_classes([d["class_id"] for d in row["detections"]]),row["predicted"])
            self.assertTrue(all(d["confidence"]>=0.25 for d in row["detections"]))
        self.assertEqual(counting_metrics([r["truth"] for r in report["images"]],
                                         [r["predicted"] for r in report["images"]]),report["counting"])

    def test_test_is_absent_or_bound_to_a_frozen_baseline(self):
        path = ROOT / "reports/baseline_001_test.json"
        if not path.exists():
            self.assertFalse((ROOT / "reports/baseline_001_frozen.json").exists())
            return
        freeze = json.loads((ROOT / "reports/baseline_001_frozen.json").read_text())
        report = json.loads(path.read_text())
        self.assertTrue(freeze["baseline_frozen"])
        self.assertEqual(report["checkpoint_sha256"],freeze["checkpoint_sha256"])
        self.assertEqual(report["role"],"final frozen baseline evaluation")
        self.assertEqual(len(report["images"]),26)
