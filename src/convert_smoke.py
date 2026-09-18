"""Small, fixed-split conversion using Supervision; independently validate its output."""
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import supervision as sv
import yaml

from src.yolo_checks import validate_example, validate_pairs

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/holoselecta/FinalDataset"
NAMES = ["Red Bull", "Knoppers", "Valser Classic", "Valser Still", "Capri-Sun Multivitamin"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(full=False):
    if full and (ROOT / "reports/dataset_v01_manifest.json").exists():
        raise FileExistsError("v0.1 is frozen. Verify it with src.train_baseline.verify_dataset; create a new version for changes.")
    report_path = ROOT / ("reports/full_export_validation.json" if full else "reports/conversion_smoke.json")
    report_path.write_text('{"status": "not_completed"}\n', encoding="utf-8")
    frozen_paths = ["configs/class_map.json", "configs/splits.json"]
    frozen_hashes = {p: digest(ROOT / p) for p in frozen_paths}
    class_map = json.loads((ROOT / frozen_paths[0]).read_text())
    splits = json.loads((ROOT / frozen_paths[1]).read_text())
    subset = splits["images"] if full else json.loads((ROOT / "configs/smoke_subset.json").read_text())["images"]
    assert splits["status"] == "data_support_passed"
    for config in (class_map, splits):
        for path, expected in config["input_sha256"].items():
            assert digest(ROOT / path) == expected, f"Stale preflight input: {path}"
    classes = class_map["classes"]
    assert [c["class_id"] for c in classes] == list(range(5))
    source_to_id = {c["source_label"]: c["class_id"] for c in classes}
    stage = ROOT / ("data/full_voc" if full else "data/smoke_voc")
    for directory in (stage / "images", stage / "annotations"):
        directory.mkdir(parents=True, exist_ok=True)
    all_names = [name for names in subset.values() for name in names]
    assert len(set(all_names)) == len(all_names)
    for split, names in subset.items():
        assert set(names) <= set(splits["images"][split]), "Smoke membership changed the frozen split"
        for name in names:
            shutil.copy2(RAW / name, stage / "images" / name)
            xml = Path(name).with_suffix(".xml")
            shutil.copy2(RAW / xml, stage / "annotations" / xml)
    assert {p.name for p in (stage / "images").iterdir()} == set(all_names)
    # Import all source labels. Filtering/remapping happens on Supervision Detections,
    # so class IDs never depend on which labels happen to occur in a split.
    imported = sv.DetectionDataset.from_pascal_voc(
        images_directory_path=str(stage / "images"),
        annotations_directory_path=str(stage / "annotations"))
    selected_annotations = {}
    for image_path, detections in imported.annotations.items():
        selected = [i for i, class_id in enumerate(detections.class_id)
                    if imported.classes[int(class_id)] in source_to_id]
        filtered = detections[np.array(selected, dtype=int)]
        filtered.class_id = np.array([source_to_id[imported.classes[int(detections.class_id[i])]]
                                     for i in selected], dtype=int)
        selected_annotations[image_path] = filtered
    output = ROOT / ("data/yolo_v01" if full else "data/yolo_smoke")
    rows = []
    for split, names in subset.items():
        keys = [key for key in selected_annotations if Path(key).name in names]
        dataset = sv.DetectionDataset(classes=NAMES,
                                      images=keys,
                                      annotations={key: selected_annotations[key] for key in keys})
        images_dir = output / "images" / split
        labels_dir = output / "labels" / split
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        # Export labels with the library; copy image bytes without JPEG recompression.
        dataset.as_yolo(annotations_directory_path=str(labels_dir))
        for name in names:
            shutil.copy2(RAW / name, images_dir / name)
            label = labels_dir / Path(name).with_suffix(".txt")
            row = validate_example(RAW / name, RAW / Path(name).with_suffix(".xml"),
                                   images_dir / name, label, classes)
            assert digest(RAW / name) == digest(images_dir / name), "Image bytes changed"
            rows.append({"split": split, **row})
        validate_pairs(images_dir, labels_dir, names)
    # The full-data YAML is only a planned location, not a claim of full export.
    for suffix, folder in ([("v01", "yolo_v01")] if full else [("smoke", "yolo_smoke")]):
        config = {"path": str(ROOT / "data" / folder),
                  "train": "images/train", "val": "images/val", "test": "images/test",
                  "names": dict(enumerate(NAMES))}
        comment = ("# Eight-image conversion check only; do not train this subset.\n" if suffix == "smoke"
                   else "# Verified full export of frozen configs/splits.json (123/26/26).\n")
        (ROOT / "configs" / f"yolo_{suffix}.yaml").write_text(
            comment + yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    assert frozen_hashes == {p: digest(ROOT / p) for p in frozen_paths}, "Frozen configs changed"
    report = {"status": "passed", "supervision_version": sv.__version__,
              "method": "DetectionDataset.from_pascal_voc -> filter/remap Detections -> as_yolo",
              "coordinate_convention": "Supervision subtracts 1 from all four VOC endpoints; independent checker does the same explicitly. YOLO writes five decimal places.",
              "tolerance_px": 0.1, "frozen_config_sha256": frozen_hashes,
              "images": rows, "total_boxes": sum(r["yolo_boxes"] for r in rows),
              "counts_by_class": [sum(r["counts"][i] for r in rows) for i in range(5)],
              "full_export_completed": full, "augmentation": False}
    if full:
        groups = json.loads((ROOT / "reports/scene_groups.json").read_text())
        group_lookup = {name: g["scene_group"] for g in groups for name in g["images"]}
        group_splits = {}
        for row in rows:
            name, split = row["image"], row["split"]
            group = group_lookup[name]
            assert group in splits["groups"][split]
            assert group_splits.setdefault(group, split) == split, "Machine leakage"
            row["scene_group"] = group
            row["source_xml_sha256"] = digest(RAW / Path(name).with_suffix(".xml"))
            row["image_sha256"] = digest(output / "images" / split / name)
            row["label_sha256"] = digest(output / "labels" / split / Path(name).with_suffix(".txt"))
        expected = json.loads((ROOT / "reports/split_preflight.json").read_text())["selected_support"]
        assert report["counts_by_class"] == [expected[c["product_id"]]["instances"] for c in classes]
        assert {s: len(ns) for s, ns in subset.items()} == {"train":123, "val":26, "test":26}
        manifest = {"version": "holoselecta-five-v0.1", "classes": classes,
                    "source_archive_sha256": splits["source_archive_sha256"],
                    "frozen_config_sha256": frozen_hashes, "images": rows}
        payload = json.dumps(manifest, indent=2) + "\n"
        manifest_path = ROOT / "reports/dataset_v01_manifest.json"
        if manifest_path.exists():
            assert manifest_path.read_text() == payload, "Immutable manifest would change"
        else:
            manifest_path.write_text(payload, encoding="utf-8")
        report["manifest_sha256"] = digest(manifest_path)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"images": len(rows), "boxes": report["total_boxes"],
                      "counts": report["counts_by_class"], "status": "passed"}))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Export and freeze all retained images once")
    main(full=parser.parse_args().full)
