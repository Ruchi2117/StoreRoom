"""Deterministic pipeline/API tests; no trained model predictions."""
import hashlib
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import numpy as np
import torch
from PIL import Image
from pydantic import ValidationError
from fastapi.testclient import TestClient
from src.inference import Detector
from src.inference.config import load_config, ROOT
from src.inference.images import decode_image, ImageInputError, MAX_BYTES
from src.inference.results import Prediction
from src.api import create_app


def image_bytes(fmt='PNG'):
    stream=BytesIO()
    Image.new('RGB',(32,24),'white').save(stream,format=fmt)
    return stream.getvalue()


class FakeModel:
    def __init__(self,names,empty=False):
        self.names=dict(enumerate(names)); self.calls=[]; self.empty=empty
    def predict(self,image,**kwargs):
        self.calls.append(kwargs)
        boxes=SimpleNamespace(cls=torch.tensor([] if self.empty else [0,1,1]),
            conf=torch.tensor([] if self.empty else [.2,.8,.7]),
            xyxy=torch.empty((0,4)) if self.empty else torch.tensor([[1.,2.,8.,10.],[10.,2.,15.,12.],[17.,2.,22.,12.]]))
        return [SimpleNamespace(boxes=boxes)]


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        checkpoint=self.directory/'fixture.pt'; checkpoint.write_bytes(b'test-only checkpoint')
        self.config=replace(load_config(),checkpoint=checkpoint,
            checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest())
        self.backend=FakeModel(self.config.names)
        self.loader=Mock(return_value=self.backend)
    def detector(self,**kwargs):
        return Detector(config=self.config,model_factory=self.loader,output_dir=self.directory/'annotations',**kwargs)

    def test_frozen_profile(self):
        c=load_config()
        self.assertEqual(c.checkpoint,ROOT/'runs/augmentation_001/weights/best.pt')
        self.assertEqual(c.arguments['imgsz'],320)
        self.assertEqual(c.arguments['iou'],.5)
        self.assertEqual(c.thresholds,(.15,.25,.25,.25,.25))
        self.assertFalse(c.arguments['agnostic_nms'])
        self.assertEqual(c.names[0],'Red Bull')

    def test_load_once_and_reuse_frozen_predictor(self):
        detector=self.detector()
        for _ in range(2): detector.predict(image_bytes())
        self.loader.assert_called_once()
        self.assertEqual(len(self.backend.calls),2)
        from src.class_confidence_predictor import ClassConfidencePredictor
        args=self.backend.calls[0]
        self.assertTrue(issubclass(args['predictor'],ClassConfidencePredictor))
        self.assertEqual(args['predictor'].thresholds,self.config.thresholds)
        self.assertEqual(args['conf'],min(self.config.thresholds))
        self.assertEqual({k:args[k] for k in self.config.arguments},self.config.arguments)

    def test_structure_counts_and_annotation_single_pass(self):
        detector=self.detector()
        result=detector.predict(image_bytes(),annotate=True)
        self.assertEqual(result.total_count,3)
        self.assertEqual([p.count for p in result.products],[1,2,0,0,0])
        self.assertEqual(result.image_width,32)
        self.assertEqual(result.image_height,24)
        self.assertTrue(all(p.class_name for p in result.products))
        self.assertTrue(all(type(p.count) is int for p in result.products))
        self.assertEqual(len(self.backend.calls),1)
        path=detector.output_dir/result.annotated_image
        with Image.open(path) as img:
            self.assertEqual(img.size,(32,24))
            self.assertNotEqual(np.asarray(img).min(),255)
        self.assertEqual(Prediction.model_validate_json(result.model_dump_json()),result)

    def test_empty_detections_include_five_zeros(self):
        self.backend.empty=True
        r=self.detector().predict(image_bytes())
        self.assertEqual(r.total_count,0)
        self.assertEqual(len(r.products),5)
        self.assertTrue(all(p.count==0 and p.detections==[] for p in r.products))
        self.assertIsNone(r.annotated_image)

    def test_missing_or_changed_checkpoint_fails_before_loader(self):
        self.config.checkpoint.unlink()
        with self.assertRaisesRegex(FileNotFoundError,'checkpoint missing'): self.detector()
        self.config.checkpoint.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'SHA-256'): self.detector()
        self.loader.assert_not_called()

    def test_wrong_class_mapping_rejected(self):
        self.backend.names[0]='wrong'
        with self.assertRaisesRegex(ValueError,'class names'): self.detector()

    def test_input_types_and_errors(self):
        path=self.directory/'valid.png'; path.write_bytes(image_bytes())
        np.testing.assert_array_equal(decode_image(path),decode_image(image_bytes()))
        np.testing.assert_array_equal(decode_image(image_bytes('JPEG')),decode_image(image_bytes()))
        array=np.zeros((10,10,3),dtype=np.uint8)
        self.assertIsNot(decode_image(array),array)
        for source,code in [(b'',400),(b'not an image',422),(image_bytes()[:30],422),
                            (image_bytes('GIF'),415),(self.directory/'missing.jpg',400),
                            (b'x'*(MAX_BYTES+1),413),(np.zeros((3,3)),422)]:
            with self.subTest(code=code,kind=type(source)):
                with self.assertRaises(ImageInputError) as e: decode_image(source)
                self.assertEqual(e.exception.status_code,code)

    def test_result_rejects_invalid_counts(self):
        result=self.detector().predict(image_bytes()).model_dump()
        result['total_count']=99
        with self.assertRaises(ValidationError): Prediction.model_validate(result)
        result['total_count']=3; result['products'][0]['count']=-1
        with self.assertRaises(ValidationError): Prediction.model_validate(result)

    def test_annotations_cannot_overwrite_research_directories(self):
        detector=self.detector(); detector.output_dir=ROOT/'reports/visuals'
        with self.assertRaisesRegex(ValueError,'outputs'): detector.predict(image_bytes(),annotate=True)

    def test_http_uses_same_detector_and_schema(self):
        detector=self.detector(); factory=Mock(return_value=detector)
        expected=detector.predict(image_bytes()).model_dump(mode='json')
        with TestClient(create_app(detector_factory=factory,output_dir=detector.output_dir)) as client:
            self.assertEqual(client.get('/health').json(),{'status':'ok'})
            response=client.post('/predict?annotate=false',files={'file':('shelf.png',image_bytes(),'image/png')})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json(),expected)
            response=client.post('/predict',files={'file':('shelf.png',image_bytes(),'image/png')})
            self.assertEqual(response.status_code,200,response.text)
            result=Prediction.model_validate(response.json())
            annotated=client.get(result.annotated_image)
            self.assertEqual(annotated.status_code,200)
            self.assertEqual(annotated.headers['content-type'],'image/jpeg')
            self.assertEqual(client.get('/annotations/not-a-result.jpg').status_code,404)
            self.assertEqual(len(self.backend.calls),3)
        factory.assert_called_once()
        self.loader.assert_called_once()

    def test_http_invalid_and_multiple_uploads(self):
        detector=self.detector()
        with TestClient(create_app(detector_factory=lambda **_:detector)) as client:
            self.assertEqual(client.post('/predict').status_code,422)
            for data,code in [(b'',400),(b'no image',422),(image_bytes()[:25],422),(image_bytes('GIF'),415)]:
                response=client.post('/predict',files={'file':('input.png',data,'image/png')})
                self.assertEqual(response.status_code,code,response.text)
            response=client.post('/predict',files=[('file',('a.png',image_bytes())),('file',('b.png',image_bytes()))])
            self.assertEqual(response.status_code,400,response.text)
        self.assertEqual(len(self.backend.calls),0)

    def test_startup_failure_is_explicit(self):
        def missing(**_): raise FileNotFoundError('checkpoint missing')
        with self.assertRaisesRegex(FileNotFoundError,'checkpoint missing'):
            with TestClient(create_app(detector_factory=missing)): pass
