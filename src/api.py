"""Minimal local HTTP adapter; the detector owns all inference/counting."""
from contextlib import asynccontextmanager
from pathlib import Path
import re
from typing import Annotated
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from src.inference import Detector
from src.inference.config import ROOT
from src.inference.images import ImageInputError, MAX_BYTES
from src.inference.results import Prediction


def create_app(*, detector_factory=Detector, output_dir=None):
    directory = Path(output_dir) if output_dir is not None else ROOT / 'outputs/annotations'

    @asynccontextmanager
    async def lifespan(app):
        app.state.detector = await run_in_threadpool(detector_factory, output_dir=directory)
        try:
            yield
        finally:
            del app.state.detector

    app = FastAPI(title='StoreRoom', version='0.2', lifespan=lifespan)

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/predict', response_model=Prediction)
    async def predict(request: Request, file: Annotated[UploadFile, File()], annotate: bool = True):
        try:
            form = await request.form()
            if sum(isinstance(v, type(file)) for _,v in form.multi_items()) != 1:
                raise HTTPException(400, 'Upload exactly one image')
            if not file.filename:
                raise HTTPException(400, 'Image filename is missing')
            data = await file.read(MAX_BYTES + 1)
            result = await run_in_threadpool(request.app.state.detector.predict, data, annotate=annotate)
            if result.annotated_image:
                result = result.model_copy(update={'annotated_image': '/annotations/' + result.annotated_image})
            return result
        except ImageInputError as e:
            raise HTTPException(e.status_code, str(e)) from e
        finally:
            await file.close()

    @app.get('/annotations/{name}')
    def annotation(name: str):
        if not re.fullmatch(r'[0-9a-f]{32}\.jpg', name):
            raise HTTPException(404, 'Annotation not found')
        path = directory / name
        if not path.is_file():
            raise HTTPException(404, 'Annotation not found')
        return FileResponse(path, media_type='image/jpeg')

    return app


app = create_app()
