from pathlib import Path
import tempfile
import unittest

from PIL import Image
from src.yolo_checks import read_yolo, validate_example, validate_pairs


class YoloValidationChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = self.root / "sample.jpg"
        Image.new("RGB", (100, 80)).save(self.image)
        self.xml = self.root / "sample.xml"
        self.xml.write_text('<annotation><size><width>100</width><height>80</height></size>'
                            '<object><name>product_2</name><bndbox><xmin>11</xmin><ymin>21</ymin>'
                            '<xmax>51</xmax><ymax>61</ymax></bndbox></object></annotation>')
        self.label = self.root / "sample.txt"
        self.label.write_text("2 0.3 0.5 0.4 0.5\n")
        self.classes = [{"class_id": i, "source_label": f"product_{i}"} for i in range(5)]

    def compare(self):
        return validate_example(self.image, self.xml, self.image, self.label, self.classes)

    def test_independent_pixel_round_trip(self):
        result = self.compare()
        self.assertEqual(result["source_selected_boxes"], 1)
        self.assertEqual(result["counts"], [0, 0, 1, 0, 0])
        self.assertLess(result["max_coordinate_error_px"], 1e-10)

    def test_malformed_coordinates_and_ids_are_rejected(self):
        for row in ["5 .3 .5 .4 .5", "-1 .3 .5 .4 .5", "2.5 .3 .5 .4 .5",
                    "2 1.1 .5 .4 .5", "2 nan .5 .4 .5", "2 inf .5 .4 .5",
                    "2 .3 .5 -.4 .5", "2 .3 .5 0 .5", "2 .3 .5 .4 0",
                    "2 .01 .5 .4 .5", "2 .3 .5 .4"]:
            with self.subTest(row=row):
                self.label.write_text(row)
                with self.assertRaises(ValueError):
                    read_yolo(self.label)

    def test_count_mapping_and_coordinate_changes_are_rejected(self):
        for row in ["", "3 .3 .5 .4 .5", "2 .31 .5 .4 .5", "2 .3 .5 .4 .5\n2 .3 .5 .4 .5"]:
            with self.subTest(row=row):
                self.label.write_text(row)
                with self.assertRaises(ValueError):
                    self.compare()

    def test_missing_label_and_image_are_rejected(self):
        with self.assertRaises(ValueError):
            read_yolo(self.root / "missing.txt")
        with self.assertRaises(ValueError):
            validate_example(self.image, self.xml, self.root / "missing.jpg", self.label, self.classes)
        with self.assertRaises(ValueError):
            validate_pairs(self.root, self.root, ["missing.jpg"])

    def test_empty_label_is_valid_only_for_a_negative_image(self):
        self.xml.write_text('<annotation><size><width>100</width><height>80</height></size></annotation>')
        self.label.write_text("")
        self.assertEqual(self.compare()["yolo_boxes"], 0)

    def test_dimension_mismatch_is_rejected(self):
        Image.new("RGB", (101, 80)).save(self.image)
        with self.assertRaises(ValueError):
            self.compare()

    def test_five_decimal_edge_rounding_has_a_strict_bound(self):
        # Real DSC01642 export: center-height/2 is -0.000005 after rounding.
        self.label.write_text("3 0.63917 0.21862 0.09833 0.43725\n")
        self.assertEqual(len(read_yolo(self.label)), 1)
        self.label.write_text("3 0.63917 0.21860 0.09833 0.43725\n")
        with self.assertRaises(ValueError):
            read_yolo(self.label)


if __name__ == "__main__":
    unittest.main()
