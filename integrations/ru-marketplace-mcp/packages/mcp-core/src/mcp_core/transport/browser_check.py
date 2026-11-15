"""Let a site's normal browser check finish within an owned, bounded tab."""
import asyncio
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from .chrome_cdp import NavBlocked, _check_final_host, _raw_cdp_page

HOSTS = frozenset({'www.dns-shop.ru', 'dns-shop.ru'})
STATUS_JS = "performance.getEntriesByType('navigation').slice(-1)[0]?.responseStatus || 0"


@asynccontextmanager
async def open_browser_check_page(url: str, wait_ms: int, *, max_wait_s: float = 25):
    if urlsplit(url).scheme != 'https' or urlsplit(url).hostname not in HOSTS:
        raise ValueError('browser check is limited to DNS HTTPS pages')
    async with _raw_cdp_page('about:blank', 0) as page:
        status = await page.goto_and_status(url, navigation_timeout_ms=20000)
        _check_final_host(page.url, HOSTS)
        if status in (401, 429):
            deadline = time.monotonic() + max_wait_s
            while True:
                current = await asyncio.wait_for(page.evaluate(STATUS_JS), timeout=3)
                _check_final_host(page.url, HOSTS)
                if current == 200:
                    status = 200
                    break
                if time.monotonic() >= deadline:
                    raise NavBlocked(status, page.url)
                await asyncio.sleep(min(1, max(0, deadline - time.monotonic())))
        if status in (401, 403, 429) or status is not None and status >= 500:
            raise NavBlocked(status, page.url)
        if wait_ms:
            await asyncio.sleep(wait_ms / 1000)
        yield page
