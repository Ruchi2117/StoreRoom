"""Draw source boxes/crops for the proposed classes; these are NOT predictions."""
import json
from collections import Counter
from PIL import Image, ImageDraw, ImageOps
from src.preflight import ROOT, DATA, REPORTS


def main():
    records = json.loads((REPORTS / "image_manifest.json").read_text(encoding="utf-8"))
    products = json.loads((ROOT / "configs/candidate_classes.json").read_text())["products"]
    colors = ["red", "blue", "limegreen", "darkorange", "magenta"]
    indices = [0, 43, 72, 101, 174, 179, 218, 224, 232, 240]
    sheet = Image.new("RGB", (8 * 175, 5 * 255), "white")
    draw = ImageDraw.Draw(sheet)
    for row, product in enumerate(products):
        examples = [(record, obj) for index in indices for record in [records[index]]
                    for obj in record["objects"] if obj["label"] == product["source_label"]]
        seen = set()
        column = 0
        for record, obj in examples:
            if record["image"] in seen:
                continue
            seen.add(record["image"])
            with Image.open(DATA / record["image"]) as source:
                crop = ImageOps.contain(source.crop(tuple(obj["box"])).convert("RGB"), (170, 200))
            x, y = column * 175, row * 255
            sheet.paste(crop, (x, y + 30))
            draw.text((x + 2, y + 2), product["name"].split(" (")[0], fill="black")
            draw.text((x + 2, y + 235), f'Source image #{record["review_index"]}', fill="black")
            column += 1
            if column == 8:
                break
    sheet.save(REPORTS / "visuals/candidate_crops.jpg", quality=94)
    for index in [72, 174, 232]:
        record = records[index]
        with Image.open(DATA / record["image"]) as source:
            canvas = source.convert("RGB")
        overlay = ImageDraw.Draw(canvas)
        counts = Counter()
        for product, color in zip(products, colors):
            for obj in record["objects"]:
                if obj["label"] != product["source_label"]:
                    continue
                counts[product["name"]] += 1
                overlay.rectangle(obj["box"], outline=color, width=12)
        canvas.thumbnail((1100, 1350))
        panel = Image.new("RGB", (max(canvas.width, 700), canvas.height + 125), "white")
        panel.paste(canvas, (0, 0))
        legend = ImageDraw.Draw(panel)
        legend.text((10, canvas.height + 5), "SOURCE ANNOTATIONS ONLY - " + record["image"], fill="black")
        for n, (product, color) in enumerate(zip(products, colors)):
            legend.text((10, canvas.height + 25 + n * 18), f'{product["name"]}: {counts[product["name"]]}', fill=color)
        panel.save(REPORTS / f"visuals/source_boxes_{index}.jpg", quality=94)


if __name__ == "__main__":
    main()
