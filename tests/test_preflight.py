"""Checks for errors that could silently corrupt identity or box audits."""
from pathlib import Path
import tempfile
import unittest

from src.extract_data import safe_target
from src.preflight import box_issues, gtin_from_label, valid_gtin


class PreflightChecks(unittest.TestCase):
    def test_gtin_keeps_leading_zero_and_ignores_pack_size(self):
        self.assertEqual(gtin_from_label("brand_product__250__012345678905"), "012345678905")
        self.assertTrue(valid_gtin("012345678905"))
        self.assertFalse(valid_gtin("012345678906"))
        self.assertIsNone(gtin_from_label("brand_product_250"))

    def test_boxes_at_image_edge_are_not_silently_clipped(self):
        self.assertEqual(box_issues([0, 0, 100, 80], 100, 80), [])
        self.assertIn("out_of_bounds", box_issues([-1, 0, 100, 80], 100, 80))
        self.assertIn("out_of_bounds", box_issues([0, 0, 101, 80], 100, 80))
        self.assertIn("nonpositive_box", box_issues([50, 0, 40, 80], 100, 80))
        self.assertIn("nonfinite_box", box_issues([float("nan"), 0, 10, 10], 100, 80))

    def test_archive_paths_cannot_escape_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(safe_target(root, "FinalDataset/photo.jpg"), root / "FinalDataset/photo.jpg")
            with self.assertRaises(ValueError):
                safe_target(root, "../outside.jpg")


if __name__ == "__main__":
    unittest.main()
