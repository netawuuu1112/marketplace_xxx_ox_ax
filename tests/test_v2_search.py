import asyncio
from types import SimpleNamespace
import pytest
from catalog_v2.models import MarketplaceOffer, SearchRequest, SourceStatus
from catalog_v2.identity import identify
from catalog_v2.sources import SourceBatch
from catalog_v2.service import SearchService


class Adapter:
    def __init__(self,name,price=500000,blocked=False): self.name,self.price,self.blocked=name,price,blocked
    async def search(self,query,region):
        await asyncio.sleep(.001)
        if self.blocked: return SourceBatch(SourceStatus(source=self.name,status='blocked'),[])
        return SourceBatch(SourceStatus(source=self.name,status='ok',offers_count=2),[
            (MarketplaceOffer(id=self.name+'a',source=self.name,native_id='a',title='Kingston NV3 1TB',price=self.price),identify('Kingston NV3 1TB')),
            (MarketplaceOffer(id=self.name+'b',source=self.name,native_id='b',title='Kingston NV3 500GB',price=300000),identify('Kingston NV3 500GB'))])


def test_search_groups_only_exact_variants_and_survives_blocked_source():
    async def scenario():
        service=SearchService(SimpleNamespace(),adapters={n:Adapter(n,p,b) for n,p,b in [('a',500000,False),('b',550000,False),('c',480000,False),('ozon',0,True)]})
        result=await service.search(1,SearchRequest(query='кингстон нв3 терабайт'))
        assert len(result.groups)==1
        assert result.groups[0].minimum_price==480000
        assert result.groups[0].sources_count==3
        assert all('500' not in o.title for o in result.groups[0].offers)
        assert any('500' in g.product.title for g in result.related)
        assert not result.complete
        assert any(s.status=='blocked' for s in result.sources)
        with pytest.raises(LookupError): await service.snapshot(2,result.search_id)
        with pytest.raises(LookupError): await service.get_product(2,result.groups[0].product.id)
        await service.close()
    asyncio.run(scenario())


def test_owner_can_cancel_job_and_unknown_source_is_rejected():
    async def scenario():
        service=SearchService(SimpleNamespace(),adapters={'a':Adapter('a')})
        job=await service.start(1,SearchRequest(query='ssd'))
        with pytest.raises(LookupError): await service.cancel(2,job.search_id)
        await service.cancel(1,job.search_id)
        assert (await service.snapshot(1,job.search_id)).status=='cancelled'
        with pytest.raises(ValueError): await service.start(1,SearchRequest(query='ssd',sources=['evil']))
        await service.close()
    asyncio.run(scenario())
