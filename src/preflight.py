"""Inspect source annotations and images; no YOLO conversion or model training.

ElementTree reads XML for statistics only. Supervision will perform VOC-to-YOLO
conversion at the next, separate milestone. All paths in reports are relative to
the original extracted dataset, so the reports can be reused on another machine.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/raw/holoselecta/FinalDataset"
REPORTS = ROOT / "reports"


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def gtin_from_label(label):
    match = re.search(r"(?:^|_)(\d{8,14})$", label.strip())
    return match.group(1) if match else None


def valid_gtin(gtin):
    if not gtin or len(gtin) not in {8, 12, 13, 14}:
        return False
    total = sum(int(digit) * (3 if index % 2 == 0 else 1)
                for index, digit in enumerate(reversed(gtin[:-1])))
    return (10 - total % 10) % 10 == int(gtin[-1])


def box_issues(box, width, height):
    x1, y1, x2, y2 = box
    if not all(math.isfinite(value) for value in box):
        return ["nonfinite_box"]
    issues = []
    if x2 <= x1 or y2 <= y1:
        issues.append("nonpositive_box")
    if min(x1, x2) < 0 or min(y1, y2) < 0 or max(x1, x2) > width or max(y1, y2) > height:
        issues.append("out_of_bounds")
    if x2 - x1 < 5 or y2 - y1 < 5:
        issues.append("tiny_box_under_5px")
    return issues


def difference_hash(image):
    small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.get_flattened_data())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return value


def contact_sheets(records, directory, prefix="all", columns=6, per_page=36):
    """Visual review indexes, not augmented training images."""
    directory.mkdir(parents=True, exist_ok=True)
    for page, start in enumerate(range(0, len(records), per_page), 1):
        subset = records[start:start + per_page]
        rows = (len(subset) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * 240, rows * 265), "white")
        draw = ImageDraw.Draw(sheet)
        for offset, record in enumerate(subset):
            with Image.open(DATA / record["image"]) as source:
                thumb = ImageOps.contain(source.convert("RGB"), (236, 222))
            x, y = (offset % columns) * 240, (offset // columns) * 265
            sheet.paste(thumb, (x + (240 - thumb.width) // 2, y))
            draw.text((x + 3, y + 224), f'{start + offset:03d} {Path(record["image"]).stem}', fill="black")
            draw.text((x + 3, y + 239), f'{record["width"]}x{record["height"]} | boxes {len(record["objects"])}', fill="black")
        sheet.save(directory / f"{prefix}_{page:02d}.jpg", quality=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-visuals", action="store_true")
    args = parser.parse_args()
    policy = json.loads((ROOT / "configs/preflight_policy.json").read_text())
    hash_threshold = policy["near_duplicate_dhash_distance"]
    REPORTS.mkdir(exist_ok=True)
    images = sorted(p for p in DATA.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    annotations = sorted(DATA.rglob("*.xml"))
    if not images or not annotations:
        raise SystemExit("No dataset found. Download and run python -m src.extract_data first.")
    by_stem = defaultdict(list)
    for image in images:
        by_stem[image.stem].append(image)
    records, annotation_records, issues = [], [], []
    orphan_annotations = []
    paired_images = set()
    for annotation in annotations:
        tree = ET.parse(annotation).getroot()
        width, height = int(tree.findtext("size/width")), int(tree.findtext("size/height"))
        objects = []
        for index, obj in enumerate(tree.findall("object")):
            name = obj.findtext("name", "").strip()
            box = [float(obj.findtext(f"bndbox/{axis}")) for axis in ("xmin", "ymin", "xmax", "ymax")]
            problems = box_issues(box, width, height)
            if not name:
                problems.append("empty_label")
            for problem in problems:
                issues.append({"file": annotation.name, "object_index": index, "issue": problem})
            objects.append({"label": name, "gtin": gtin_from_label(name), "box": box,
                            "difficult": obj.findtext("difficult", "0"),
                            "truncated": obj.findtext("truncated", "0"), "issues": problems})
        duplicates = Counter((o["label"], tuple(o["box"])) for o in objects)
        for (name, box), count in duplicates.items():
            if count > 1:
                issues.append({"file": annotation.name, "issue": "duplicate_annotation", "label": name, "box": box, "count": count})
        base = {"annotation": annotation.relative_to(DATA).as_posix(), "width": width,
                "height": height, "xml_filename": tree.findtext("filename"), "objects": objects}
        annotation_records.append(base)
        candidates = by_stem[annotation.stem]
        if len(candidates) != 1:
            orphan_annotations.append(annotation.name)
            continue
        image = candidates[0]
        paired_images.add(image)
        with image.open("rb") as stream:
            file_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        with Image.open(image) as source:
            source.load()
            actual_size = list(source.size)
            exif = source.getexif()
            exif_time = exif.get(306)
            try:
                exif_time = source.getexif().get_ifd(34665).get(36867, exif_time)
            except (KeyError, TypeError):
                pass
            rgb = source.convert("RGB")
            pixel_hash = hashlib.sha256(bytes(str(rgb.size), "ascii") + rgb.tobytes()).hexdigest()
            dhash = difference_hash(rgb)
            mean_rgb = list(rgb.resize((1, 1)).getpixel((0, 0)))
            orientation = exif.get(274, 1)
        date_match = re.search(r"(20\d{6})[_-]?(\d{6})", image.stem)
        if actual_size != [width, height]:
            issues.append({"file": image.name, "issue": "dimension_mismatch", "actual": actual_size, "xml": [width, height]})
        if orientation != 1:
            issues.append({"file": image.name, "issue": "exif_orientation", "orientation": orientation})
        if Path(base["xml_filename"] or "").name.lower() != image.name.lower():
            issues.append({"file": image.name, "issue": "xml_filename_mismatch", "xml_filename": base["xml_filename"]})
        records.append({**base, "image": image.relative_to(DATA).as_posix(), "actual_size": actual_size,
                        "sha256": file_hash, "pixel_sha256": pixel_hash, "dhash": f"{dhash:016x}",
                        "mean_rgb": mean_rgb, "exif_datetime": exif_time, "exif_orientation": orientation,
                        "filename_datetime": "_".join(date_match.groups()) if date_match else None})
        if len(records) % 50 == 0:
            print(f"Inspected {len(records)} image/XML pairs", flush=True)
    records.sort(key=lambda r: r["image"])
    for index, record in enumerate(records):
        record["review_index"] = index
    exact_groups = []
    for key in ("sha256", "pixel_sha256"):
        groups = defaultdict(list)
        for record in records:
            groups[record[key]].append(record["image"])
        exact_groups.append({"method": key, "groups": [members for members in groups.values() if len(members) > 1]})
    near_pairs = []
    for first, second in itertools.combinations(records, 2):
        distance = (int(first["dhash"], 16) ^ int(second["dhash"], 16)).bit_count()
        if distance <= hash_threshold:
            near_pairs.append({"a": first["image"], "b": second["image"], "dhash_distance": distance})
    near_pairs.sort(key=lambda pair: (pair["dhash_distance"], pair["a"], pair["b"]))
    all_counts = Counter(o["label"] for r in annotation_records for o in r["objects"])
    paired_counts = Counter(o["label"] for r in records for o in r["objects"])
    class_rows = []
    for label, count in all_counts.most_common():
        supporting = [r for r in records if any(o["label"] == label for o in r["objects"])]
        dates = {r["filename_datetime"][:8] for r in supporting if r["filename_datetime"]}
        gtin = gtin_from_label(label)
        class_rows.append({"label": label, "gtin": gtin, "gtin_checksum_valid": valid_gtin(gtin),
                           "all_xml_instances": count, "paired_instances": paired_counts[label],
                           "paired_images": len(supporting), "filename_dates": len(dates),
                           "box_issue_count": sum(bool(o["issues"]) for r in supporting for o in r["objects"] if o["label"] == label)})
    labels_by_gtin = defaultdict(set)
    for label in all_counts:
        labels_by_gtin[gtin_from_label(label)].add(label)
    summary = {
        "image_files": len(images), "xml_files": len(annotations), "paired_images": len(records),
        "all_xml_instances": sum(all_counts.values()), "paired_instances": sum(paired_counts.values()),
        "all_xml_classes": len(all_counts), "paired_classes": len(paired_counts),
        "orphan_annotations": orphan_annotations,
        "unannotated_images": [p.name for p in images if p not in paired_images],
        "ambiguous_image_stems": {k: [p.name for p in v] for k, v in by_stem.items() if len(v) > 1},
        "issues_by_type": dict(Counter(i["issue"] for i in issues)),
        "duplicate_groups": exact_groups, "near_duplicate_candidate_pairs": len(near_pairs),
        "near_duplicate_method": f"64-bit dHash Hamming distance <= {hash_threshold}; candidates only, not proof of same/different machine",
        "filename_dates": dict(sorted(Counter(r["filename_datetime"][:8] if r["filename_datetime"] else "unknown" for r in records).items())),
        "gtin_label_collisions": {str(k): sorted(v) for k, v in labels_by_gtin.items() if k and len(v) > 1},
        "scene_status": "Requires visual review; capture date and hashes alone do not establish independent machines/scenes."
    }
    save_json(REPORTS / "dataset_summary.json", summary)
    save_json(REPORTS / "image_manifest.json", records)
    save_json(REPORTS / "annotation_issues.json", issues)
    save_json(REPORTS / "near_duplicate_candidates.json", near_pairs)
    write_csv(REPORTS / "class_counts.csv", class_rows, list(class_rows[0]))
    if not args.skip_visuals:
        contact_sheets(records, REPORTS / "visuals")
    print(json.dumps(summary, indent=2))
    print("\nTop paired class counts:")
    for row in sorted(class_rows, key=lambda row: -row["paired_images"])[:15]:
        print(row)


if __name__ == "__main__":
    main()
