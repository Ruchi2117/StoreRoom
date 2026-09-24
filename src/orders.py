"""Local order requests. Accepted items are reservations, never rewritten observations."""
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Annotated
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship
from src.storage import Base
from src.catalog import CatalogProduct, Shop, ShopInventory, iso
from src.data_lock import data_lock

CUSTOMER_ID = 'demo_customer'


class DemoCustomer(Base):
    __tablename__ = 'demo_customers'
    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)


class Order(Base):
    __tablename__ = 'orders'
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','ACCEPTED','REJECTED','CANCELLED')"),
        CheckConstraint("(status='PENDING' AND accepted_at IS NULL AND rejected_at IS NULL AND cancelled_at IS NULL) OR "
                        "(status='ACCEPTED' AND accepted_at IS NOT NULL AND rejected_at IS NULL AND cancelled_at IS NULL) OR "
                        "(status='REJECTED' AND accepted_at IS NULL AND rejected_at IS NOT NULL AND cancelled_at IS NULL) OR "
                        "(status='CANCELLED' AND accepted_at IS NULL AND rejected_at IS NULL AND cancelled_at IS NOT NULL)"),
        CheckConstraint("status='REJECTED' OR rejection_reason IS NULL"),
    )
    order_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('demo_customers.customer_id', ondelete='RESTRICT'))
    shop_id: Mapped[str] = mapped_column(ForeignKey('shops.shop_id', ondelete='RESTRICT'), index=True)
    shop_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejection_reason: Mapped[str | None] = mapped_column(String)
    items: Mapped[list['OrderItem']] = relationship(order_by='OrderItem.product_id')


class OrderItem(Base):
    __tablename__ = 'order_items'
    __table_args__ = (UniqueConstraint('order_id','product_id'),
                     CheckConstraint("typeof(quantity)='integer' AND quantity BETWEEN 1 AND 100"),)
    order_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.order_id', ondelete='RESTRICT'), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.product_id', ondelete='RESTRICT'))
    product_name: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer)


def seed_customer(connection):
    if not connection.execute(select(DemoCustomer.customer_id).where(DemoCustomer.customer_id==CUSTOMER_ID)).first():
        connection.execute(DemoCustomer.__table__.insert().values(customer_id=CUSTOMER_ID,name='Demo Customer'))


def reserved_quantity(session, shop_id, product_id):
    return session.scalar(select(func.coalesce(func.sum(OrderItem.quantity),0)).join(Order).where(
        Order.shop_id==shop_id, Order.status=='ACCEPTED', OrderItem.product_id==product_id))


class ItemRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: Annotated[str, Field(min_length=1,max_length=100)]
    quantity: Annotated[int, Field(strict=True,ge=1,le=100)]


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    shop_id: Annotated[str, Field(min_length=1,max_length=100)]
    items: Annotated[list[ItemRequest], Field(min_length=1,max_length=5)]

    @model_validator(mode='after')
    def unique_products(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError('Each product may appear only once')
        return self


class AcceptRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    availability_confirmed: Annotated[bool, Field(strict=True)]


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: Annotated[str, Field(max_length=200)] | None = None


class OrderError(ValueError):
    def __init__(self, message, status_code=409):
        super().__init__(message)
        self.status_code = status_code


def serialize(order):
    return {'order_id':order.order_id, 'request_id':order.request_id,
        'customer_id':order.customer_id, 'customer_name':'Demo Customer', 'prototype_identity':True,
        'shop_id':order.shop_id, 'shop_name':order.shop_name, 'status':order.status,
        **{key:iso(getattr(order,key)) for key in ('created_at','updated_at','accepted_at','rejected_at','cancelled_at')},
        'rejection_reason':order.rejection_reason,
        'items':[{'product_id':i.product_id,'product_name':i.product_name,'quantity':i.quantity} for i in order.items]}


class OrderStore:
    def __init__(self, catalog):
        self.catalog = catalog
        self.store = catalog.store
        self._lock = Lock()

    @contextmanager
    def transaction(self):
        # Cooperative lock also coordinates snapshots. SQLite's write lock protects
        # the read/check/reserve sequence even across independent engine connections.
        with self._lock, data_lock(self.store.path,self.store.evidence.root), Session(self.store.engine) as session, session.begin():
            session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            yield session

    def inventory(self, session, shop_id, product_id, now):
        row = session.get(ShopInventory,(shop_id,product_id))
        if row is None:
            raise OrderError('Shop has no inventory observation for this product')
        age = (now-row.last_confirmed_at).total_seconds() if row.last_confirmed_at else None
        if row.is_demo or age is None or not 0 <= age <= self.catalog.fresh_seconds:
            raise OrderError('A fresh reviewed shelf count is required. Re-scan and confirm availability first.')
        return row.quantity-reserved_quantity(session,shop_id,product_id)

    def create(self, request):
        with self.transaction() as session:
            existing = session.scalar(select(Order).where(Order.request_id==str(request.request_id)))
            if existing:
                pairs = sorted((i.product_id,i.quantity) for i in request.items)
                if existing.shop_id!=request.shop_id or pairs!=sorted((i.product_id,i.quantity) for i in existing.items):
                    raise OrderError('Request ID was already used for different items')
                return serialize(existing)
            shop = session.get(Shop,request.shop_id)
            if shop is None:
                raise OrderError('Shop not found',404)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            items = []
            for item in request.items:
                product = session.get(CatalogProduct,item.product_id)
                if product is None:
                    raise OrderError('Product not found',404)
                if self.inventory(session,request.shop_id,item.product_id,now)<=0:
                    raise OrderError('No unreserved units are currently recorded for this product')
                # Intent may exceed the observation; only acceptance can promise a reservation.
                items.append(OrderItem(product_id=item.product_id,product_name=product.name,quantity=item.quantity))
            order = Order(order_id=str(uuid4()), request_id=str(request.request_id), customer_id=CUSTOMER_ID,
                shop_id=shop.shop_id, shop_name=shop.name, status='PENDING', created_at=now, updated_at=now,items=items)
            session.add(order)
            session.flush()
            return serialize(order)

    def transition(self, order_id, target, *, confirmed=False, reason=None):
        if target not in {'ACCEPTED','REJECTED','CANCELLED'}:
            raise OrderError('Invalid order transition')
        reason = (reason or '').strip() or None
        with self.transaction() as session:
            order = session.get(Order,str(order_id))
            if order is None:
                raise OrderError('Order not found',404)
            if order.status==target:
                if target=='REJECTED' and order.rejection_reason!=reason:
                    raise OrderError('A completed rejection cannot be edited')
                return serialize(order)  # Safe retry; no second reservation.
            if order.status!='PENDING':
                raise OrderError('Only pending requests can be accepted, rejected or cancelled')
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if target=='ACCEPTED':
                if confirmed is not True:
                    raise OrderError('Confirm current availability before accepting')
                for item in order.items:
                    available = self.inventory(session,order.shop_id,item.product_id,now)
                    if available < item.quantity:
                        raise OrderError(f'Insufficient inventory for {item.product_name}: {max(0,available)} unreserved, {item.quantity} requested. Request remains pending.')
            order.status, order.updated_at = target, now
            setattr(order,target.lower()+'_at',now)
            if target=='REJECTED':
                order.rejection_reason = reason
            session.flush()
            return serialize(order)

    def get(self, order_id):
        with Session(self.store.engine) as session:
            order = session.get(Order,str(order_id))
            return serialize(order) if order else None

    def history(self, shop_id=None, status=None, limit=50, offset=0):
        with Session(self.store.engine) as session:
            query = select(Order).where(Order.customer_id==CUSTOMER_ID)
            if shop_id is not None:
                query = query.where(Order.shop_id==shop_id)
            if status is not None:
                query = query.where(Order.status==status)
            query = query.order_by(Order.created_at.desc(),Order.order_id.desc()).limit(limit).offset(offset)
            return [serialize(order) for order in session.scalars(query)]
