import asyncio,json
from wb_connector.server import wb_search
async def main():
 r=await wb_search(query='ssd',page=1)
 items=getattr(r,'items',[])
 print(json.dumps({'count':len(items),'ordinary':sum(i.price_rub is not None and i.price_kind=='regular' for i in items),'first':[{'id':i.nm_id,'price':i.price_rub,'kind':i.price_kind} for i in items[:5]]}))
asyncio.run(asyncio.wait_for(main(),timeout=85))
