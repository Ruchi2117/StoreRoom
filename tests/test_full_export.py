import hashlib
import json
from pathlib import Path
import unittest
from src.yolo_checks import validate_example, validate_pairs

ROOT = Path(__file__).resolve().parents[1]


class FullExportTests(unittest.TestCase):
    def test_all_frozen_images_and_machine_memberships(self):
        path = ROOT / "reports/dataset_v01_manifest.json"
        manifest = json.loads(path.read_text())
        report = json.loads((ROOT / "reports/full_export_validation.json").read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), report["manifest_sha256"])
        splits = json.loads((ROOT / "configs/splits.json").read_text())
        self.assertEqual(len(manifest["images"]),175)
        seen, groups = set(), {}
        totals = [0]*5
        for row in manifest["images"]:
            name, split = row["image"], row["split"]
            self.assertNotIn(name,seen)
            seen.add(name)
            self.assertIn(name,splits["images"][split])
            self.assertIn(row["scene_group"],splits["groups"][split])
            self.assertEqual(groups.setdefault(row["scene_group"],split),split)
            raw = ROOT / "data/raw/holoselecta/FinalDataset"
            base = ROOT / "data/yolo_v01"
            result = validate_example(raw/name,raw/Path(name).with_suffix('.xml'),
                                      base/'images'/split/name,base/'labels'/split/Path(name).with_suffix('.txt'),manifest["classes"])
            self.assertEqual(result["counts"],row["counts"])
            totals = [a+b for a,b in zip(totals,result["counts"])]
        self.assertEqual(totals,[597,268,150,165,300])
        for split,names in splits["images"].items():
            validate_pairs(ROOT/'data/yolo_v01/images'/split,ROOT/'data/yolo_v01/labels'/split,names)
