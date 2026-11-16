"""Private read-only connector agent. Never expose this service to the Internet."""
import asyncio
import hmac
import os
from contextlib import asynccontextmanager
import signal

from aiohttp import web
from pydantic import BaseModel,ConfigDict,Field,ValidationError

REQUEST_TIMEOUT_SECONDS=80


class AgentQuery(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    source: str=Field(min_length=1,max_length=40)
    query: str=Field(min_length=1,max_length=200)
    region: str=Field(default='',max_length=100)


def create_app(token: str, *, adapters=None):
    if not token or len(token)<16:
        raise ValueError('Private source agent requires a strong access token')
    # Construct local adapters directly: a configured remote agent must never
    # recursively forward back to itself.
    if adapters is None:
        from .sources import ConnectorSource
        from compare_connector.server import SOURCES
        names=('wildberries','yandex_market','ozon','megamarket','avito','dns','citilink','lamoda','aliexpress','taobao')
        adapters={name:ConnectorSource(name) for name in names if name in SOURCES}
    gate=asyncio.Semaphore(2)
    queued=0
    calls=[]

    @web.middleware
    async def authenticate(request,handler):
        supplied=request.headers.get('Authorization','')
        if not hmac.compare_digest(supplied.encode(),('Bearer '+token).encode()):
            raise web.HTTPUnauthorized()
        return await handler(request)

    app=web.Application(client_max_size=8192,middlewares=[authenticate])

    async def health(request):
        return web.json_response({'ok':True,'sources':list(adapters),'max_concurrency':2})

    async def search(request):
        nonlocal queued
        try:
            query=AgentQuery.model_validate(await request.json())
        except (ValueError,ValidationError):
            raise web.HTTPBadRequest(text='Invalid source request')
        if query.source not in adapters:
            raise web.HTTPBadRequest(text='Unknown source')
        now=asyncio.get_running_loop().time()
        calls[:]=[value for value in calls if now-value<60]
        if queued>=5 or len(calls)>=20:
            raise web.HTTPTooManyRequests(headers={'Retry-After':'60'})
        calls.append(now);queued+=1
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                async with gate:
                    batch=await adapters[query.source].search(query.query,query.region)
            return web.json_response({'status':batch.status.model_dump(mode='json'),
                'candidates':[[offer.model_dump(mode='json'),variant.model_dump(mode='json')] for offer,variant in batch.candidates]})
        except TimeoutError:
            raise web.HTTPGatewayTimeout(text='Source timed out')
        finally:
            queued-=1

    app.router.add_get('/health',health)
    app.router.add_post('/search',search)
    return app


@asynccontextmanager
async def serving_agent(app,*,host='127.0.0.1',port=8092):
    runner=web.AppRunner(app,access_log=None,handler_cancellation=True)
    await runner.setup()
    try:
        site=web.TCPSite(runner,host,port)
        await site.start()
        yield site
    finally:
        await runner.cleanup()


async def main():
    stop=asyncio.Event()
    loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):
        try: loop.add_signal_handler(sig,stop.set)
        except NotImplementedError: pass  # Windows console cancellation is handled by asyncio.run.
    app=create_app(os.environ.get('MARKETFUSION_SOURCE_AGENT_TOKEN',''))
    async with serving_agent(app,host=os.environ.get('MARKETFUSION_SOURCE_AGENT_BIND','127.0.0.1')):
        await stop.wait()


if __name__=='__main__':
    asyncio.run(main())
