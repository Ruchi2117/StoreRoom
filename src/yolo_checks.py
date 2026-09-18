"""Independent checks of YOLO output against source VOC; this does not export labels."""
from collections import Counter
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image


def read_yolo(path: Path, class_count=5):
    if not path.is_file():
        raise ValueError(f"Missing YOLO label: {path}")
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"Expected five columns: {path}:{line_number}")
        if not parts[0].isdigit() or not 0 <= int(parts[0]) < class_count:
            raise ValueError(f"Invalid class ID: {path}:{line_number}")
        coordinates = [float(value) for value in parts[1:]]
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in coordinates):
            raise ValueError(f"Coordinates outside [0,1] or nonfinite: {path}:{line_number}")
        x, y, width, height = coordinates
        if width <= 0 or height <= 0:
            raise ValueError(f"Zero/negative box area: {path}:{line_number}")
        # Supervision writes five decimal places. Reconstructing x +/- w/2
        # can accumulate at most 0.5e-5 + 0.25e-5 normalized rounding error.
        rounding_bound = 7.5e-6 + 1e-12
        if min(x - width / 2, y - height / 2) < -rounding_bound or max(x + width / 2, y + height / 2) > 1 + rounding_bound:
            raise ValueError(f"Box corners outside image: {path}:{line_number}")
        rows.append((int(parts[0]), *coordinates))
    return rows


def source_boxes(annotation: Path, classes):
    """Read VOC boxes independently, converting 1-based endpoints to 0-based.

    Supervision uses (xmin-1, ymin-1, xmax-1, ymax-1). Preserve that documented
    endpoint convention, including its original xmax-xmin width (no added pixel).
    """
    root = ET.parse(annotation).getroot()
    mapping = {item["source_label"]: item["class_id"] for item in classes}
    dimensions = (int(root.findtext("size/width")), int(root.findtext("size/height")))
    boxes = []
    for obj in root.findall("object"):
        label = obj.findtext("name", "").strip()
        if label in mapping:
            box = tuple(float(obj.findtext(f"bndbox/{key}")) - 1 for key in ("xmin", "ymin", "xmax", "ymax"))
            if not (0 <= box[0] < box[2] < dimensions[0] and 0 <= box[1] < box[3] < dimensions[1]):
                raise ValueError(f"Invalid 1-based source VOC box: {annotation}")
            boxes.append((mapping[label], *box))
    return dimensions, sorted(boxes)


def decoded_boxes(rows, width, height):
    return sorted((class_id, (x - w / 2) * width, (y - h / 2) * height,
                   (x + w / 2) * width, (y + h / 2) * height)
                  for class_id, x, y, w, h in rows)


def validate_example(source_image, source_xml, output_image, output_label, classes, tolerance_px=0.1):
    if not output_image.is_file():
        raise ValueError(f"Missing exported image: {output_image}")
    dimensions, expected = source_boxes(source_xml, classes)
    with Image.open(source_image) as image:
        if image.size != dimensions:
            raise ValueError("Source image/XML dimensions disagree")
    with Image.open(output_image) as image:
        if image.size != dimensions:
            raise ValueError("Export changed image dimensions")
    rows = read_yolo(output_label, len(classes))
    actual = decoded_boxes(rows, *dimensions)
    if len(expected) != len(actual):
        raise ValueError(f"Changed annotation count for {source_image.name}: {len(expected)} -> {len(actual)}")
    if Counter(row[0] for row in expected) != Counter(row[0] for row in actual):
        raise ValueError("Product-to-class mapping changed")
    maximum_error = 0.0
    for original, exported in zip(expected, actual):
        if original[0] != exported[0]:
            raise ValueError("Product-to-class mapping changed")
        maximum_error = max(maximum_error, *(abs(a - b) for a, b in zip(original[1:], exported[1:])))
    if maximum_error > tolerance_px:
        raise ValueError(f"Box coordinates changed: {maximum_error:.6f}px exceeds {tolerance_px}px")
    return {"image": source_image.name, "width": dimensions[0], "height": dimensions[1],
            "source_selected_boxes": len(expected), "yolo_boxes": len(actual),
            "counts": [sum(row[0] == index for row in actual) for index in range(len(classes))],
            "max_coordinate_error_px": maximum_error}


def validate_pairs(image_directory, label_directory, expected_names):
    images = {p.name for p in image_directory.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}}
    labels = {p.stem for p in label_directory.glob("*.txt")}
    if images != set(expected_names) or labels != {Path(name).stem for name in expected_names}:
        raise ValueError("Missing, extra, or mismatched image/label pairs")
