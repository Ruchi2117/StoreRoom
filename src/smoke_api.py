"""Explicit one-image local runtime check; never called by unit-test discovery."""
from io import BytesIO
import json
import socket
from threading import Thread
import time
import httpx
from PIL import Image
import uvicorn
from src.api import create_app
from src.inference.config import ROOT
from src.inference.results import Prediction


def main():
    # Deliberately ordinary validation, never the protected test partition.
    image = ROOT / 'data/yolo_v01/images/val/IMG_20181218_170247.jpg'
    if not image.is_file():
        raise FileNotFoundError(image)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    address = f'http://127.0.0.1:{listener.getsockname()[1]}'
    server = uvicorn.Server(uvicorn.Config(create_app(), log_level='info'))
    thread = Thread(target=server.run, kwargs={'sockets': [listener]})
    thread.start()
    record = {}
    try:
        deadline = time.monotonic() + 120
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('API startup failed or timed out')
            time.sleep(0.1)
        with httpx.Client(base_url=address, timeout=120) as client:
            health = client.get('/health')
            assert health.status_code == 200 and health.json() == {'status': 'ok'}
            with image.open('rb') as stream:
                response = client.post('/predict', files={'file': (image.name, stream, 'image/jpeg')})
            assert response.status_code == 200, response.text
            prediction = Prediction.model_validate(response.json())
            assert len(prediction.products) == 5 and prediction.total_count > 0
            annotation = client.get(prediction.annotated_image)
            assert annotation.status_code == 200
            with Image.open(BytesIO(annotation.content)) as rendered:
                rendered.load()
                assert rendered.size == (prediction.image_width, prediction.image_height)
            invalid = client.post('/predict', files={'file': ('bad.jpg', b'not an image', 'image/jpeg')})
            assert invalid.status_code == 422, invalid.text
            record = {
                'purpose': 'single-image runtime smoke only, no accuracy evaluation',
                'image': image.relative_to(ROOT).as_posix(), 'split': 'val',
                'health_status': health.status_code, 'predict_status': response.status_code,
                'annotation_status': annotation.status_code, 'invalid_upload_status': invalid.status_code,
                'prediction': prediction.model_dump(mode='json'),
                'retraining': False, 'test_set_evaluation': False,
            }
    finally:
        server.should_exit = True
        thread.join(timeout=30)
        listener.close()
        if thread.is_alive():
            raise RuntimeError('API did not shut down cleanly')
    record['server_stopped_cleanly'] = True
    destination = ROOT / 'reports/v0_2_smoke.json'
    destination.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
