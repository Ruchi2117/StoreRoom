"""Decode photographed machine stickers as grouping evidence, without visiting URLs."""
import json
from PIL import Image
import zxingcpp
from src.preflight import DATA, REPORTS, save_json


def main():
    records = json.loads((REPORTS / "image_manifest.json").read_text(encoding="utf-8"))
    output = []
    for index, record in enumerate(records):
        with Image.open(DATA / record["image"]) as source:
            codes = zxingcpp.read_barcodes(source.convert("RGB"), formats=zxingcpp.BarcodeFormat.QRCode)
        output.append({"image": record["image"], "review_index": record["review_index"],
                       "codes": [{"text": code.text, "position": str(code.position)} for code in codes]})
        if codes:
            print(record["review_index"], record["image"], [code.text for code in codes], flush=True)
        elif index % 50 == 0:
            print(f"Scanned {index + 1} images", flush=True)
    save_json(REPORTS / "machine_codes.json", output)
    print("Images with a readable QR code:", sum(bool(row["codes"]) for row in output))


if __name__ == "__main__":
    main()
