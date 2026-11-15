"""Actual PostgreSQL + HTTP + shared search + worker. External boundaries are fixtures."""
import asyncio
import os
from urllib.parse import urlsplit,urlunsplit
from uuid import uuid4
from types import SimpleNamespace
import asyncpg
import pytest
from aiohttp.test_utils import TestClient,TestServer
from storage.postgres import PostgresDatabase
from catalog_v2.service import SearchService
from catalog_v2 import watches
from test_v2_api import headers
from test_v2_search import Adapter
from web import ApiContext,create_app
import config


def test_http_search_watch_crossing_and_restart_persistence(monkeypatch):
    base=os.getenv('MARKETFUSION_TEST_DATABASE_URL')
    if not base: pytest.skip('isolated PostgreSQL required')
    monkeypatch.setattr(config,'BOT_TOKEN','fixture-token')
    monkeypatch.setattr(config,'API_TOKEN','')
    monkeypatch.setattr(config,'API_ALLOW_ANON',False)
    async def scenario():
        name='v2_e2e_'+uuid4().hex
        admin=await asyncpg.connect(base)
        await admin.execute(f'CREATE DATABASE "{name}"')
        url=urlunsplit(urlsplit(base)._replace(path='/'+name))
        db=PostgresDatabase(url)
        try:
            await db.connect()
            await db.pool.execute("INSERT INTO favorites(user_id,marketplace,ext_id,title,price,url,added) VALUES(10,'wb','legacy','Sony WH-1000XM5',5000,'https://www.wildberries.ru/catalog/1/detail.aspx',now()-interval '1 day')")
            class RegionalAdapter(Adapter):
                async def search(self,query,region):
                    batch=await super().search(query,region)
                    for offer,_ in batch.candidates: offer.region='Москва'
                    return batch
            adapter=RegionalAdapter('wildberries',550000)
            db._catalog_v2_service=SearchService(db,adapters={'wildberries':adapter})
            legacy=await db._catalog_v2_service.repository.list_favorites(10)
            assert len(legacy)==1 and legacy[0].offers[0].price is None
            assert await db.pool.fetchval('SELECT count(*) FROM favorites')==1
            assert not await db._catalog_v2_service.repository.list_favorites(11)
            async with TestClient(TestServer(create_app(ApiContext(db,None,None,{})))) as client:
                created=await client.post('/api/v2/search',json={'query':'Kingston NV3 1TB','region':'Москва'},headers=headers(10))
                assert created.status==202
                sid=(await created.json())['search_id']
                await db._catalog_v2_service.jobs[sid][1]
                result=await (await client.get('/api/v2/search/'+sid,headers=headers(10))).json()
                pid=result['groups'][0]['product']['id']
                response=await client.post('/api/v2/watches',json={'product_id':pid,'region':'Москва','threshold':500000},headers=headers(10))
                assert response.status==201,await response.text()
                watch=await response.json()
                row=await watches.claim_due_watch(db)
                await watches.check_watch(db,row)
                assert await db.pool.fetchval('SELECT count(*) FROM v2_alert_events')==0
                adapter.price=490000
                await db.pool.execute('UPDATE v2_watches SET next_run_at=now()')
                await watches.check_watch(db,await watches.claim_due_watch(db))
                await db.pool.execute('UPDATE v2_watches SET next_run_at=now()')
                await watches.check_watch(db,await watches.claim_due_watch(db))
                assert await db.pool.fetchval('SELECT count(*) FROM v2_alert_events')==1
                assert (await client.get('/api/v2/watches',headers=headers(11))).status==200
                assert not (await (await client.get('/api/v2/watches',headers=headers(11))).json())['watches']
                assert (await client.delete('/api/v2/watches/'+str(watch['id']),headers=headers(11))).status==404
            await db.close()
            db=PostgresDatabase(url);await db.connect()
            db._catalog_v2_service=SearchService(db,adapters={})
            assert (await db._catalog_v2_service.get_product(10,pid)).product.id==pid
            assert len(await watches.list_watches(db,10))==1
            assert await db.pool.fetchval('SELECT count(*) FROM v2_alert_events')==1
        finally:
            await db.close()
            await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
            await admin.close()
    asyncio.run(scenario())
