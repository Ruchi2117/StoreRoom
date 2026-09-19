"""Local confirmed observations. Sessions and transactions never escape this layer."""
from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4
from threading import Lock
from sqlalchemy import Boolean, Float, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import URL, create_engine, event, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from src.inference.config import ROOT
from src.review import ConfirmedReview, ReviewItem, ReviewRequest, ScanSummary
from src.review import StoredDetection
from src.inference.results import Prediction, Product, Detection
from src.evidence import EvidenceFiles, EvidenceError
from src.migrations import initialize_schema
from src.data_lock import data_lock


class Base(DeclarativeBase):
    pass


class Scan(Base):
    __tablename__ = 'scans'
    __table_args__ = (CheckConstraint("status = 'confirmed'"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # SQLite stores naive timestamps; all timestamps here are UTC.
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(16), default='confirmed')
    source_image_path: Mapped[str | None] = mapped_column(String)
    annotated_image_path: Mapped[str | None] = mapped_column(String)
    prediction_id: Mapped[str | None] = mapped_column(String(36))
    model_id: Mapped[str | None] = mapped_column(String)
    checkpoint_sha256: Mapped[str | None] = mapped_column(String(64))
    image_width: Mapped[int | None] = mapped_column(Integer)
    image_height: Mapped[int | None] = mapped_column(Integer)
    items: Mapped[list['ScanItem']] = relationship(back_populates='scan', cascade='all, delete-orphan',
                                                order_by='ScanItem.id')
    detections: Mapped[list['ScanDetection']] = relationship(cascade='all, delete-orphan', order_by='ScanDetection.id')


class ScanItem(Base):
    __tablename__ = 'scan_items'
    __table_args__ = (
        UniqueConstraint('scan_id', 'class_id'),
        CheckConstraint('class_id >= 0 AND class_id < 5'),
        CheckConstraint("typeof(predicted_count) = 'integer' AND predicted_count BETWEEN 0 AND 9007199254740991"),
        CheckConstraint("typeof(confirmed_count) = 'integer' AND confirmed_count BETWEEN 0 AND 9007199254740991"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey('scans.id', ondelete='CASCADE'), index=True)
    class_id: Mapped[int] = mapped_column(Integer)
    class_name: Mapped[str] = mapped_column(String(100))
    predicted_count: Mapped[int] = mapped_column(Integer)
    confirmed_count: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[str | None] = mapped_column(String)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=True)
    scan: Mapped[Scan] = relationship(back_populates='items')


class ScanDetection(Base):
    __tablename__ = 'scan_detections'
    __table_args__ = (CheckConstraint('confidence >= 0 AND confidence <= 1'),
                      CheckConstraint('x1 >= 0 AND y1 >= 0 AND x2 >= x1 AND y2 >= y1'))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey('scans.id', ondelete='CASCADE'), index=True)
    class_id: Mapped[int] = mapped_column(Integer)
    class_name: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float)
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    x2: Mapped[float] = mapped_column(Float)
    y2: Mapped[float] = mapped_column(Float)


def database_path(value=None):
    path = Path(value if value is not None else os.environ.get('STOREROOM_DB_PATH', 'data/storeroom.db'))
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


class ScanStore:
    def __init__(self, path=None, scan_storage_dir=None):
        self.path = database_path(path)
        self.evidence = EvidenceFiles(scan_storage_dir)
        self._confirmation_lock = Lock()
        self.engine = create_engine(URL.create('sqlite+pysqlite', database=str(self.path)),
                                    connect_args={'check_same_thread': False, 'timeout': 5})

        @event.listens_for(self.engine, 'connect')
        def enable_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with data_lock(self.path, self.evidence.root):
            initialize_schema(self.engine, Base.metadata)

    def close(self):
        self.engine.dispose()

    @staticmethod
    def result(scan):
        timestamp = scan.created_at.replace(tzinfo=timezone.utc)
        detections = [StoredDetection(class_id=d.class_id, class_name=d.class_name,
            confidence=d.confidence, bbox=(d.x1, d.y1, d.x2, d.y2)) for d in scan.detections]
        original = f'/inventory/scans/{scan.id}/original' if scan.source_image_path else None
        annotated = f'/inventory/scans/{scan.id}/annotated' if scan.annotated_image_path else None
        prediction = None
        if scan.prediction_id:
            products = [Product(class_id=i.class_id, class_name=i.class_name, product_id=i.product_id,
                count=i.predicted_count, detections=[Detection(confidence=d.confidence, bbox=d.bbox)
                    for d in detections if d.class_id == i.class_id]) for i in scan.items]
            prediction = Prediction(model_id=scan.model_id, checkpoint_sha256=scan.checkpoint_sha256,
                image_width=scan.image_width, image_height=scan.image_height, products=products,
                total_count=sum(p.count for p in products), annotated_image=annotated)
        return ConfirmedReview(scan_id=scan.id, created_at=timestamp, confirmed_at=timestamp,
            prediction_id=scan.prediction_id, original_image_url=original, annotated_image_url=annotated,
            original_prediction=prediction, detections=detections,
            items=[ReviewItem(class_id=i.class_id, class_name=i.class_name,
                             predicted_count=i.predicted_count, confirmed_count=i.confirmed_count)
                   for i in scan.items if i.reviewed])

    def confirm(self, review: ReviewRequest):
        # Serialize promotion/retries within the supported single-process deployment.
        with self._confirmation_lock, data_lock(self.path, self.evidence.root):
            with Session(self.engine) as session:
                previous = session.scalar(select(Scan).where(Scan.prediction_id == str(review.prediction_id)))
                if previous:
                    result = self.result(previous)
                    if sorted(result.items, key=lambda i:i.class_id) != sorted(review.items, key=lambda i:i.class_id):
                        raise EvidenceError('This prediction was already confirmed with different counts')
                    return result
            manifest, prediction = self.evidence.read(review.prediction_id)
            submitted = {i.class_id: i for i in review.items}
            for product in prediction.products:
                item = submitted.get(product.class_id)
                if item and (item.predicted_count != product.count or item.class_name != product.class_name):
                    raise EvidenceError('Original AI prediction cannot be changed', 422)
                if product.count and item is None:
                    raise EvidenceError('Review every detected product before confirming', 422)
            scan_id = str(uuid4())
            published = False
            try:
                original, annotated = self.evidence.publish(review.prediction_id, scan_id, manifest)
                published = True
                with Session(self.engine) as session, session.begin():
                    scan = Scan(id=scan_id, created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        prediction_id=str(review.prediction_id), source_image_path=original,
                        annotated_image_path=annotated, model_id=prediction.model_id,
                        checkpoint_sha256=prediction.checkpoint_sha256,
                        image_width=prediction.image_width, image_height=prediction.image_height)
                    session.add(scan)
                    session.flush()
                    for product in prediction.products:
                        item = submitted.get(product.class_id)
                        scan.items.append(ScanItem(class_id=product.class_id, class_name=product.class_name,
                            product_id=product.product_id, predicted_count=product.count,
                            confirmed_count=item.confirmed_count if item else 0, reviewed=item is not None))
                        for d in product.detections:
                            scan.detections.append(ScanDetection(class_id=product.class_id,
                                class_name=product.class_name, confidence=d.confidence,
                                x1=d.bbox[0], y1=d.bbox[1], x2=d.bbox[2], y2=d.bbox[3]))
                    session.flush()
                    result = self.result(scan)
            except Exception:
                # If commit outcome cannot be checked, preserve files for recovery rather than
                # risk removing committed evidence. Normal rollback removes only this UUID dir.
                with Session(self.engine) as check:
                    committed = check.get(Scan, scan_id)
                    if committed:
                        return self.result(committed)
                if published:
                    self.evidence.cleanup(scan_id)
                raise
            # A pending draft is disposable only after its committed evidence is safely present.
            try:
                self.evidence.cleanup(review.prediction_id, pending=True)
            except (OSError, EvidenceError):
                pass  # A leftover pending draft is safer than undoing a committed scan.
            return result

    def recent(self, limit=20):
        if not 1 <= limit <= 100:
            raise ValueError('Limit must be between 1 and 100')
        with Session(self.engine) as session:
            rows = session.execute(select(Scan.id, Scan.created_at, func.count(ScanItem.id))
                .outerjoin(ScanItem, (ScanItem.scan_id == Scan.id) & ScanItem.reviewed).where(Scan.status == 'confirmed').group_by(Scan.id)
                .order_by(Scan.created_at.desc(), Scan.id.desc()).limit(limit))
            return [ScanSummary(scan_id=id, created_at=created.replace(tzinfo=timezone.utc), item_count=count)
                    for id, created, count in rows]

    def get(self, scan_id):
        with Session(self.engine) as session:
            scan = session.get(Scan, str(scan_id))
            return self.result(scan) if scan else None

    def image(self, scan_id, kind):
        with Session(self.engine) as session:
            scan = session.get(Scan, str(scan_id))
            if not scan:
                return None
            reference = scan.source_image_path if kind == 'original' else scan.annotated_image_path
            return self.evidence.image(str(scan_id), reference, kind)
