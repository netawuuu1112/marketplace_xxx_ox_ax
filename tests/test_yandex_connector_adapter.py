"""The main search should use the live connector when it returns priced offers."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from adapters.yandex import YandexMarketAdapter


def test_yandex_adapter_uses_connector_results(monkeypatch):
    from compare_connector import server

    async def compare_prices(query, per_source_limit, sources):
        assert (query, per_source_limit, sources) == ("ssd", 5, ["yandex_market"])
        return SimpleNamespace(offers=[SimpleNamespace(
            source="yandex_market", product_id="123", title="SSD 1 TB",
            price_rub=4999, url="https://market.yandex.ru/product/123",
            rating=4.7, rating_count=12, brand="Brand",
        )])

    monkeypatch.setattr(server, "compare_prices", compare_prices)

    async def run():
        adapter = YandexMarketAdapter()
        try:
            return await adapter.search("ssd", limit=5)
        finally:
            await adapter.aclose()

    products = asyncio.run(run())
    assert len(products) == 1
    assert products[0].marketplace == "yandex"
    assert products[0].ext_id == "123"
    assert products[0].price == 4999
    assert products[0].reviews_count == 12
