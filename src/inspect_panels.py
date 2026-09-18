"""Make review crops of vending-machine context and source product boxes."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from src.preflight import ROOT, DATA, REPORTS


def main():
    records = json.loads((REPORTS / "image_manifest.json").read_text(encoding="utf-8"))
    indices = [72, 82, 86, 89, 93, 96, 101, 108, 111, 114, 120, 126, 131, 135, 140, 146, 149, 154, 159, 162, 166]
    for page, start in enumerate(range(0, len(indices), 7), 1):
        batch = indices[start:start + 7]
        sheet = Image.new("RGB", (2100, 1050), "white")
        draw = ImageDraw.Draw(sheet)
        for column, index in enumerate(batch):
            record = records[index]
            with Image.open(DATA / record["image"]) as source:
                width, height = source.size
                # Full context above; enlarged right-side controls below.
                thumb = ImageOps.contain(source.convert("RGB"), (295, 430))
                panel = ImageOps.contain(source.crop((width * 0.65, height * 0.18, width, height * 0.9)).convert("RGB"), (295, 550))
            sheet.paste(thumb, (column * 300, 25))
            sheet.paste(panel, (column * 300, 475))
            draw.text((column * 300 + 3, 5), str(index) + " " + Path(record["image"]).stem, fill="black")
        sheet.save(REPORTS / f"visuals/panels_{page}.jpg", quality=95)


if __name__ == "__main__":
    main()
