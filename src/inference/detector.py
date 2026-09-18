"""One loaded detector, shared by Python callers and the HTTP adapter."""
import hashlib
from pathlib import Path
from threading import Lock
from src.counting import count_classes
from .config import ROOT, load_config
from .images import decode_image
from .results import Prediction, Product, Detection
from .annotation import save_annotation


class Detector:
    def __init__(self, *, output_dir=None, config=None, model_factory=None):
        self.config = config or load_config()
        path = self.config.checkpoint
        if not path.is_file():
            raise FileNotFoundError(f'Frozen AUGMENTATION_001 checkpoint missing: {path}. Restore the recorded local artifact; no download is attempted.')
        with path.open('rb') as f:
            actual = hashlib.file_digest(f, 'sha256').hexdigest()
        if actual != self.config.checkpoint_sha256:
            raise ValueError('Checkpoint SHA-256 mismatch; refusing to load a different model')
        # Reuse the frozen gate; its legacy runtime-settings import does not train.
        from src.class_confidence_predictor import ClassConfidencePredictor
        if model_factory is None:
            from ultralytics import YOLO
            model_factory = YOLO
        self._model = model_factory(str(path))
        if tuple(self._model.names[i] for i in range(len(self.config.names))) != self.config.names:
            raise ValueError('Checkpoint class names do not match the frozen mapping')
        self._predictor = type('ConfiguredPredictor', (ClassConfidencePredictor,),
                               {'thresholds': self.config.thresholds})
        self.output_dir = Path(output_dir) if output_dir is not None else ROOT / 'outputs/annotations'
        self._lock = Lock()  # Ultralytics predictor state is shared across requests

    def predict(self, image, *, annotate=False) -> Prediction:
        bgr = decode_image(image)
        with self._lock:
            raw = self._model.predict(bgr, predictor=self._predictor,
                                      conf=min(self.config.thresholds), **self.config.arguments)[0]
            boxes = raw.boxes
            ids = [int(c) for c in boxes.cls.cpu().tolist()]
            scores = boxes.conf.cpu().tolist()
            coordinates = boxes.xyxy.cpu().tolist()
        counts = count_classes(ids, len(self.config.names))
        products = [Product(class_id=i, class_name=name, product_id=self.config.product_ids[i],
                            count=counts[i], detections=[Detection(confidence=s, bbox=b)
                                for c,s,b in zip(ids,scores,coordinates) if c == i])
                    for i,name in enumerate(self.config.names)]
        result = Prediction(model_id=self.config.model_id, checkpoint_sha256=self.config.checkpoint_sha256,
                            image_width=bgr.shape[1], image_height=bgr.shape[0],
                            products=products, total_count=sum(counts))
        if annotate:
            result.annotated_image = save_annotation(bgr, result, self.output_dir)
        return result
