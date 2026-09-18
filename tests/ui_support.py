"""Deterministic web fixtures; no checkpoint load, dataset read or model inference."""
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
import socket
from threading import Thread
import time
from PIL import Image
import uvicorn
from src.api import create_app
from src.inference.config import load_config
from src.inference.images import decode_image
from src.inference.results import Prediction, Product, Detection


def photo_bytes():
    stream = BytesIO()
    Image.new('RGB', (320, 240), '#edf0e5').save(stream, format='PNG')
    return stream.getvalue()


class FixtureDetector:
    def __init__(self, *, output_dir):
        self.directory = Path(output_dir)
        self.calls = 0
        self.empty = False

    def predict(self, data, *, annotate):
        decode_image(data)  # same validation path, but no model
        self.calls += 1
        config = load_config()
        products = []
        for i, name in enumerate(config.names):
            count = 0 if self.empty else (2 if i == 0 else 1 if i == 2 else 0)
            products.append(Product(class_id=i, class_name=name, product_id=config.product_ids[i],
                count=count, detections=[Detection(confidence=.8, bbox=(1, 1, 10, 10)) for _ in range(count)]))
        filename = 'a' * 32 + '.jpg'
        self.directory.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (320, 240), '#edf0e5').save(self.directory / filename)
        return Prediction(model_id=config.model_id, checkpoint_sha256=config.checkpoint_sha256,
            image_width=320, image_height=240, products=products,
            total_count=sum(p.count for p in products), annotated_image=filename if annotate else None)


@contextmanager
def local_server(app):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    url = f'http://127.0.0.1:{listener.getsockname()[1]}'
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning'))
    thread = Thread(target=server.run, kwargs={'sockets': [listener]})
    thread.start()
    try:
        deadline = time.monotonic() + 60
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('Local API startup failed')
            time.sleep(.05)
        yield url
    finally:
        server.should_exit = True
        thread.join(30)
        listener.close()
        if thread.is_alive():
            raise RuntimeError('Local server did not stop')
