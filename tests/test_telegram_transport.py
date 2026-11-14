import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import config
import telegram_transport


def test_bot_uses_only_configured_telegram_proxy(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_SOCKS_PROXY", "socks5://user:pass@proxy.example:40180")
    session = object()
    fake_session = MagicMock(return_value=session)
    fake_bot = MagicMock()
    monkeypatch.setattr(telegram_transport, "AiohttpSession", fake_session)
    monkeypatch.setattr(telegram_transport, "Bot", fake_bot)

    telegram_transport.build_bot("test-token", default=None)

    fake_session.assert_called_once_with(proxy="socks5://user:pass@proxy.example:40180")
    fake_bot.assert_called_once_with("test-token", session=session, default=None)


def test_worker_uses_same_proxy_and_direct_mode_stays_direct(monkeypatch):
    fake_connector = MagicMock()
    monkeypatch.setattr(telegram_transport, "ProxyConnector", fake_connector)
    monkeypatch.setattr(config, "TELEGRAM_SOCKS_PROXY", "socks5://user:pass@proxy.example:40180")
    telegram_transport.build_notification_connector()
    fake_connector.from_url.assert_called_once_with("socks5://user:pass@proxy.example:40180", rdns=True)

    monkeypatch.setattr(config, "TELEGRAM_SOCKS_PROXY", "")
    assert telegram_transport.build_notification_connector() is None
    fake_session = MagicMock()
    monkeypatch.setattr(telegram_transport, "AiohttpSession", fake_session)
    monkeypatch.setattr(telegram_transport, "Bot", MagicMock())
    telegram_transport.build_bot("test-token")
    fake_session.assert_called_once_with()


def test_proxy_rejects_non_socks_url_without_exposing_it(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_SOCKS_PROXY", "https://secret:password@proxy.example")
    with pytest.raises(ValueError, match="TELEGRAM_SOCKS_PROXY must use socks5") as error:
        telegram_transport.telegram_proxy_url()
    assert "secret" not in str(error.value)
