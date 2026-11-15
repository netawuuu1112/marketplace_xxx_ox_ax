import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import monitoring


def test_notification_timeout_covers_proxy_latency(monkeypatch):
    calls = []

    class Response:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

    class Session:
        def __init__(self, connector):
            calls.append({"connector": connector})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def post(self, _url, *, json, timeout):
            calls[-1]["timeout"] = timeout.total
            calls[-1]["chat_id"] = json["chat_id"]
            return Response()

    monkeypatch.setattr(monitoring.aiohttp, "ClientSession", Session)

    proxy = object()
    monkeypatch.setattr(monitoring, "build_notification_connector", lambda: proxy)
    asyncio.run(monitoring._send_telegram("test-token", 42, "test"))
    assert calls[-1] == {"connector": proxy, "timeout": 45, "chat_id": 42}

    monkeypatch.setattr(monitoring, "build_notification_connector", lambda: None)
    asyncio.run(monitoring._send_telegram("test-token", 42, "test"))
    assert calls[-1] == {"connector": None, "timeout": 10, "chat_id": 42}
