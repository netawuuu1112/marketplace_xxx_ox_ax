"""Owner-scoped persistence. In-memory mode is explicit test/development storage."""
import json
from datetime import datetime
from .models import ProductGroup, SearchSnapshot


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


class CatalogRepository:
    def __init__(self, db):
        self.db = db
        self.searches = {}
        self.groups = {}
        self.favorites = set()
        self.regions = {}

    @property
    def persistent(self):
        return getattr(self.db, '_pool', None) is not None

    async def save(self, user_id, snapshot):
        self.searches[snapshot.search_id] = (user_id, snapshot.model_copy(deep=True))
        if len(self.searches)>200: self.searches.pop(next(iter(self.searches)))
        for group in snapshot.groups + snapshot.related:
            self.groups[(user_id, group.product.id)] = group.model_copy(deep=True)
        while len(self.groups)>1000: self.groups.pop(next(iter(self.groups)))
        if not self.persistent: return
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('INSERT INTO mf_searches(id,user_id,query,data) VALUES($1,$2,$3,$4::jsonb) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated_at=now() WHERE mf_searches.user_id=excluded.user_id',snapshot.search_id,user_id,snapshot.query,snapshot.model_dump_json())
                for group in snapshot.groups + snapshot.related:
                    await conn.execute('INSERT INTO mf_products(id,data) VALUES($1,$2::jsonb) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated_at=now()',group.product.id,group.product.model_dump_json())
                    await conn.execute('INSERT INTO mf_variants(id,product_id,data) VALUES($1,$2,$3::jsonb) ON CONFLICT(id) DO UPDATE SET data=excluded.data',group.variant.id,group.product.id,group.variant.model_dump_json())
                    await conn.execute('INSERT INTO mf_user_products(user_id,product_id) VALUES($1,$2) ON CONFLICT DO NOTHING',user_id,group.product.id)
                    for offer in group.offers:
                        checked_at=datetime.fromisoformat(offer.checked_at)
                        await conn.execute('INSERT INTO mf_offers(id,product_id,variant_id,source,native_id,data,checked_at) VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::timestamptz) ON CONFLICT(id) DO UPDATE SET product_id=excluded.product_id,variant_id=excluded.variant_id,source=excluded.source,native_id=excluded.native_id,data=excluded.data,checked_at=excluded.checked_at',offer.id,group.product.id,group.variant.id,offer.source,offer.native_id,offer.model_dump_json(),checked_at)
                        if group.match_status == 'exact' and offer.match_status == 'exact' and offer.price and offer.currency == 'RUB':
                            await conn.execute('INSERT INTO mf_price_observations(user_id,product_id,variant_id,offer_id,source,price,currency,region,captured_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9::timestamptz) ON CONFLICT DO NOTHING',user_id,group.product.id,group.variant.id,offer.id,offer.source,offer.price,offer.currency,offer.region,checked_at)

    async def search(self, user_id, search_id):
        if self.persistent:
            raw=await self.db.pool.fetchval('SELECT data FROM mf_searches WHERE id=$1 AND user_id=$2',search_id,user_id)
            if raw is None: raise LookupError('Search not found')
            result=SearchSnapshot.model_validate(decoded(raw))
            if search_id not in self.searches and result.status in ('queued','running'):
                result.status='failed'; result.error='Поиск прерван перезапуском; повторите запрос'
                await self.save(user_id,result)
            return result
        owner,result=self.searches.get(search_id,(None,None))
        if owner!=user_id or result is None: raise LookupError('Search not found')
        return result.model_copy(deep=True)

    async def product(self, user_id, product_id):
        if self.persistent:
            row=await self.db.pool.fetchrow('SELECT p.data AS product,v.data AS variant FROM mf_products p JOIN mf_user_products u ON u.product_id=p.id JOIN mf_variants v ON v.product_id=p.id WHERE p.id=$1 AND u.user_id=$2',product_id,user_id)
            if row is None: raise LookupError('Product not found')
            from .models import CatalogProduct,ProductVariant,MarketplaceOffer,compare_group
            product=CatalogProduct.model_validate(decoded(row['product']))
            variant=ProductVariant.model_validate(decoded(row['variant']))
            rows=await self.db.pool.fetch('SELECT data FROM mf_offers WHERE product_id=$1 AND variant_id=$2',product_id,variant.id)
            offers=[MarketplaceOffer.model_validate(decoded(r['data'])) for r in rows]
            from datetime import timezone
            for offer in offers:
                if (datetime.now(timezone.utc)-datetime.fromisoformat(offer.checked_at)).total_seconds()>180:
                    offer.price=None
            return compare_group(variant,offers,product=product,region=await self.region(user_id))
        group=self.groups.get((user_id,product_id))
        if group is None: raise LookupError('Product not found')
        from .models import compare_group
        return compare_group(group.variant,group.offers,product=group.product,region=await self.region(user_id))

    async def recent(self,user_id):
        if self.persistent:
            rows=await self.db.pool.fetch('SELECT data FROM mf_searches WHERE user_id=$1 ORDER BY created_at DESC LIMIT 12',user_id)
            searches=[SearchSnapshot.model_validate(decoded(r['data'])) for r in rows]
        else:
            searches=[s for owner,s in reversed(list(self.searches.values())) if owner==user_id][:12]
        queries=list(dict.fromkeys(s.query for s in searches))
        groups={g.product.id:g for s in searches for g in s.groups}
        return {'queries':queries,'products':[g.model_dump(mode='json') for g in list(groups.values())[:12]]}

    async def region(self,user_id,value=None):
        if self.persistent:
            if value is not None:
                await self.db.pool.execute('INSERT INTO mf_profiles(user_id,region) VALUES($1,$2) ON CONFLICT(user_id) DO UPDATE SET region=excluded.region',user_id,value)
            return await self.db.pool.fetchval('SELECT region FROM mf_profiles WHERE user_id=$1',user_id) or ''
        if value is not None: self.regions[user_id]=value
        return self.regions.get(user_id,'')

    async def favorite(self,user_id,product_id,remove=False):
        await self.product(user_id,product_id)
        if self.persistent:
            if remove:
                await self.db.pool.execute('DELETE FROM mf_favorites WHERE user_id=$1 AND product_id=$2',user_id,product_id)
                for row in await self.db.pool.fetch('SELECT marketplace,ext_id,title FROM favorites WHERE user_id=$1',user_id):
                    _,_,pid=self._legacy_identity(row)
                    if pid==product_id:
                        await self.db.pool.execute('DELETE FROM favorites WHERE user_id=$1 AND marketplace=$2 AND ext_id=$3',user_id,row['marketplace'],row['ext_id'])
            else: await self.db.pool.execute('INSERT INTO mf_favorites(user_id,product_id) VALUES($1,$2) ON CONFLICT DO NOTHING',user_id,product_id)
        elif remove: self.favorites.discard((user_id,product_id))
        else: self.favorites.add((user_id,product_id))

    async def list_favorites(self,user_id):
        if self.persistent:
            await self._import_legacy_favorites(user_id)
            ids=[r['product_id'] for r in await self.db.pool.fetch('SELECT product_id FROM mf_favorites WHERE user_id=$1 ORDER BY created_at DESC LIMIT 100',user_id)]
        else: ids=[pid for uid,pid in self.favorites if uid==user_id]
        return [await self.product(user_id,pid) for pid in ids]

    def _legacy_identity(self,row):
        from .identity import identify,identity_key
        source={'wb':'wildberries','yandex':'yandex_market'}.get(row['marketplace'],row['marketplace'])
        variant=identify(row['title'])
        pid=identity_key(variant,f"{source}:{row['ext_id']}")
        return source,variant,pid

    async def _import_legacy_favorites(self,user_id):
        from .models import CatalogProduct,MarketplaceOffer
        import hashlib
        rows=await self.db.pool.fetch('SELECT * FROM favorites WHERE user_id=$1 LIMIT 100',user_id)
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                for row in rows:
                    source,variant,pid=self._legacy_identity(row)
                    variant.id=pid;variant.product_id=pid
                    product=CatalogProduct(id=pid,title=row['title'],brand=variant.brand,model=variant.model,category=variant.category)
                    oid=hashlib.sha256(f"{source}:{row['ext_id']}:".encode()).hexdigest()[:32]
                    offer=MarketplaceOffer(id=oid,product_id=pid,variant_id=pid,source=source,native_id=row['ext_id'],title=row['title'],url=row['url'],price=None,checked_at=row['added'].isoformat())
                    await conn.execute('INSERT INTO mf_products(id,data) VALUES($1,$2::jsonb) ON CONFLICT DO NOTHING',pid,product.model_dump_json())
                    await conn.execute('INSERT INTO mf_variants(id,product_id,data) VALUES($1,$1,$2::jsonb) ON CONFLICT DO NOTHING',pid,variant.model_dump_json())
                    await conn.execute('INSERT INTO mf_offers(id,product_id,variant_id,source,native_id,data,checked_at) VALUES($1,$2,$2,$3,$4,$5::jsonb,$6) ON CONFLICT DO NOTHING',oid,pid,source,row['ext_id'],offer.model_dump_json(),row['added'])
                    await conn.execute('INSERT INTO mf_user_products(user_id,product_id) VALUES($1,$2) ON CONFLICT DO NOTHING',user_id,pid)
                    await conn.execute('INSERT INTO mf_favorites(user_id,product_id,created_at) VALUES($1,$2,$3) ON CONFLICT DO NOTHING',user_id,pid,row['added'])

    async def history(self,user_id,product_id,days):
        if not self.persistent:
            return {'points':[],'summary':{'min':None,'max':None,'average':None},'region':''}
        region=await self.db.pool.fetchval('SELECT region FROM mf_price_observations WHERE user_id=$1 AND product_id=$2 ORDER BY captured_at DESC LIMIT 1',user_id,product_id)
        rows=await self.db.pool.fetch("SELECT captured_at,price,source,offer_id FROM mf_price_observations WHERE user_id=$1 AND product_id=$2 AND currency='RUB' AND region=$3 AND ($4::int IS NULL OR captured_at>now()-make_interval(days=>$4::int)) ORDER BY captured_at DESC LIMIT 1000",user_id,product_id,region or '',None if days=='all' else int(days))
        points=[dict(captured_at=r['captured_at'].isoformat(),price=r['price'],source=r['source'],offer_id=r['offer_id']) for r in reversed(rows)]
        prices=[p['price'] for p in points]
        return {'points':points,'summary':{'min':min(prices) if prices else None,'max':max(prices) if prices else None,'average':sum(prices)/len(prices) if prices else None},'region':region or '', 'currency':'RUB'}
