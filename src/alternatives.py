"""Explicit catalog relationships and conservative, request-only preference matching."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.catalog import ProductAlternative, ProductMetadata, normalize, iso
from src.data_lock import data_lock

Term = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Terms = Annotated[list[Term], Field(max_length=20)]


class Facts(BaseModel):
    """Free-from declarations must be explicit, never inferred from a missing tag."""
    model_config = ConfigDict(extra='forbid', strict=True)
    dietary_tags: list[Literal['vegan', 'vegetarian']] | None = None
    allergen_tags: Terms | None = None
    ingredients: Terms | None = None
    free_from_allergens: Terms | None = None
    free_from_ingredients: Terms | None = None
    subcategory: Term | None = None


class Preferences(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    diet: Literal['vegan', 'vegetarian'] | None = None
    avoid_allergens: Terms = Field(default_factory=list)
    avoid_ingredients: Terms = Field(default_factory=list)
    same_category: bool = False
    same_variant: bool = False

    @field_validator('avoid_allergens', 'avoid_ingredients')
    @classmethod
    def normalized_terms(cls, values):
        values = [normalize(value) for value in values]
        if any(not value for value in values):
            raise ValueError('Use named ingredients or allergens, not punctuation')
        return sorted(set(values))


def metadata(session, product_id):
    row = session.get(ProductMetadata, product_id)
    facts, source, updated_at = Facts(), None, None
    if row and row.source.strip():
        try:
            facts = Facts.model_validate(row.facts)
            source, updated_at = row.source, iso(row.updated_at)
        except ValidationError:
            pass  # Malformed imported metadata cannot establish a preference match.
    return facts, {'facts': facts.model_dump(), 'source': source, 'updated_at': updated_at}


def compatibility(source, target, facts, prefs):
    checks = []
    if prefs.diet:
        state = 'unknown' if facts.dietary_tags is None else ('match' if prefs.diet in facts.dietary_tags else 'unknown')
        checks.append({'preference': prefs.diet, 'status': state})
    for field, present, absent in (
        ('avoid_allergens', facts.allergen_tags, facts.free_from_allergens),
        ('avoid_ingredients', facts.ingredients, facts.free_from_ingredients),
    ):
        for term in getattr(prefs, field):
            # Presence wins even if an imported declaration is contradictory.
            state = 'conflict' if term in {normalize(x) for x in present or []} else (
                'match' if term in {normalize(x) for x in absent or []} else 'unknown')
            checks.append({'preference': field+': '+term, 'status': state})
    for preference, field in (('same_category', 'category'), ('same_variant', 'variant')):
        if getattr(prefs, preference):
            a, b = normalize(source[field] or ''), normalize(target[field] or '')
            checks.append({'preference': preference, 'status': 'unknown' if not a or not b else ('match' if a==b else 'conflict')})
    return checks


def availability(rows):
    if any(r['recently_confirmed_positive'] for r in rows):
        return 'RECENT_POSITIVE'
    if any(r['freshness']=='FRESH' for r in rows):
        return 'RECENT_ZERO'
    if any(r['freshness']=='STALE' for r in rows):
        return 'STALE'
    return 'DEMO' if rows else 'UNKNOWN'


class AlternativeStore:
    def __init__(self, catalog):
        self.catalog = catalog

    def find(self, product_id, preferences=None):
        prefs = preferences or Preferences()
        source = self.catalog.product(product_id)
        if source is None:
            return None
        now = datetime.now(timezone.utc)  # One freshness boundary across all candidates.
        candidates, excluded = [], []
        with Session(self.catalog.store.engine) as session:
            links = session.scalars(select(ProductAlternative).where(ProductAlternative.source_id==product_id)).all()
            for link in links:
                target = self.catalog.product(link.target_id)
                facts, information = metadata(session, link.target_id)
                checks = compatibility(source, target, facts, prefs)
                failed = [check for check in checks if check['status']!='match']
                if failed:
                    excluded.append({'product_id': link.target_id, 'checks': failed})
                    continue
                rows = self.catalog.inventory(link.target_id, now=now)
                candidates.append({'product': target, 'metadata': information,
                    'relationship_type': link.relationship_type, 'priority': link.priority,
                    'is_demo': link.is_demo, 'match_reason': link.reason,
                    'preference_status': 'matches_selected_metadata' if checks else 'not_assessed',
                    'checks': checks, 'inventory': rows, 'availability': availability(rows),
                    'guaranteed_available': False})
        # Only explicit edges enter this list. Fresh positive counts first; no opaque score.
        candidates.sort(key=lambda c:(c['availability']!='RECENT_POSITIVE', c['priority'], c['product']['product_id']))
        excluded.sort(key=lambda c:c['product_id'])
        return {'product_id': product_id, 'alternatives': candidates, 'excluded': excluded,
                'source_availability': availability(self.catalog.inventory(product_id, now=now)),
                'ranking': 'recent_positive_first_then_relationship_priority_then_product_id'}

    def seed_demo(self):
        store = self.catalog.store
        with data_lock(store.path, store.evidence.root), Session(store.engine) as session, session.begin():
            classic, still = 'hs_valser_classic', 'hs_valser_still'
            for source, target in ((classic, still), (still, classic)):
                if session.get(ProductAlternative, (source, target)) is None:
                    session.add(ProductAlternative(source_id=source, target_id=target, relationship_type='related_variant',
                        priority=10, is_demo=True, created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        reason='Same Valser brand, different named variant. Demo relationship; equivalence and dietary suitability are not verified.'))
