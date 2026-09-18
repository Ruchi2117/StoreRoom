"""Local confirmed observations. Sessions and transactions never escape this layer."""
from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import URL, create_engine, event, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from src.inference.config import ROOT
from src.review import ConfirmedReview, ReviewItem, ReviewRequest, ScanSummary


class Base(DeclarativeBase):
    pass


class Scan(Base):
    __tablename__ = 'scans'
    __table_args__ = (CheckConstraint("status = 'confirmed'"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # SQLite stores naive timestamps; all timestamps here are UTC.
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(16), default='confirmed')
    items: Mapped[list['ScanItem']] = relationship(back_populates='scan', cascade='all, delete-orphan',
                                                order_by='ScanItem.id')


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
    scan: Mapped[Scan] = relationship(back_populates='items')


def database_path(value=None):
    path = Path(value if value is not None else os.environ.get('STOREROOM_DB_PATH', 'data/storeroom.db'))
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


class ScanStore:
    def __init__(self, path=None):
        self.path = database_path(path)
        self.engine = create_engine(URL.create('sqlite+pysqlite', database=str(self.path)),
                                    connect_args={'check_same_thread': False, 'timeout': 5})

        @event.listens_for(self.engine, 'connect')
        def enable_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)

    def close(self):
        self.engine.dispose()

    @staticmethod
    def result(scan):
        timestamp = scan.created_at.replace(tzinfo=timezone.utc)
        return ConfirmedReview(scan_id=scan.id, created_at=timestamp, confirmed_at=timestamp,
            items=[ReviewItem(class_id=i.class_id, class_name=i.class_name,
                             predicted_count=i.predicted_count, confirmed_count=i.confirmed_count)
                   for i in scan.items])

    def confirm(self, review: ReviewRequest):
        # Parent and every item commit together. Any flush/commit failure rolls back.
        with Session(self.engine) as session, session.begin():
            scan = Scan(id=str(uuid4()), created_at=datetime.now(timezone.utc).replace(tzinfo=None))
            session.add(scan)
            session.flush()
            for item in review.items:
                scan.items.append(ScanItem(**item.model_dump()))
            session.flush()
            result = self.result(scan)
        return result  # Only return a persisted receipt after commit succeeds.

    def recent(self, limit=20):
        if not 1 <= limit <= 100:
            raise ValueError('Limit must be between 1 and 100')
        with Session(self.engine) as session:
            rows = session.execute(select(Scan.id, Scan.created_at, func.count(ScanItem.id))
                .outerjoin(ScanItem).where(Scan.status == 'confirmed').group_by(Scan.id)
                .order_by(Scan.created_at.desc(), Scan.id.desc()).limit(limit))
            return [ScanSummary(scan_id=id, created_at=created.replace(tzinfo=timezone.utc), item_count=count)
                    for id, created, count in rows]

    def get(self, scan_id):
        with Session(self.engine) as session:
            scan = session.get(Scan, str(scan_id))
            return self.result(scan) if scan else None
