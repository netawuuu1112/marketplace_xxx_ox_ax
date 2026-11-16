from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def minor_units(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError('Invalid monetary amount')
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Invalid monetary amount') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError('Invalid monetary amount')
    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


MatchStatus = Literal['exact', 'probable', 'similar', 'rejected']


class CatalogProduct(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    brand: str = ''
    model: str = ''
    category: str = ''
    image_url: str = ''


class ProductVariant(BaseModel):
    id: str = ''
    product_id: str = ''
    brand: str = ''
    model: str = ''
    category: str = ''
    title: str = ''
    mpn: str = ''
    gtin: str = ''
    attributes: dict[str, str] = Field(default_factory=dict)
    condition: str = 'unknown'


class DeliveryEstimate(BaseModel):
    price: int | None = Field(default=None, ge=0)
    date_min: str | None = None
    date_max: str | None = None
    region: str = ''
    checked_at: str | None = None
    confidence: Literal['unknown', 'reported', 'confirmed'] = 'unknown'
    conditions: str = ''


class ConditionalPrice(BaseModel):
    amount: int = Field(ge=0)
    condition: str


class MarketplaceOffer(BaseModel):
    id: str = ''
    product_id: str = ''
    variant_id: str = ''
    source: str
    native_id: str
    title: str
    seller: str = ''
    url: str = ''
    image_url: str = ''
    price: int | None = Field(default=None, gt=0)
    conditional_prices: list[ConditionalPrice] = Field(default_factory=list)
    currency: str = 'RUB'
    rating: float | None = None
    in_stock: bool | None = None
    condition: str = 'unknown'
    checked_at: str = Field(default_factory=now)
    region: str = ''
    delivery: DeliveryEstimate = Field(default_factory=DeliveryEstimate)
    match_status: MatchStatus = 'exact'

    def total(self, region: str) -> int | None:
        d = self.delivery
        if self.price is None or self.currency != 'RUB' or d.price is None or not region or d.region != region or d.confidence != 'confirmed' or (self.region and self.region != region):
            return None
        return self.price + d.price


class SourceStatus(BaseModel):
    source: str
    status: Literal['pending', 'ok', 'partial', 'blocked', 'timeout', 'auth_required', 'rate_limited', 'parser_drift', 'unavailable'] = 'pending'
    detail: str = ''
    offers_count: int = 0
    elapsed_ms: int = 0
    checked_at: str = Field(default_factory=now)
    region: str = ''
    supports_delivery: bool = False
    supports_monitoring: bool = False


class ProductGroup(BaseModel):
    product: CatalogProduct
    variant: ProductVariant
    offers: list[MarketplaceOffer] = Field(default_factory=list)
    minimum_price: int | None = None
    minimum_total: int | None = None
    best_price_offer_id: str | None = None
    best_total_offer_id: str | None = None
    sources_count: int = 0
    match_status: MatchStatus = 'exact'
    reasons: list[str] = Field(default_factory=list)


def compare_group(variant: ProductVariant, offers: list[MarketplaceOffer], *, region: str = '', product: CatalogProduct | None = None) -> ProductGroup:
    eligible = [o for o in offers if o.match_status == 'exact' and o.price is not None and o.currency == 'RUB' and o.in_stock is not False and (not region or not o.region or o.region == region)]
    cheapest = min(eligible, key=lambda o: o.price, default=None)
    delivered = [o for o in eligible if o.total(region) is not None]
    best_total = min(delivered, key=lambda o: o.total(region), default=None)
    return ProductGroup(product=product or CatalogProduct(id=variant.product_id, title=variant.title, brand=variant.brand, model=variant.model, category=variant.category),
        variant=variant, offers=offers, minimum_price=cheapest.price if cheapest else None,
        minimum_total=best_total.total(region) if best_total else None,
        best_price_offer_id=cheapest.id if cheapest else None, best_total_offer_id=best_total.id if best_total else None,
        sources_count=len({o.source for o in eligible}))


class SearchFilters(BaseModel):
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    in_stock: bool | None = None
    exact_only: bool = False
    condition: str | None = None
    delivery_days: int | None = Field(default=None, ge=0, le=365)


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    region: str = Field(default='', max_length=100)
    sources: list[str] | None = Field(default=None, max_length=15)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    sort: Literal['relevance', 'price', 'total', 'delivery', 'rating'] = 'relevance'


class SearchSnapshot(BaseModel):
    search_id: str = Field(default_factory=lambda: uuid4().hex)
    query: str
    normalized_query: str = ''
    status: Literal['queued', 'running', 'complete', 'cancelled', 'failed'] = 'queued'
    groups: list[ProductGroup] = Field(default_factory=list)
    related: list[ProductGroup] = Field(default_factory=list)
    sources: list[SourceStatus] = Field(default_factory=list)
    complete: bool = False
    error: str | None = None
    created_at: str = Field(default_factory=now)


class PriceObservation(BaseModel):
    product_id: str
    variant_id: str
    offer_id: str
    source: str
    price: int = Field(gt=0)
    currency: str = 'RUB'
    region: str = ''
    captured_at: str = Field(default_factory=now)
