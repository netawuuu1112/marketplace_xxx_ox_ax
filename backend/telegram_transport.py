"""Telegram-only transport through the operator's optional SOCKS5 proxy."""

from urllib.parse import urlsplit

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp_socks import ProxyConnector

import config


def telegram_proxy_url() -> str | None:
    value = config.TELEGRAM_SOCKS_PROXY.strip()
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "socks5" or not parsed.hostname or not parsed.port:
        raise ValueError("TELEGRAM_SOCKS_PROXY must use socks5://host:port")
    return value


def build_bot(token: str, *, default=None) -> Bot:
    proxy = telegram_proxy_url()
    session = AiohttpSession(proxy=proxy) if proxy else AiohttpSession()
    return Bot(token, session=session, default=default)


def build_notification_connector() -> ProxyConnector | None:
    proxy = telegram_proxy_url()
    return ProxyConnector.from_url(proxy, rdns=True) if proxy else None
