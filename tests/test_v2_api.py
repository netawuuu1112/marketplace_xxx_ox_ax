import asyncio
import json
from types import SimpleNamespace
from urllib.parse import urlencode
import hashlib
import hmac
import time

from aiohttp.test_utils import TestClient,TestServer
from catalog_v2.service import SearchService
from test_v2_search import Adapter
import config
from web import ApiContext,create_app


def headers(uid):
    values={'auth_date':str(int(time.time())),'user':json.dumps({'id':uid},separators=(',',':'))}
    key=hmac.new(b'WebAppData',b'fixture-token',hashlib.sha256).digest()
    check='\n'.join(f'{k}={v}' for k,v in sorted(values.items()))
    values['hash']=hmac.new(key,check.encode(),hashlib.sha256).hexdigest()
    return {'X-Telegram-Init-Data':urlencode(values)}


def test_v2_http_auth_jobs_product_and_favorite_ownership(monkeypatch):
    monkeypatch.setattr(config,'BOT_TOKEN','fixture-token')
    monkeypatch.setattr(config,'API_TOKEN','')
    monkeypatch.setattr(config,'API_ALLOW_ANON',False)
    async def scenario():
        db=SimpleNamespace()
        db._catalog_v2_service=SearchService(db,adapters={'wildberries':Adapter('wildberries')})
        async with TestClient(TestServer(create_app(ApiContext(db,None,None,{})))) as client:
            assert (await client.post('/api/v2/search',json={'query':'Kingston NV3 1TB'})).status==401
            created=await client.post('/api/v2/search',json={'query':'Kingston NV3 1TB'},headers=headers(10))
            assert created.status==202
            job=(await created.json())['search_id']
            await db._catalog_v2_service.jobs[job][1]
            assert (await client.get('/api/v2/search/'+job,headers=headers(11))).status==404
            result=await (await client.get('/api/v2/search/'+job,headers=headers(10))).json()
            pid=result['groups'][0]['product']['id']
            assert (await client.get('/api/v2/products/'+pid,headers=headers(11))).status==404
            assert (await client.post('/api/v2/favorites',json={'product_id':pid},headers=headers(10))).status==200
            assert (await (await client.get('/api/v2/favorites',headers=headers(11))).json())['products']==[]
            assert len((await (await client.get('/api/v2/favorites',headers=headers(10))).json())['products'])==1
            assert (await client.patch('/api/v2/profile',json={'region':'Москва'},headers=headers(10))).status==200
            assert (await (await client.get('/api/v2/profile',headers=headers(11))).json())['region']==''
    asyncio.run(scenario())
