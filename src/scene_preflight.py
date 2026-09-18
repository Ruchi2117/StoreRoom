"""Build evidence-backed machine groups and test five-class split feasibility.

Only metadata is written; raw images/labels remain unchanged. There is no YOLO
export or training here. Ambiguous scenes are quarantined rather than guessed.
"""
from collections import Counter, defaultdict
import hashlib
import json
import random
import re

from src.preflight import ROOT, REPORTS, gtin_from_label, save_json, valid_gtin, write_csv


def components(count, links):
    parent = list(range(count))
    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    for a, b in links:
        parent[find(b)] = find(a)
    result = defaultdict(list)
    for index in range(count):
        result[find(index)].append(index)
    return list(result.values())


def support(rows, products):
    output = {}
    for product in products:
        matches = [(row, sum(obj["label"] == product["source_label"] for obj in row["objects"])) for row in rows]
        counts = [count for _, count in matches]
        output[product["product_id"]] = {
            "positive_images": sum(count > 0 for count in counts), "instances": sum(counts),
            "scene_groups": len({row["scene_group"] for row, count in matches if count}),
            "images_with_2plus": sum(count >= 2 for count in counts),
            "count_histogram": dict(sorted(Counter(counts).items()))}
    return output


def split_is_supported(splits, products, policy):
    for split, rows in splits.items():
        for stats in support(rows, products).values():
            if stats["scene_groups"] < policy["minimum_scene_groups"][split] or stats["instances"] < policy["minimum_instances"][split]:
                return False
            if stats["images_with_2plus"] < policy["minimum_multi_instance_images_per_class_per_split"]:
                return False
    return True


def main():
    # Invalidate old success artifacts even if an input/identity check raises.
    save_json(ROOT / "configs/splits.json", {"status": "blocked", "groups": {}, "images": {}})
    save_json(ROOT / "configs/class_map.json", {"status": "not_selected", "classes": []})
    save_json(REPORTS / "split_preflight.json", {"gate": "not_completed", "training_performed": False})
    input_paths = ["reports/image_manifest.json", "reports/machine_codes.json", "reports/near_duplicate_candidates.json",
                   "configs/scene_review.json", "configs/exclusions.json", "configs/candidate_classes.json", "configs/preflight_policy.json"]
    input_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in input_paths}
    records = json.loads((REPORTS / "image_manifest.json").read_text(encoding="utf-8"))
    qr_rows = json.loads((REPORTS / "machine_codes.json").read_text(encoding="utf-8"))
    review = json.loads((ROOT / "configs/scene_review.json").read_text())
    manifest_hash = hashlib.sha256((REPORTS / "image_manifest.json").read_bytes()).hexdigest()
    if manifest_hash != review["image_manifest_sha256"]:
        raise ValueError("Image manifest changed after scene review; review the new manifest before splitting")
    excluded = json.loads((ROOT / "configs/exclusions.json").read_text())["images"]
    candidates = json.loads((ROOT / "configs/candidate_classes.json").read_text())
    products = candidates["products"]
    policy = json.loads((ROOT / "configs/preflight_policy.json").read_text())
    if len(products) != policy["target_classes"] or len({p["product_id"] for p in products}) != len(products):
        raise ValueError("Candidate class count/identifiers do not match policy")
    names = {row["image"]: index for index, row in enumerate(records)}
    if [row["image"] for row in records] != [row["image"] for row in qr_rows]:
        raise ValueError("QR report and image manifest disagree; rerun the QR audit")
    if [row["review_index"] for row in records] != list(range(len(records))):
        raise ValueError("Review indices changed; repeat visual grouping review")
    links = []
    for first, last in review["reviewed_same_scene_ranges"]:
        if not 0 <= first <= last < len(records):
            raise ValueError("Invalid scene range")
        links.extend((first, index) for index in range(first + 1, last + 1))
    for group in review["conservative_possible_revisit_merges"]:
        links.extend((group[0], index) for index in group[1:])
    codes = defaultdict(list)
    for index, row in enumerate(qr_rows):
        for code in row["codes"]:
            # Only the observed UUID-bearing machine sticker format is accepted.
            if re.fullmatch(r"02:[0-9a-f-]{36}:[0-9a-f]{40}", code["text"]):
                codes[code["text"]].append(index)
    for members in codes.values():
        links.extend((members[0], index) for index in members[1:])
    # Exact duplicates must stay together even if filenames/capture times differ.
    for key in ("sha256", "pixel_sha256"):
        by_hash = defaultdict(list)
        for index, row in enumerate(records):
            by_hash[row[key]].append(index)
        for members in by_hash.values():
            links.extend((members[0], index) for index in members[1:])
    group_rows, eligible, quarantine = [], [], []
    for members in components(len(records), links):
        found = {code["text"] for index in members for code in qr_rows[index]["codes"] if code["text"] in codes}
        if len(found) > 1:
            raise ValueError(f"Visual group joins different QR stickers: {members}. Review before splitting.")
        code = next(iter(found), None)
        group_id = "machine_" + hashlib.sha256(code.encode()).hexdigest()[:12] if code else f"unresolved_{min(members):03d}"
        for index in members:
            records[index]["scene_group"] = group_id
            reason = excluded.get(records[index]["image"])
            if reason or not code:
                quarantine.append({"image": records[index]["image"], "scene_group": group_id,
                                   "reason": reason or "No machine sticker decoded in this reviewed scene; cross-visit identity unresolved"})
            else:
                eligible.append(records[index])
        group_rows.append({"scene_group": group_id, "status": "sticker_supported" if code else "unresolved",
                           "readable_sticker_images": [records[i]["image"] for i in members if qr_rows[i]["codes"]],
                           "images": [records[i]["image"] for i in members]})
    # Every approximate-hash match is triaged, never automatically equated to a duplicate.
    pairs = json.loads((REPORTS / "near_duplicate_candidates.json").read_text())
    eligible_names = {row["image"] for row in eligible}
    for pair in pairs:
        first, second = records[names[pair["a"]]], records[names[pair["b"]]]
        if first["scene_group"] == second["scene_group"]:
            pair["review_result"] = "same_machine_keep_together"
        elif first["image"] not in eligible_names or second["image"] not in eligible_names:
            pair["review_result"] = "unresolved_image_quarantined"
        else:
            pair["review_result"] = "different_readable_machine_stickers_similar_shelf_layout"
    save_json(REPORTS / "near_duplicate_review.json", pairs)
    save_json(REPORTS / "scene_groups.json", group_rows)
    save_json(REPORTS / "quarantine.json", quarantine)
    labels = defaultdict(set)
    for row in records:
        for obj in row["objects"]:
            labels[gtin_from_label(obj["label"])].add(obj["label"])
    for product in products:
        gtin = product["source_gtin"]
        if not valid_gtin(gtin) or labels[gtin] != {product["source_label"]}:
            raise ValueError(f"Candidate has ambiguous/malformed source identity: {product}")
        if any(obj["issues"] for row in eligible for obj in row["objects"] if obj["label"] == product["source_label"]):
            raise ValueError("Candidate has invalid source boxes")
    by_group = defaultdict(list)
    for row in eligible:
        by_group[row["scene_group"]].append(row)
    group_ids = sorted(by_group)
    target_labels = {product["source_label"] for product in products}
    negative = lambda row: not any(obj["label"] in target_labels for obj in row["objects"])
    # Search only annotation support/size balance, never predictions or model scores.
    rng = random.Random(42)
    best = None
    val_size = max(3, round(len(group_ids) * 0.15))
    for _ in range(5000):
        shuffled = group_ids.copy()
        rng.shuffle(shuffled)
        assignments = {"val": shuffled[:val_size], "test": shuffled[val_size:2 * val_size], "train": shuffled[2 * val_size:]}
        splits = {split: [row for group in groups for row in by_group[group]] for split, groups in assignments.items()}
        # Both hold-outs need whole-image negatives for the false-positive check.
        if not all(any(negative(row) for row in splits[split]) for split in ("val", "test")):
            continue
        if not split_is_supported(splits, products, policy):
            continue
        score = sum(abs(len(splits[split]) / len(eligible) - ratio) for split, ratio in (("train", .7), ("val", .15), ("test", .15)))
        if best is None or score < best[0]:
            best = score, assignments, splits
    class_rows = []
    eligible_support = support(eligible, products)
    for product in products:
        class_rows.append({"product_id": product["product_id"], "source_label": product["source_label"],
                           **{k: v for k, v in eligible_support[product["product_id"]].items() if k != "count_histogram"}})
    write_csv(REPORTS / "selected_class_coverage.csv", class_rows, list(class_rows[0]))
    all_products = [{"product_id": label, "source_label": label} for label in sorted({o["label"] for r in records for o in r["objects"]})]
    all_support = support(eligible, all_products)
    all_rows = [{"source_label": label, **{k: v for k, v in stats.items() if k != "count_histogram"}} for label, stats in all_support.items()]
    write_csv(REPORTS / "class_scene_counts.csv", all_rows, list(all_rows[0]))
    result = {"gate": "pass" if best else "fail", "eligible_images": len(eligible), "quarantined_images": len(quarantine),
              "eligible_machine_groups": len(by_group), "decoded_sticker_images": sum(bool(r["codes"]) for r in qr_rows),
              "distinct_sticker_payloads": len(codes), "selected_support": eligible_support,
              "near_duplicate_review": dict(Counter(pair["review_result"] for pair in pairs)),
              "interpretation": review["limitation"], "input_sha256": input_hashes, "training_performed": False}
    if best:
        _, assignments, splits = best
        result["splits"] = {split: {"images": len(rows), "groups": len(assignments[split]),
                                    "negative_images": sum(negative(row) for row in rows), "support": support(rows, products)} for split, rows in splits.items()}
        save_json(ROOT / "configs/splits.json", {"status": "data_support_passed", "input_sha256": input_hashes, "seed": 42, "image_manifest_sha256": manifest_hash, "source_archive_sha256": "4492e5f544a035cf4884626187ebf39ab5e703f71a3ff05733b6c11baf926afb",
                  "policy": "machine-sticker groups, reviewed adjacent views, unresolved scenes excluded", "groups": assignments,
                  "images": {split: sorted(row["image"] for row in rows) for split, rows in splits.items()}})
        save_json(ROOT / "configs/class_map.json", {"status": "selected_for_public_dataset_baseline", "input_sha256": input_hashes, "identity_note": candidates["identity_note"],
                  "identity_level": "source_product_class", "catalog_sku_verified": False,
                  "evaluation_ground_truth": "source_annotated_visible_front_packages",
                  "classes": [{"class_id": index, **product} for index, product in enumerate(products)]})
    else:
        # Explicitly invalidate previously generated assignments on a failed rerun.
        save_json(ROOT / "configs/splits.json", {"status": "blocked", "groups": {}, "images": {}})
        save_json(ROOT / "configs/class_map.json", {"status": "not_selected", "classes": []})
    save_json(REPORTS / "split_preflight.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
