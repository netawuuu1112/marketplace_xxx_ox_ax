"""Local staging only: actual HTTP search/favorite/watch and real worker measure.

Keeps genuine data in staging for review. No fake drops, Telegram sends or LLM
calls. All source reads use configured direct/private-agent connectors.
"""
import http.cookiejar
import json
from pathlib import Path
import subprocess
import time
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.error import URLError


def main():
    root=Path(__file__).resolve().parents[2]
    base='http://127.0.0.1:8089'
    settings=dict(line.split('=',1) for line in (root/'.env.v2-staging').read_text().splitlines() if '=' in line)
    opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path,data=None,method=None):
        headers={'Origin':base,'Content-Type':'application/json'}
        payload=json.dumps(data).encode() if data is not None else None
        with opener.open(Request(base+path,data=payload,headers=headers,method=method),timeout=15) as response:
            return json.load(response)
    deadline=time.monotonic()+30
    while True:
        try:
            assert request('/health').get('demo') is False
            break
        except URLError:
            if time.monotonic()>=deadline:
                raise
            time.sleep(.5)
    request('/api/auth/login',{'password':settings['V2_WEB_PASSWORD']})
    request('/api/v2/profile',{'region':'Москва'},'PATCH')
    snapshot=request('/api/v2/search',{'query':'Kingston NV3 1TB','region':'Москва',
        'sources':['yandex_market','wildberries','avito','dns','aliexpress']})
    deadline=time.monotonic()+240
    while snapshot['status'] in ('queued','running') and time.monotonic()<deadline:
        time.sleep(2)
        snapshot=request('/api/v2/search/'+snapshot['search_id'])
    assert snapshot['status']=='complete',snapshot.get('error')
    group=next(group for group in snapshot['groups'] if any(offer['source']=='yandex_market' and offer['price'] and offer['region']=='Москва' for offer in group['offers']))
    offer=next(offer for offer in group['offers'] if offer['source']=='yandex_market' and offer['price'] and offer['region']=='Москва')
    pid=group['product']['id']
    request('/api/v2/favorites',{'product_id':pid})
    existing=request('/api/v2/watches')['watches']
    watch=next((row for row in existing if row.get('offer_id')==offer['id'] and row.get('product_id')==pid),None)
    if not watch:
        watch=request('/api/v2/watches',{'product_id':pid,'mode':'offer','offer_id':offer['id'],
            'region':'Москва','sources':['yandex_market'],'threshold':offer['price']-1,'interval_minutes':60})
    # Ensure this can only mutate the explicitly named local staging project.
    details=json.loads(subprocess.check_output(['docker','inspect','marketfusion-v2-staging-api-1'],text=True,encoding='utf-8'))
    assert details[0]['Config']['Labels']['com.docker.compose.project']=='marketfusion-v2-staging'
    script='''import asyncio,json,os
from storage.postgres import PostgresDatabase
from catalog_v2 import watches
async def main():
 db=PostgresDatabase(os.environ['DATABASE_URL']);await db.connect()
 try:
  await db.pool.execute('UPDATE v2_watches SET next_run_at=now() WHERE id=$1',WATCH)
  row=await watches.claim_due_watch(db,watch_id=WATCH)
  assert row is not None and row['id']==WATCH
  await watches.check_watch(db,row)
  state=await db.pool.fetchrow('SELECT last_price,last_error FROM v2_watches WHERE id=$1',WATCH)
  count=await db.pool.fetchval('SELECT count(*) FROM v2_observations WHERE watch_id=$1',WATCH)
  print(json.dumps({'measured_price':state['last_price'],'error':state['last_error'],'observations':count}))
 finally: await db.close()
asyncio.run(main())
'''.replace('WATCH',str(int(watch['id'])))
    result=subprocess.run(['docker','exec','-i','marketfusion-v2-staging-api-1','python','-'],input=script,
        capture_output=True,text=True,encoding='utf-8',timeout=110)
    assert result.returncode==0,result.stderr[-1000:]
    measurement=json.loads(result.stdout)
    assert measurement['observations']>0 and measurement['measured_price'] is not None,measurement
    history=request('/api/v2/products/'+pid+'/history')
    assert history['points'] and history['region']=='Москва'
    output={'search_id':snapshot['search_id'],'product_id':pid,'watch_id':watch['id'],
        'sources':snapshot['sources'],'exact_groups':len(snapshot['groups']),'measurement':measurement,'history_points':len(history['points'])}
    (root/'backups/v2/live-staging-flow.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=True))


if __name__=='__main__':
    main()
