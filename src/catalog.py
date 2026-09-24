"""Five source-class catalog identities and latest reviewed visible counts."""
from datetime import datetime, timezone
import os
import re
import unicodedata
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, JSON, select
from sqlalchemy.orm import Mapped, Session, mapped_column, object_session
from src.storage import Base
from src.inference.config import load_config
from src.evidence import EvidenceError

SHOP_ID = 'local_demo_shop'
DEMO_COUNTS = (5, 3, 2, 4, 6)


def normalize(value):
    value = unicodedata.normalize('NFKC', value).casefold()
    return ' '.join(re.sub(r'[^\w\s]', ' ', value).split())


class CatalogProduct(Base):
    __tablename__ = 'products'
    __table_args__ = (CheckConstraint('class_id >= 0 AND class_id < 5'),)
    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    class_id: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String)
    normalized_name: Mapped[str] = mapped_column(String, unique=True)
    brand: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String)
    variant: Mapped[str | None] = mapped_column(String)
    package_size: Mapped[str | None] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String, default='visible_package')
    image_reference: Mapped[str | None] = mapped_column(String)
    metadata_source: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class Shop(Base):
    __tablename__ = 'shops'
    shop_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ProductMetadata(Base):
    """Optional sourced declarations; no row means all additional facts are unknown."""
    __tablename__ = 'product_metadata'
    product_id: Mapped[str] = mapped_column(ForeignKey('products.product_id', ondelete='RESTRICT'), primary_key=True)
    facts: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ProductAlternative(Base):
    __tablename__ = 'product_alternatives'
    __table_args__ = (CheckConstraint('source_id <> target_id'),
        CheckConstraint("typeof(priority) = 'integer' AND priority >= 0"),
        CheckConstraint("relationship_type IN ('related_variant', 'substitute')"),)
    source_id: Mapped[str] = mapped_column(ForeignKey('products.product_id', ondelete='RESTRICT'), primary_key=True)
    target_id: Mapped[str] = mapped_column(ForeignKey('products.product_id', ondelete='RESTRICT'), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(String)
    priority: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ShopInventory(Base):
    __tablename__ = 'shop_inventory'
    __table_args__ = (
        CheckConstraint("typeof(quantity) = 'integer' AND quantity BETWEEN 0 AND 9007199254740991"),
        CheckConstraint('(is_demo = 1 AND source_scan_id IS NULL AND last_confirmed_at IS NULL) OR '
                        '(is_demo = 0 AND source_scan_id IS NOT NULL AND last_confirmed_at IS NOT NULL)'),
    )
    shop_id: Mapped[str] = mapped_column(ForeignKey('shops.shop_id', ondelete='RESTRICT'), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.product_id', ondelete='RESTRICT'), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_scan_id: Mapped[str | None] = mapped_column(ForeignKey('scans.id', ondelete='RESTRICT'))
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


def seed_catalog(connection):
    """Metadata only, inside the additive schema transaction. No invented stock."""
    config = load_config()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    brands = ('Red Bull', 'Knoppers', 'Valser', 'Valser', 'Capri-Sun')
    variants = (None, 'Riegel', 'Classic', 'Still', 'Multivitamin')
    for i, product_id in enumerate(config.product_ids):
        existing = connection.execute(select(CatalogProduct.__table__).where(CatalogProduct.product_id==product_id)).mappings().first()
        if existing:
            if existing['class_id'] != i:
                raise ValueError('Catalog class mapping differs from frozen identities')
            continue
        connection.execute(CatalogProduct.__table__.insert().values(product_id=product_id,class_id=i,
            name=config.names[i],normalized_name=normalize(config.names[i]),brand=brands[i],variant=variants[i],
            category=None,package_size=None,image_reference=None,unit='visible_package',
            metadata_source='configs/class_map.json: source identity, not verified SKU metadata',created_at=now,updated_at=now))
    if not connection.execute(select(Shop.shop_id).where(Shop.shop_id==SHOP_ID)).first():
        connection.execute(Shop.__table__.insert().values(shop_id=SHOP_ID,name='Demo Shop',is_demo=True,
                                                       created_at=now,updated_at=now))


def apply_review(session, scan):
    """Use only explicitly reviewed items; same transaction as scan/evidence rows."""
    for item in scan.items:
        if not item.reviewed:
            continue
        product = session.get(CatalogProduct,item.product_id)
        if product is None or product.class_id != item.class_id:
            raise EvidenceError('Recognized class cannot be resolved to its catalog product')
        inventory = session.get(ShopInventory,(SHOP_ID,product.product_id))
        if inventory is None:
            inventory = ShopInventory(shop_id=SHOP_ID,product_id=product.product_id)
            session.add(inventory)
        inventory.quantity = item.confirmed_count
        inventory.source_scan_id = scan.id
        inventory.last_confirmed_at = scan.created_at
        inventory.updated_at = scan.created_at
        inventory.is_demo = False


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value is not None else None


def product_json(product):
    from src.alternatives import metadata
    _, information = metadata(object_session(product), product.product_id)
    return {key:getattr(product,key) for key in ('product_id','class_id','name','normalized_name','brand',
        'category','variant','package_size','unit','image_reference','metadata_source')} | {
        'created_at':iso(product.created_at),'updated_at':iso(product.updated_at),
        'identity_level':'source_product_class','catalog_sku_verified':False, 'metadata':information}


def freshness_seconds():
    value = int(os.environ.get('INVENTORY_FRESHNESS_SECONDS','3600'))
    if value < 1:
        raise ValueError('INVENTORY_FRESHNESS_SECONDS must be a positive integer')
    return value


class CatalogStore:
    def __init__(self, store, fresh_seconds=None):
        self.store = store
        self.fresh_seconds = freshness_seconds() if fresh_seconds is None else fresh_seconds
        if type(self.fresh_seconds) is not int or self.fresh_seconds < 1:
            raise ValueError('Freshness must be a positive number of seconds')

    def search(self, query=''):
        term = normalize(query)
        compact = term.replace(' ','')
        with Session(self.store.engine) as session:
            products = session.scalars(select(CatalogProduct)).all()
            matches = [p for p in products if not term or any(term in value or compact in value.replace(' ','')
                for value in (p.normalized_name, normalize(p.brand or '')))]
            matches.sort(key=lambda p:(0 if p.normalized_name==term or p.normalized_name.replace(' ','')==compact else 1,
                                       p.normalized_name,p.product_id))
            return [product_json(p) for p in matches]

    def product(self, product_id):
        with Session(self.store.engine) as session:
            product = session.get(CatalogProduct,product_id)
            return product_json(product) if product else None

    def inventory(self, product_id=None, shop_id=None, availability=None, now=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('Inventory clock must be timezone-aware')
        with Session(self.store.engine) as session:
            query = select(ShopInventory,CatalogProduct,Shop).join(CatalogProduct).join(Shop)
            if product_id is not None:
                query = query.where(ShopInventory.product_id==product_id)
            if shop_id is not None:
                query = query.where(ShopInventory.shop_id==shop_id)
            query = query.order_by(CatalogProduct.normalized_name, Shop.shop_id)
            result = []
            for row, product, shop in session.execute(query):
                age = (now-row.last_confirmed_at.replace(tzinfo=timezone.utc)).total_seconds() if row.last_confirmed_at else None
                fresh = age is not None and 0 <= age <= self.fresh_seconds
                status = 'DEMO' if row.is_demo else ('FRESH' if fresh else 'STALE')
                available = not row.is_demo and fresh and row.quantity > 0
                match = {'available':available,'unavailable':not row.is_demo and fresh and row.quantity==0,
                         'stale':status=='STALE','demo':row.is_demo}
                if availability and not match[availability]:
                    continue
                result.append({'shop_id':row.shop_id,'shop_name':shop.name,'shop_is_demo':shop.is_demo,
                    'product':product_json(product),'product_id':row.product_id,'quantity':row.quantity,
                    'quantity_meaning':'latest_reviewed_visible_packages','last_confirmed_at':iso(row.last_confirmed_at),
                    'source_scan_id':row.source_scan_id,'updated_at':iso(row.updated_at),'is_demo':row.is_demo,
                    'freshness':status,'freshness_seconds':self.fresh_seconds,'age_seconds':age,
                    'recently_confirmed_positive':available,'guaranteed_available':False})
            return result

    def seed_demo(self):
        from src.data_lock import data_lock
        with data_lock(self.store.path,self.store.evidence.root), Session(self.store.engine) as session, session.begin():
            for product in session.scalars(select(CatalogProduct)):
                if session.get(ShopInventory,(SHOP_ID,product.product_id)) is None:
                    session.add(ShopInventory(shop_id=SHOP_ID,product_id=product.product_id,
                        quantity=DEMO_COUNTS[product.class_id],is_demo=True,last_confirmed_at=None,source_scan_id=None,
                        updated_at=datetime(2026,1,1)))
