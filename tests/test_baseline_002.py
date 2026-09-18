import json
from pathlib import Path
import unittest

from src.baseline_002_checks import verify_configuration, verify_preservation
from src.counting import count_classes, counting_metrics

ROOT = Path(__file__).resolve().parents[1]


class ControlledBudgetTests(unittest.TestCase):
    def test_only_epoch_budget_changed_and_old_artifacts_preserved(self):
        self.assertEqual(verify_configuration(), {"epochs": [10, 30]})
        self.assertGreater(verify_preservation(), 20)

    def test_test_evaluation_is_rejected_before_inference(self):
        from src.evaluate_baseline_002 import main
        with self.assertRaisesRegex(ValueError, "validation-only"):
            main("test")
        self.assertFalse((ROOT / "reports/baseline_002_test.json").exists())
        self.assertFalse((ROOT / "runs/baseline_002_test").exists())

    def test_same_effective_training_settings_and_initial_weights(self):
        old = json.loads((ROOT / "reports/baseline_001_experiment.json").read_text())
        new = json.loads((ROOT / "reports/baseline_002_experiment.json").read_text())
        self.assertEqual(new["status"], "completed")
        for key in ["dataset_manifest_sha256", "initial_weights_sha256", "python", "ultralytics", "torch", "cpu_threads"]:
            self.assertEqual(new[key], old[key], key)
        ignored = {"epochs", "name", "save_dir"}
        a,b = old["actual_settings"], new["actual_settings"]
        self.assertEqual({k:v for k,v in a.items() if k not in ignored},
                         {k:v for k,v in b.items() if k not in ignored})

    def test_validation_membership_threshold_and_counting(self):
        report = json.loads((ROOT / "reports/baseline_002_val.json").read_text())
        old = json.loads((ROOT / "reports/baseline_001_val.json").read_text())
        self.assertEqual(report["split"], "val")
        self.assertEqual(report["role"], "development")
        self.assertEqual({r["image"] for r in report["images"]}, {r["image"] for r in old["images"]})
        self.assertEqual(report["zero_baseline"], old["zero_baseline"])
        self.assertEqual(report["protocol"]["counting_confidence"], .25)
        self.assertEqual(report["protocol"]["nms_iou"], .7)
        for row in report["images"]:
            self.assertEqual(row["predicted"], count_classes([d["class_id"] for d in row["detections"]]))
            self.assertTrue(all(d["confidence"]>=.25 for d in row["detections"]))
        self.assertEqual(report["counting"], counting_metrics([r["truth"] for r in report["images"]], [r["predicted"] for r in report["images"]]))
