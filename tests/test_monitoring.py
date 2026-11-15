"""Behavioral checks for alert deduplication and unavailable marketplace data."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import monitoring


class FakePool:
    def __init__(self):
        self.statements = []

    def acquire(self):
        return self

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def execute(self, sql, *args):
        self.statements.append((sql, args))
        return "UPDATE 1"


def test_threshold_alert_only_on_crossing(monkeypatch):
    async def compare(*_args, **_kwargs):
        offer = SimpleNamespace(price_rub=90, source="wildberries", url="https://example.test/item")
        return SimpleNamespace(cheapest_comparable=offer)

    monkeypatch.setattr(monitoring, "compare_prices", compare)
    pool = FakePool()
    db = SimpleNamespace(pool=pool)
    row = {"id": 1, "user_id": 7, "query": "ssd", "sources": None,
           "threshold_rub": 100, "last_price_rub": None}
    asyncio.run(monitoring.check_watch(db, row))
    row["last_price_rub"] = 90
    asyncio.run(monitoring.check_watch(db, row))
    assert sum("INSERT INTO price_history" in sql for sql, _ in pool.statements) == 2
    assert sum("INSERT INTO notifications" in sql for sql, _ in pool.statements) == 1


def test_no_price_does_not_create_history(monkeypatch):
    async def compare(*_args, **_kwargs):
        return SimpleNamespace(cheapest_comparable=None)

    monkeypatch.setattr(monitoring, "compare_prices", compare)
    pool = FakePool()
    db = SimpleNamespace(pool=pool)
    row = {"id": 1, "user_id": 7, "query": "ssd", "sources": None,
           "threshold_rub": 100, "last_price_rub": None}
    asyncio.run(monitoring.check_watch(db, row))
    assert not any("INSERT INTO price_history" in sql for sql, _ in pool.statements)
    assert any("last_error" in sql for sql, _ in pool.statements)
