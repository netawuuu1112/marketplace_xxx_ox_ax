"""Operator-configured private data route; no arbitrary user-supplied URLs."""
import asyncio
import aiohttp

from .models import MarketplaceOffer,ProductVariant,SourceStatus
from .sources import SourceBatch


class RemoteSource:
    def __init__(self,name,url,token,*,socket_path=None):
        self.name,self.url,self.token,self.socket_path=name,url.rstrip('/'),token,socket_path

    async def search(self,query,region):
        try:
            connector=aiohttp.UnixConnector(path=self.socket_path) if self.socket_path else None
            timeout=aiohttp.ClientTimeout(total=84)
            async with aiohttp.ClientSession(connector=connector,timeout=timeout) as session:
                async with session.post(self.url+'/search',json={'source':self.name,'query':query,'region':region},
                        headers={'Authorization':'Bearer '+self.token},allow_redirects=False) as response:
                    if response.status==429:
                        return SourceBatch(SourceStatus(source=self.name,status='rate_limited',detail='Поисковый агент временно ограничил запросы'),[])
                    response.raise_for_status()
                    if response.content_length and response.content_length>2_000_000:
                        raise ValueError('Agent response too large')
                    chunks=[];size=0
                    async for chunk in response.content.iter_chunked(65536):
                        size+=len(chunk)
                        if size>2_000_000:
                            raise ValueError('Agent response too large')
                        chunks.append(chunk)
                    payload=b''.join(chunks)
            import json
            data=json.loads(payload)
            status=SourceStatus.model_validate(data['status'])
            if status.source!=self.name or len(data['candidates'])>100:
                raise ValueError('Wrong source identity')
            candidates=[]
            for raw,variant in data['candidates']:
                offer=MarketplaceOffer.model_validate(raw)
                if offer.source!=self.name:
                    raise ValueError('Wrong offer source')
                candidates.append((offer,ProductVariant.model_validate(variant)))
            return SourceBatch(status,candidates)
        except asyncio.CancelledError:
            raise
        except Exception:
            return SourceBatch(SourceStatus(source=self.name,status='unavailable',
                detail='Приватный поисковый агент недоступен или вернул некорректный ответ'),[])
