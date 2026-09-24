"""Minimal local HTTP adapter; the detector owns all inference/counting."""
from contextlib import asynccontextmanager
from pathlib import Path
import re
from typing import Annotated, Literal
from uuid import UUID
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from src.inference import Detector
from src.inference.config import ROOT
from src.inference.images import ImageInputError, MAX_BYTES
from src.review import ReviewRequest, ConfirmedReview, ScanHistory, EvidencePrediction
from src.storage import ScanStore
from src.evidence import EvidenceError
from src.inference.images import decode_image
from src.inference.annotation import save_annotation
from sqlalchemy.exc import SQLAlchemyError
from src.data_lock import data_lock, DataBusyError
from src.catalog import CatalogStore
from src.alternatives import AlternativeStore, Preferences
from src.orders import OrderStore, OrderRequest, AcceptRequest, RejectRequest, OrderError


def create_app(*, detector_factory=Detector, output_dir=None, database_path=None, scan_storage_dir=None, freshness_seconds=None):
    directory = Path(output_dir) if output_dir is not None else ROOT / 'outputs/annotations'

    @asynccontextmanager
    async def lifespan(app):
        store = ScanStore(database_path, scan_storage_dir)
        with data_lock(store.path, store.evidence.root, 'runtime'):
            try:
                await run_in_threadpool(store.initialize)
                app.state.detector = await run_in_threadpool(detector_factory, output_dir=directory)
                app.state.store = store
                app.state.catalog = CatalogStore(store,freshness_seconds)
                app.state.orders = OrderStore(app.state.catalog)
                yield
            finally:
                await run_in_threadpool(store.close)
                if hasattr(app.state, 'detector'):
                    del app.state.detector

    app = FastAPI(title='StoreRoom', version='1.0', lifespan=lifespan)
    app.mount('/static', StaticFiles(directory=ROOT / 'src/web'), name='static')

    @app.get('/', include_in_schema=False)
    def shopkeeper():
        return FileResponse(ROOT / 'src/web/index.html', headers={'Cache-Control': 'no-cache'})

    @app.get('/customer', include_in_schema=False)
    def customer():
        return FileResponse(ROOT/'src/web/customer.html',headers={'Cache-Control':'no-cache'})

    @app.get('/customer/orders', include_in_schema=False)
    @app.get('/shopkeeper/orders', include_in_schema=False)
    def order_page():
        return FileResponse(ROOT/'src/web/orders.html',headers={'Cache-Control':'no-cache'})

    @app.post('/orders')
    def create_order(body: OrderRequest, request: Request):
        return JSONResponse(request.app.state.orders.create(body),headers={'Cache-Control':'no-store'})

    @app.get('/orders')
    def order_history(request: Request, shop_id: Annotated[str | None,Query(max_length=100)]=None,
                      status: Literal['PENDING','ACCEPTED','REJECTED','CANCELLED'] | None=None,
                      limit: Annotated[int,Query(ge=1,le=100)]=50, offset: Annotated[int,Query(ge=0)]=0):
        return JSONResponse({'orders':request.app.state.orders.history(shop_id,status,limit,offset)},headers={'Cache-Control':'no-store'})

    @app.get('/orders/{order_id}')
    def order_detail(order_id: UUID, request: Request):
        result = request.app.state.orders.get(order_id)
        if result is None:
            raise OrderError('Order not found',404)
        return JSONResponse(result,headers={'Cache-Control':'no-store'})

    @app.post('/orders/{order_id}/accept')
    def accept_order(order_id: UUID, body: AcceptRequest, request: Request):
        return JSONResponse(request.app.state.orders.transition(order_id,'ACCEPTED',confirmed=body.availability_confirmed),headers={'Cache-Control':'no-store'})

    @app.post('/orders/{order_id}/reject')
    def reject_order(order_id: UUID, body: RejectRequest, request: Request):
        return JSONResponse(request.app.state.orders.transition(order_id,'REJECTED',reason=body.reason),headers={'Cache-Control':'no-store'})

    @app.post('/orders/{order_id}/cancel')
    def cancel_order(order_id: UUID, request: Request):
        return JSONResponse(request.app.state.orders.transition(order_id,'CANCELLED'),headers={'Cache-Control':'no-store'})

    @app.exception_handler(OrderError)
    async def order_error(request, error):
        return JSONResponse(status_code=error.status_code,content={'detail':str(error)},headers={'Cache-Control':'no-store'})

    @app.get('/products/search')
    def products(request: Request, q: Annotated[str,Query(max_length=100)]=''):
        return {'products':request.app.state.catalog.search(q)}

    @app.get('/products/{product_id}/alternatives')
    def alternatives(product_id: str, request: Request):
        return preferred_alternatives(product_id, Preferences(), request)

    @app.post('/products/{product_id}/alternatives')
    def preferred_alternatives(product_id: str, preferences: Preferences, request: Request):
        result = AlternativeStore(request.app.state.catalog).find(product_id, preferences)
        if result is None:
            raise HTTPException(404, 'Product not found')
        # Preference bodies are transient; do not cache them or place them in URLs.
        return JSONResponse(result, headers={'Cache-Control': 'no-store'})

    @app.post('/inventory/confirm', response_model=ConfirmedReview)
    def confirm(review: ReviewRequest, request: Request):
        return request.app.state.store.confirm(review)

    @app.get('/inventory/scans', response_model=ScanHistory)
    def history(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 20):
        return ScanHistory(scans=request.app.state.store.recent(limit))

    @app.get('/inventory/scans/{scan_id}', response_model=ConfirmedReview)
    def scan(scan_id: UUID, request: Request):
        result = request.app.state.store.get(scan_id)
        if result is None:
            raise HTTPException(404, 'Scan not found')
        return result

    @app.get('/inventory/scans/{scan_id}/original')
    def original_image(scan_id: UUID, request: Request):
        path = request.app.state.store.image(scan_id, 'original')
        if path is None:
            raise HTTPException(404, 'Original image not found')
        return FileResponse(path, media_type='image/png' if path.suffix == '.png' else 'image/jpeg')

    @app.get('/inventory/scans/{scan_id}/annotated')
    def annotated_image(scan_id: UUID, request: Request):
        path = request.app.state.store.image(scan_id, 'annotated')
        if path is None:
            raise HTTPException(404, 'Annotated image not found')
        return FileResponse(path, media_type='image/jpeg')

    @app.get('/inventory')
    def inventory(request: Request, product_id: Annotated[str | None,Query(max_length=100)]=None,
                  shop_id: Annotated[str | None,Query(max_length=100)]=None,
                  availability: Literal['available','unavailable','stale','demo'] | None=None):
        return {'inventory':request.app.state.catalog.inventory(product_id,shop_id,availability)}

    # Register after existing /inventory/scans routes to preserve their contracts.
    @app.get('/inventory/{product_id}')
    def product_inventory(product_id: str, request: Request, shop_id: Annotated[str | None,Query(max_length=100)]=None,
                          availability: Literal['available','unavailable','stale','demo'] | None=None):
        catalog = request.app.state.catalog
        product = catalog.product(product_id)
        if product is None:
            raise HTTPException(404,'Product not found')
        return {'product':product,'inventory':catalog.inventory(product_id,shop_id,availability)}

    @app.exception_handler(EvidenceError)
    async def evidence_error(request, error):
        return JSONResponse(status_code=error.status_code, content={'detail': str(error)})

    @app.exception_handler(OSError)
    async def image_storage_error(request, error):
        return JSONResponse(status_code=503, content={'detail': 'Image storage is unavailable. Your scan was not completed; check history before retrying.'})

    @app.exception_handler(DataBusyError)
    async def data_busy(request, error):
        return JSONResponse(status_code=503, content={'detail': str(error)})

    @app.exception_handler(SQLAlchemyError)
    async def storage_error(request, error):
        # Never expose SQL statements, local database paths or driver messages.
        return JSONResponse(status_code=503, content={'detail':
            'Scan storage is unavailable. If saving was interrupted, check Scan History before confirming again.'})

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/predict', response_model=EvidencePrediction)
    async def predict(request: Request, file: Annotated[UploadFile, File()], annotate: bool = True):
        try:
            form = await request.form()
            if sum(isinstance(v, type(file)) for _,v in form.multi_items()) != 1:
                raise HTTPException(400, 'Upload exactly one image')
            if not file.filename:
                raise HTTPException(400, 'Image filename is missing')
            data = await file.read(MAX_BYTES + 1)
            result = await run_in_threadpool(request.app.state.detector.predict, data, annotate=annotate)
            # Rendering from saved detections is allowed; never run the model twice.
            name = result.annotated_image
            if name is None:
                name = await run_in_threadpool(save_annotation, decode_image(data), result, directory)
            annotated_bytes = await run_in_threadpool((directory / name).read_bytes)
            prediction_id = await run_in_threadpool(request.app.state.store.evidence.stage, data, annotated_bytes, result)
            if result.annotated_image:
                result = result.model_copy(update={'annotated_image': '/annotations/' + result.annotated_image})
            return EvidencePrediction(**result.model_dump(), prediction_id=prediction_id)
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
