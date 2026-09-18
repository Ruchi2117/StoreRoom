"""Side-by-side original VOC and decoded YOLO boxes for human inspection."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from src.yolo_checks import source_boxes, read_yolo, decoded_boxes

ROOT = Path(__file__).resolve().parents[1]
COLORS = ["#ff4545", "#ffd500", "#35e3ff", "#59ff64", "#ff72ff"]
NAMES = ["Red Bull", "Knoppers", "Valser Classic", "Valser Still", "Capri-Sun Multivitamin"]


def panel(path, boxes, title):
    with Image.open(path) as original:
        image = original.convert("RGB")
    scale = min(600 / image.width, 580 / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)))
    draw = ImageDraw.Draw(image)
    for class_id, x1, y1, x2, y2 in boxes:
        xy = [v * scale for v in (x1, y1, x2, y2)]
        draw.rectangle(xy, outline=COLORS[class_id], width=2)
        draw.text((xy[0] + 1, xy[1] + 1), str(class_id), fill="black",
                  stroke_width=1, stroke_fill=COLORS[class_id])
    canvas = Image.new("RGB", (620, 630), "#171c25")
    canvas.paste(image, ((620 - image.width) // 2, 40))
    ImageDraw.Draw(canvas).text((10, 10), title, fill="white", font=ImageFont.load_default(size=16))
    return canvas


def main():
    classes = json.loads((ROOT / "configs/class_map.json").read_text())["classes"]
    subset = json.loads((ROOT / "configs/smoke_subset.json").read_text())
    raw = ROOT / "data/raw/holoselecta/FinalDataset"
    out = ROOT / "reports/visuals"
    out.mkdir(exist_ok=True)
    pairs = []
    for split, names in subset["images"].items():
        for name in names:
            dimensions, original = source_boxes(raw / Path(name).with_suffix(".xml"), classes)
            labels = ROOT / "data/yolo_smoke/labels" / split / Path(name).with_suffix(".txt")
            converted = decoded_boxes(read_yolo(labels), *dimensions)
            canvas = Image.new("RGB", (1240, 720), "#171c25")
            canvas.paste(panel(raw / name, original, f"VOC | {name} | {len(original)} boxes"), (0, 0))
            canvas.paste(panel(raw / name, converted, f"YOLO decoded | {split} | {len(converted)} boxes"), (620, 0))
            draw = ImageDraw.Draw(canvas)
            x = 12
            for i, display in enumerate(NAMES):
                draw.text((x, 639), f"{i}: {display}", fill=COLORS[i], font=ImageFont.load_default(size=15))
                x += [175, 155, 220, 205, 300][i]
            note = subset["review_notes"].get(name, "Compare geometry, identities and count; boxes describe source annotations only.")
            # Wrap long notes for a readable review sheet.
            import textwrap
            draw.multiline_text((12, 666), textwrap.fill(note, 140), fill="white", font=ImageFont.load_default(size=15))
            canvas.save(out / f"yolo_compare_{Path(name).stem}.jpg", quality=92)
            pairs.append(ImageOps.contain(canvas, (930, 540)))
    sheet = Image.new("RGB", (1860, 540 * ((len(pairs) + 1) // 2)), "#171c25")
    for i, pair in enumerate(pairs):
        sheet.paste(pair, ((i % 2) * 930, (i // 2) * 540))
    sheet.save(out / "yolo_smoke_contact.jpg", quality=92)
    print(out / "yolo_smoke_contact.jpg")


if __name__ == "__main__":
    main()
