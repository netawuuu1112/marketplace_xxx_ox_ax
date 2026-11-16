import asyncio
from types import SimpleNamespace

from aiohttp.test_utils import TestClient,TestServer
from catalog_v2.identity import identify
from catalog_v2.models import MarketplaceOffer,SourceStatus
from catalog_v2.sources import SourceBatch


def test_private_agent_auth_contract_and_source_identity():
    from catalog_v2.source_agent import create_app
    from catalog_v2.remote_source import RemoteSource
    async def scenario():
        class Adapter:
            async def search(self,query,region):
                return SourceBatch(SourceStatus(source='dns',status='ok'),[(MarketplaceOffer(id='1',source='dns',native_id='1',title='Kingston NV3 1TB',price=500000),identify('Kingston NV3 1TB'))])
        async with TestClient(TestServer(create_app('fixture-private-token',adapters={'dns':Adapter()}))) as client:
            assert (await client.post('/search',json={'source':'dns','query':'ssd'})).status==401
            headers={'Authorization':'Bearer fixture-private-token'}
            assert (await client.post('/search',json={'source':'other','query':'ssd'},headers=headers)).status==400
            assert (await client.post('/search',json={'source':'dns','query':'ssd','url':'http://127.0.0.1/'},headers=headers)).status==400
            source=RemoteSource('dns',str(client.make_url('')).rstrip('/'),'fixture-private-token')
            result=await source.search('ssd','Москва')
            assert result.status.status=='ok' and result.status.source=='dns'
            assert result.candidates[0][0].price==500000
            assert result.candidates[0][0].region==''  # Requested region is not fabricated.
            bad=RemoteSource('dns',str(client.make_url('')).rstrip('/'),'wrong-token')
            assert (await bad.search('ssd','')).status.status=='unavailable'
    asyncio.run(scenario())


def test_agent_bounds_concurrency_and_reports_offline():
    from catalog_v2.source_agent import create_app
    from catalog_v2.remote_source import RemoteSource
    async def scenario():
        active=maximum=0
        class Adapter:
            async def search(self,query,region):
                nonlocal active,maximum
                active+=1;maximum=max(maximum,active)
                try:
                    await asyncio.sleep(.03)
                    return SourceBatch(SourceStatus(source='dns',status='ok'),[])
                finally: active-=1
        async with TestClient(TestServer(create_app('fixture-private-token',adapters={'dns':Adapter()}))) as client:
            source=RemoteSource('dns',str(client.make_url('')).rstrip('/'),'fixture-private-token')
            await asyncio.gather(*(source.search('ssd','') for _ in range(5)))
            assert maximum==2
        assert (await source.search('ssd','')).status.status=='unavailable'
    asyncio.run(scenario())


def test_default_adapters_use_only_operator_selected_agent_sources(monkeypatch):
    from catalog_v2.sources import default_adapters,ConnectorSource
    from catalog_v2.remote_source import RemoteSource
    monkeypatch.setenv('MARKETFUSION_SOURCE_AGENT_URL','http://agent:8092')
    monkeypatch.setenv('MARKETFUSION_SOURCE_AGENT_TOKEN','fixture-private-token')
    monkeypatch.setenv('MARKETFUSION_SOURCE_AGENT_SOURCES','dns,avito')
    adapters=default_adapters()
    assert isinstance(adapters['dns'],RemoteSource) and isinstance(adapters['avito'],RemoteSource)
    assert isinstance(adapters['wildberries'],ConnectorSource)


def test_remote_source_reads_fragmented_response_to_completion():
    from aiohttp import web
    from catalog_v2.remote_source import RemoteSource
    async def scenario():
        async def fragmented(request):
            response=web.StreamResponse(headers={'Content-Type':'application/json'})
            await response.prepare(request)
            await response.write(b'{"status":{"source":"dns",')
            await asyncio.sleep(.01)
            await response.write(b'"status":"ok"},"candidates":[]}')
            await response.write_eof()
            return response
        app=web.Application();app.router.add_post('/search',fragmented)
        async with TestClient(TestServer(app)) as client:
            source=RemoteSource('dns',str(client.make_url('')).rstrip('/'),'fixture-private-token')
            assert (await source.search('ssd','')).status.status=='ok'
    asyncio.run(scenario())


def test_agent_cancels_its_source_when_client_disconnects():
    from catalog_v2.source_agent import create_app,serving_agent
    from catalog_v2.remote_source import RemoteSource
    async def scenario():
        entered=asyncio.Event();finished=asyncio.Event()
        class Adapter:
            async def search(self,*args):
                entered.set()
                try: await asyncio.Event().wait()
                finally: finished.set()
        async with serving_agent(create_app('fixture-private-token',adapters={'dns':Adapter()}),host='127.0.0.1',port=0) as site:
            port=site._server.sockets[0].getsockname()[1]
            remote=RemoteSource('dns',f'http://127.0.0.1:{port}','fixture-private-token')
            task=asyncio.create_task(remote.search('ssd',''))
            await asyncio.wait_for(entered.wait(),1)
            task.cancel();await asyncio.gather(task,return_exceptions=True)
            await asyncio.wait_for(finished.wait(),1)
    asyncio.run(scenario())


def test_agent_deadline_includes_time_waiting_for_a_slot(monkeypatch):
    import catalog_v2.source_agent as agent
    monkeypatch.setattr(agent,'REQUEST_TIMEOUT_SECONDS',.04)
    async def scenario():
        active=started=0
        class Adapter:
            async def search(self,*args):
                nonlocal active,started
                active+=1;started+=1
                try: await asyncio.sleep(1)
                finally: active-=1
        async with TestClient(TestServer(agent.create_app('fixture-private-token',adapters={'dns':Adapter()}))) as client:
            responses=await asyncio.gather(*(client.post('/search',json={'source':'dns','query':'ssd'},
                headers={'Authorization':'Bearer fixture-private-token'}) for _ in range(4)))
            assert all(response.status==504 for response in responses)
            assert started==2 and active==0
    asyncio.run(scenario())
