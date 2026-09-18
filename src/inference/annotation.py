"""Render saved detections only; no model calls."""
from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageDraw, ImageFont
from .config import ROOT


def save_annotation(bgr, result, output_dir):
    directory = Path(output_dir).resolve()
    if directory.is_relative_to(ROOT) and not directory.is_relative_to(ROOT / 'outputs'):
        raise ValueError('Repository annotations must be written under outputs/')
    directory.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(bgr[:, :, ::-1])
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(12, round(min(image.size) / 65)))
    line_width = max(2, round(min(image.size) / 500))
    colors = ['#ff4545', '#ffd500', '#35e3ff', '#59ff64', '#ff72ff']
    for product in result.products:
        for detection in product.detections:
            box = detection.bbox
            color = colors[product.class_id % len(colors)]
            draw.rectangle(box, outline=color, width=line_width)
            label = f'{product.class_name} {detection.confidence:.2f}'
            bounds = draw.textbbox((0, 0), label, font=font)
            x = max(0, min(box[0], image.width - bounds[2] - 4))
            y = max(0, box[1] - bounds[3] - 4)
            draw.rectangle((x, y, x + bounds[2] + 4, y + bounds[3] + 4), fill=color)
            draw.text((x + 2, y + 2), label, fill='black', font=font)
    name = uuid4().hex + '.jpg'
    with (directory / name).open('xb') as f:
        image.save(f, format='JPEG', quality=90)
    return name
