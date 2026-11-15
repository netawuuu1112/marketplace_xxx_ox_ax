import asyncio
from functools import wraps
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from mcp_core.transport import browser_check
from mcp_core.transport.chrome_cdp import NavBlocked


def run_async(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))
    return wrapped


@run_async
async def test_browser_check_accepts_completed_navigation(monkeypatch):
    page = AsyncMock()
    page.url = 'https://www.dns-shop.ru/search/?q=ssd'
    page.goto_and_status.return_value = 401
    page.evaluate.return_value = 200
    @asynccontextmanager
    async def opened(*args, **kwargs):
        yield page
    monkeypatch.setattr(browser_check, '_raw_cdp_page', opened)
    async with browser_check.open_browser_check_page(page.url, 0, max_wait_s=0) as result:
        assert result is page


@run_async
async def test_browser_check_preserves_refusal(monkeypatch):
    page = AsyncMock()
    page.url = 'https://www.dns-shop.ru/'
    page.goto_and_status.return_value = 401
    page.evaluate.return_value = 401
    @asynccontextmanager
    async def opened(*args, **kwargs):
        yield page
    monkeypatch.setattr(browser_check, '_raw_cdp_page', opened)
    with pytest.raises(NavBlocked):
        async with browser_check.open_browser_check_page(page.url, 0, max_wait_s=0):
            pytest.fail('refusal must not reach the parser')


@run_async
async def test_browser_check_rejects_other_hosts():
    with pytest.raises(ValueError):
        async with browser_check.open_browser_check_page('https://example.com/', 0):
            pytest.fail('unexpected host')

