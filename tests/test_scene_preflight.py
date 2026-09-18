import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.preflight import ROOT, REPORTS
from src.scene_preflight import components, split_is_supported
from src.scene_preflight import main as scene_main


class SceneChecks(unittest.TestCase):
    def test_revisited_scene_links_are_transitive(self):
        self.assertEqual(components(5, [(0, 2), (2, 4), (1, 3)]), [[0, 2, 4], [1, 3]])

    def test_many_instances_in_one_scene_do_not_pass_scene_gate(self):
        products = [{"product_id": "example", "source_label": "label"}]
        row = {"scene_group": "one_machine", "objects": [{"label": "label"}] * 100}
        policy = {"minimum_scene_groups": {"train": 3}, "minimum_instances": {"train": 20},
                  "minimum_multi_instance_images_per_class_per_split": 1}
        self.assertFalse(split_is_supported({"train": [row] * 50}, products, policy))

    def test_bad_input_invalidates_previous_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "configs").mkdir()
            (root / "configs/splits.json").write_text('{"status":"data_support_passed"}')
            with patch("src.scene_preflight.ROOT", root), patch("src.scene_preflight.REPORTS", root / "reports"):
                with self.assertRaises(FileNotFoundError):
                    scene_main()
            self.assertEqual(json.loads((root / "configs/splits.json").read_text())["status"], "blocked")
            self.assertEqual(json.loads((root / "reports/split_preflight.json").read_text())["gate"], "not_completed")

    @unittest.skipUnless((ROOT / "configs/splits.json").exists(), "Run the data preflight first")
    def test_real_split_preserves_groups_and_excludes_quarantine(self):
        splits = json.loads((ROOT / "configs/splits.json").read_text())
        self.assertEqual(splits["status"], "data_support_passed")
        for path, expected in splits["input_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected, f"Stale split input: {path}")
        groups = json.loads((REPORTS / "scene_groups.json").read_text())
        quarantined = {row["image"] for row in json.loads((REPORTS / "quarantine.json").read_text())}
        assignments = {}
        for split, images in splits["images"].items():
            for name in images:
                self.assertNotIn(name, assignments)
                self.assertNotIn(name, quarantined)
                assignments[name] = split
        for group in groups:
            actual = {assignments[name] for name in group["images"] if name in assignments}
            self.assertLessEqual(len(actual), 1, group["scene_group"])
        manifest = json.loads((REPORTS / "image_manifest.json").read_text())
        self.assertEqual(set(assignments) | quarantined, {row["image"] for row in manifest})
        group_lookup = {image: group["scene_group"] for group in groups for image in group["images"]}
        rows = {row["image"]: {**row, "scene_group": group_lookup[row["image"]]} for row in manifest}
        policy = json.loads((ROOT / "configs/preflight_policy.json").read_text())
        products = json.loads((ROOT / "configs/class_map.json").read_text())["classes"]
        self.assertTrue(split_is_supported({split: [rows[name] for name in names] for split, names in splits["images"].items()}, products, policy))


if __name__ == "__main__":
    unittest.main()
