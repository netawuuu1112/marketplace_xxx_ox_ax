"""Read-only, bounded browser probe. Never prints cookies or request headers."""
import asyncio
import json
from mcp_core.transport.chrome_cdp import _raw_cdp_page
from wb_connector.dom_transport import SEARCH_OBSERVER_JS

OBSERVE = r"""
window.__mfProbe = [];
const originalFetch = window.fetch;
window.fetch = async function(...args) {
 const r = await originalFetch.apply(this,args);
 const u = new URL(r.url);
 if ((u.hostname.endsWith('.wb.ru') || u.hostname.endsWith('.wildberries.ru')) && u.pathname.includes('search')) {
  const entry={host:u.hostname,path:u.pathname,status:r.status,query:u.searchParams.get("query"),page:u.searchParams.get("page"),keys:[...u.searchParams.keys()]};
  window.__mfProbe.push(entry);
  r.clone().json().then(d => {const ps=d.products || d.data?.products; if(Array.isArray(ps)){entry.count=ps.length;entry.sample=ps.slice(0,1).map(p=>({id:p.id,name:p.name,price:p.sizes?.[0]?.price}));}}).catch(()=>{});
 }
 return r;
};
"""
async def main():
 async with _raw_cdp_page('about:blank',0) as page:
  await page._send('Page.addScriptToEvaluateOnNewDocument',{'source':OBSERVE + SEARCH_OBSERVER_JS})
  status=await page.goto_and_status('https://www.wildberries.ru/catalog/0/search.aspx?search=ssd',navigation_timeout_ms=25000)
  await asyncio.sleep(15)
  data=await page.evaluate('JSON.stringify({url:location.href,observed:window.__mfSearchProducts?.length,title:document.title,responses:window.__mfProbe,tiles:document.querySelectorAll(".product-card").length})')
  print(json.dumps({'status':status,'page':json.loads(data)},ensure_ascii=True)[:6000],flush=True)
if __name__=='__main__':
 asyncio.run(asyncio.wait_for(main(),timeout=60))


