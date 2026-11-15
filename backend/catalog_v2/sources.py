"""Independent adapters around the existing installed connector; no second browser."""
import asyncio
import hashlib
import time
from dataclasses import dataclass
from .identity import identify
from .models import MarketplaceOffer, ConditionalPrice, SourceStatus, minor_units


@dataclass
class SourceBatch:
    status: SourceStatus
    candidates: list


class ConnectorSource:
    def __init__(self,name):
        self.name=name
        self.failures=0
        self.open_until=0.0
        self.cache={}

    async def search(self,query,region):
        from compare_connector.server import compare_prices
        key=(query,region)
        cached=self.cache.get(key)
        if cached and time.monotonic()-cached[0]<180:
            return cached[1]
        if self.open_until>time.monotonic():
            return SourceBatch(SourceStatus(source=self.name,status='unavailable',detail='Источник временно на паузе после ошибок',region=region),[])
        started=time.monotonic()
        try:
            result=await compare_prices(query,sources=[self.name],per_source_limit=15)
            outcome=result.source_outcomes[0]
            code=outcome.error_code or ''
            status={'challenge_required':'auth_required','rate_limited':'rate_limited','parser_drift':'parser_drift'}.get(code)
            if status is None:
                status=outcome.status if outcome.status in ('ok','partial','blocked','timeout') else 'unavailable'
            candidates=[]
            for raw in result.offers:
                identity=raw.identity
                variant=identify(raw.title,brand=identity.brand or raw.brand,model=identity.model,mpn=identity.mpn,gtin=identity.gtin,attributes=identity.variant_attributes)
                price=minor_units(raw.price_rub) if raw.price_rub is not None else None
                if raw.price_kind and raw.price_kind not in ('regular',):
                    price=None
                conditional=[]
                if raw.price_with_subscription_rub is not None:
                    conditional.append(ConditionalPrice(amount=minor_units(raw.price_with_subscription_rub),condition='Подписка'))
                if raw.price_kind and raw.price_kind!='regular' and raw.price_native is not None:
                    conditional.append(ConditionalPrice(amount=minor_units(raw.price_native),condition=raw.price_kind))
                currency=raw.currency.upper()
                if currency!='RUB': price=minor_units(raw.price_native) if raw.price_native and raw.price_kind in (None,'regular') else None
                oid=hashlib.sha256(f'{raw.source}:{raw.product_id}:{raw.variant_id}'.encode()).hexdigest()[:32]
                offer=MarketplaceOffer(id=oid,source=self.name,native_id=raw.product_id,title=raw.title,seller=raw.seller,
                    url=raw.url,price=price if price else None,conditional_prices=conditional,currency=currency,
                    rating=raw.rating,in_stock=raw.in_stock,region='',condition=variant.condition)
                candidates.append((offer,variant))
            if status=='ok' and candidates and not any(o.price for o,_ in candidates): status='partial'
            report=SourceStatus(source=self.name,status=status,detail=outcome.detail[:220]+'; регион источника не подтверждён',offers_count=len(candidates),elapsed_ms=int((time.monotonic()-started)*1000),region='')
            batch=SourceBatch(report,candidates)
            if status in ('ok','partial'):
                self.failures=0
                if len(self.cache)>=64: self.cache.pop(next(iter(self.cache)))
                self.cache[key]=(time.monotonic(),batch)
            else:
                self.failures+=1
                if self.failures>=2: self.open_until=time.monotonic()+max(60,min(float(outcome.retry_after_s or 60),600))
            return batch
        except asyncio.CancelledError:
            raise
        except Exception:
            self.failures+=1
            if self.failures>=2: self.open_until=time.monotonic()+60
            return SourceBatch(SourceStatus(source=self.name,status='unavailable',detail='Ошибка адаптера источника',region=region),[])


def default_adapters():
    from compare_connector.server import SOURCES
    supported=('wildberries','yandex_market','ozon','megamarket','avito','dns','citilink','lamoda','aliexpress','taobao')
    return {name:ConnectorSource(name) for name in supported if name in SOURCES}
