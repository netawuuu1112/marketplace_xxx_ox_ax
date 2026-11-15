"""Shared bounded search jobs with incremental results and conservative grouping."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from .identity import identify, identity_key, match_variant, normalize_query
from .models import CatalogProduct, SearchRequest, SearchSnapshot, SourceStatus, compare_group
from .repository import CatalogRepository
from .sources import default_adapters


class SearchService:
    def __init__(self,db,*,adapters=None):
        self.repository=CatalogRepository(db)
        self.adapters=default_adapters() if adapters is None else adapters
        self.gate=asyncio.Semaphore(2)
        self.jobs={}

    @asynccontextmanager
    async def _source_slot(self):
        """Two V2 source operations across API, bot and worker processes."""
        if not self.repository.persistent:
            yield
            return
        pool=self.repository.db.pool
        while True:
            conn=await pool.acquire()
            slot=None
            try:
                for candidate in range(2):
                    if await conn.fetchval('SELECT pg_try_advisory_lock(824503,$1)',candidate):
                        slot=candidate
                        break
                if slot is not None:
                    yield
                    return
            finally:
                if slot is not None:
                    await asyncio.shield(conn.execute('SELECT pg_advisory_unlock(824503,$1)',slot))
                await asyncio.shield(pool.release(conn))
            await asyncio.sleep(.25)

    def register_source(self,name,adapter):
        """Operator/plugin hook for an authorized data API or independent agent."""
        import re
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',name) or not callable(getattr(adapter,'search',None)):
            raise ValueError('Некорректный адаптер источника')
        if name in self.adapters: raise ValueError('Источник уже зарегистрирован')
        self.adapters[name]=adapter

    async def start(self,user_id,request):
        aliases={'wb':'wildberries','yandex':'yandex_market'}
        sources=[aliases.get(s,s) for s in request.sources] if request.sources else list(self.adapters)
        if not sources or set(sources)-self.adapters.keys(): raise ValueError('Неизвестный источник')
        for key,(owner,task) in list(self.jobs.items()):
            if task.done(): self.jobs.pop(key,None)
            elif owner==user_id: await self.cancel(owner,key)
        if len(self.jobs)>=5: raise RuntimeError('Очередь поиска заполнена; повторите позже')
        if not request.region: request=request.model_copy(update={'region':await self.repository.region(user_id)})
        query=normalize_query(request.query)
        snapshot=SearchSnapshot(query=request.query,normalized_query=query,sources=[SourceStatus(source=s,region=request.region) for s in dict.fromkeys(sources)])
        await self.repository.save(user_id,snapshot)
        self.jobs[snapshot.search_id]=(user_id,asyncio.create_task(self._run(user_id,snapshot,request)))
        return snapshot.model_copy(deep=True)

    async def search(self,user_id,request):
        snapshot=await self.start(user_id,request)
        await self.jobs[snapshot.search_id][1]
        return await self.snapshot(user_id,snapshot.search_id)

    async def snapshot(self,user_id,search_id):
        return await self.repository.search(user_id,search_id)

    async def get_product(self,user_id,product_id):
        return await self.repository.product(user_id,product_id)

    async def cancel(self,user_id,search_id):
        snapshot=await self.snapshot(user_id,search_id)
        job=self.jobs.get(search_id)
        if job and job[0]==user_id:
            job[1].cancel()
            await asyncio.gather(job[1],return_exceptions=True)
            self.jobs.pop(search_id,None)
        snapshot.status='cancelled'; snapshot.complete=False
        await self.repository.save(user_id,snapshot)

    async def close(self):
        for _,task in self.jobs.values(): task.cancel()
        await asyncio.gather(*(task for _,task in self.jobs.values()),return_exceptions=True)
        self.jobs.clear()

    async def _resolve_link(self,url):
        from urllib.parse import urlsplit,unquote
        parts=urlsplit(url)
        hosts={'www.wildberries.ru':'wildberries','wildberries.ru':'wildberries','www.ozon.ru':'ozon','ozon.ru':'ozon','market.yandex.ru':'yandex_market','www.avito.ru':'avito','avito.ru':'avito','www.dns-shop.ru':'dns'}
        source=hosts.get(parts.hostname)
        if not source or parts.username or parts.password or parts.port not in (None,443,80): raise ValueError('Ссылка этой площадки пока не поддерживается')
        # Slugs identify candidates only. They cannot establish product identity.
        slug=unquote(parts.path).split('/')[-2 if parts.path.endswith('/') else -1]
        slug=slug.removesuffix('.aspx').replace('-',' ')
        if source=='wildberries':
            import re
            match=re.search(r'/catalog/(\d+)/',parts.path)
            if match:
                from wb_connector.server import wb_card
                async with self.gate:
                    async with self._source_slot():
                        result=await asyncio.wait_for(wb_card(nm_ids=[int(match[1])]),timeout=45)
                if result.items and result.items[0].name: return normalize_query(result.items[0].name)
        if len(slug)<3 or slug.isdigit() or slug in ('detail','search','product'):
            raise ValueError('Не удалось распознать товар из ссылки. Укажите название или модель.')
        return normalize_query(slug)

    async def _run(self,user_id,snapshot,request):
        accumulated=[]
        tasks=[]
        try:
            snapshot.status='running'; await self.repository.save(user_id,snapshot)
            if request.query.startswith(('https://','http://')):
                snapshot.normalized_query=await self._resolve_link(request.query)
            async def run(source):
                async with self.gate:
                    try:
                        async with self._source_slot():
                            return source,await asyncio.wait_for(self.adapters[source].search(snapshot.normalized_query,request.region),timeout=85)
                    except TimeoutError:
                        from .sources import SourceBatch
                        return source,SourceBatch(SourceStatus(source=source,status='timeout',detail='Источник не ответил вовремя',region=request.region),[])
                    except Exception:
                        from .sources import SourceBatch
                        return source,SourceBatch(SourceStatus(source=source,status='unavailable',detail='Ошибка независимого источника',region=request.region),[])
            tasks=[asyncio.create_task(run(s.source)) for s in snapshot.sources]
            for done in asyncio.as_completed(tasks):
                source,batch=await done
                snapshot.sources=[batch.status if s.source==source else s for s in snapshot.sources]
                accumulated.extend(batch.candidates)
                self._group(snapshot,request,accumulated)
                await self.repository.save(user_id,snapshot)
            snapshot.status='complete'
            snapshot.complete=all(s.status=='ok' for s in snapshot.sources)
            await self.repository.save(user_id,snapshot)
        except asyncio.CancelledError:
            for task in tasks: task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            snapshot.status='cancelled'; snapshot.complete=False
            await self.repository.save(user_id,snapshot)
            raise
        except Exception as exc:
            for task in tasks: task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            snapshot.status='failed'; snapshot.error=str(exc)[:250] if isinstance(exc,ValueError) else 'Не удалось завершить поиск'; snapshot.complete=False
            await self.repository.save(user_id,snapshot)

    def _group(self,snapshot,request,candidates):
        target=identify(snapshot.normalized_query)
        buckets={}; seen=set()
        for native,variant in candidates:
            if native.id in seen: continue
            seen.add(native.id)
            offer=native.model_copy(deep=True)
            variant=variant.model_copy(deep=True)
            decision=match_variant(target,variant)
            key=identity_key(variant,f'{offer.source}:{offer.native_id}')
            variant.id=key; variant.product_id=key
            # Offer identity is relative to its own group; query relevance lives
            # on ProductGroup. Explicit selection can track a related card safely.
            offer.variant_id=key; offer.product_id=key; offer.match_status='exact'
            f=request.filters
            if f.min_price is not None and (offer.price is None or offer.price<f.min_price): continue
            if f.max_price is not None and (offer.price is None or offer.price>f.max_price): continue
            if f.min_rating is not None and (offer.rating is None or offer.rating<f.min_rating): continue
            if f.in_stock is True and offer.in_stock is not True: continue
            if f.condition and offer.condition != f.condition: continue
            if f.delivery_days is not None:
                try: days=(datetime.fromisoformat(offer.delivery.date_max).date()-datetime.now(timezone.utc).date()).days
                except (TypeError,ValueError): continue
                if offer.delivery.region!=request.region or days>f.delivery_days: continue
            if key not in buckets:
                product=CatalogProduct(id=key,title=offer.title,brand=variant.brand,model=variant.model,category=variant.category,image_url=offer.image_url)
                buckets[key]=compare_group(variant,[],product=product,region=request.region)
                buckets[key].match_status=decision.status; buckets[key].reasons=decision.reasons
            buckets[key].offers.append(offer)
        groups=[]; related=[]
        for group in buckets.values():
            calculated=compare_group(group.variant,group.offers,product=group.product,region=request.region)
            calculated.match_status=group.match_status; calculated.reasons=group.reasons
            (groups if group.match_status=='exact' else related).append(calculated)
        if request.sort=='price': groups.sort(key=lambda g:g.minimum_price if g.minimum_price is not None else float('inf'))
        elif request.sort=='total': groups.sort(key=lambda g:g.minimum_total if g.minimum_total is not None else float('inf'))
        elif request.sort=='rating': groups.sort(key=lambda g:max((o.rating or 0 for o in g.offers),default=0),reverse=True)
        elif request.sort=='delivery': groups.sort(key=lambda g:min((o.delivery.date_max for o in g.offers if o.delivery.date_max and o.delivery.region==request.region),default='9999'))
        snapshot.groups=groups[:100]
        snapshot.related=[] if request.filters.exact_only else related[:50]


def get_service(db):
    service=getattr(db,'_catalog_v2_service',None)
    if service is None:
        service=SearchService(db); db._catalog_v2_service=service
    return service
