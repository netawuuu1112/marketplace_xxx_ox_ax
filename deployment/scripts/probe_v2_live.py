"""Bounded live V2 diagnostic using installed connectors, with no DB or bot.

Run only in an authorized network. It performs public marketplace reads and
prints product data/statuses, never credentials or browser cookies.
"""
import argparse
import asyncio
import json
from types import SimpleNamespace

from catalog_v2.models import SearchRequest
from catalog_v2.service import SearchService
from catalog_v2.sources import ConnectorSource,default_adapters


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', default='Kingston NV3 1TB')
    parser.add_argument('--sources', default='yandex_market,wildberries')
    parser.add_argument('--region', default='')
    parser.add_argument('--agent', action='store_true')
    args = parser.parse_args()
    names = args.sources.split(',')
    available=default_adapters() if args.agent else {name:ConnectorSource(name) for name in names}
    service = SearchService(SimpleNamespace(), adapters={name:available[name] for name in names})
    try:
        result = await asyncio.wait_for(service.search(0, SearchRequest(query=args.query, region=args.region)), 95 * len(names))
        print(json.dumps(result.model_dump(mode='json'), ensure_ascii=True), flush=True)
    finally:
        await service.close()


if __name__ == '__main__':
    asyncio.run(main())
