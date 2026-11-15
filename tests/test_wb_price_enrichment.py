"""WB search tiles quote Wallet prices; only a matching native card may price them."""

import asyncio
from types import SimpleNamespace

import pytest

from compare_connector import server


def _search_item():
    return SimpleNamespace(
        nm_id=2124848933, name="SSD 1 TB", brand="Brand", supplier="Seller",
        price_rub=3185.0, price_kind="wallet", wallet_price_rub=3185.0,
        review_rating=4.8, feedbacks=20, in_stock=True, total_quantity=None,
    )


@pytest.mark.parametrize(
    "card_id,kind,card_price,expected",
    [
        (2124848933, "regular", 3284.0, 3284.0),
        (999999999, "regular", 3284.0, None),
        (2124848933, "wallet", 3185.0, None),
    ],
)
def test_wb_search_uses_only_matching_regular_card(monkeypatch, card_id, kind, card_price, expected):
    calls = []

    async def wb_search(*, query, page):
        return SimpleNamespace(items=[_search_item()], meta=SimpleNamespace(healthy=True, warnings=[]))

    async def wb_card(*, nm_ids):
        calls.append(nm_ids)
        card = SimpleNamespace(nm_id=card_id, price_kind=kind, price_rub=card_price,
                               wallet_price_rub=3185.0, total_quantity=None, in_stock=True)
        return SimpleNamespace(items=[card], meta=SimpleNamespace(healthy=True, warnings=[]))

    monkeypatch.setitem(server.SOURCES, "wildberries", SimpleNamespace(wb_search=wb_search, wb_card=wb_card))
    result = asyncio.run(server._search_wildberries("ssd", 5))
    assert calls == [[2124848933]]
    assert result[0].price_rub == expected
    assert result[0].price_kind == ("regular" if expected else "wallet")
    if expected:
        assert result[0].price_native == expected
    else:
        assert result[0].price_native == 3185.0


def test_wb_card_failure_preserves_unpriced_search_result(monkeypatch):
    async def wb_search(*, query, page):
        return SimpleNamespace(items=[_search_item()], meta=SimpleNamespace(healthy=True, warnings=[]))

    async def wb_card(*, nm_ids):
        raise TimeoutError("card read exceeded budget")

    monkeypatch.setitem(server.SOURCES, "wildberries", SimpleNamespace(wb_search=wb_search, wb_card=wb_card))
    result = asyncio.run(server._search_wildberries("ssd", 5))
    assert result[0].price_rub is None
    assert any("card" in warning for warning in result.warnings)


def test_wb_enrichment_reads_at_most_one_card(monkeypatch):
    items = [_search_item(), SimpleNamespace(**{**vars(_search_item()), "nm_id": 2124848934})]
    calls = []

    async def wb_search(*, query, page):
        return SimpleNamespace(items=items, meta=SimpleNamespace(healthy=True, warnings=[]))

    async def wb_card(*, nm_ids):
        calls.append(nm_ids)
        return SimpleNamespace(items=[], meta=SimpleNamespace(healthy=False, warnings=[]))

    monkeypatch.setitem(server.SOURCES, "wildberries", SimpleNamespace(wb_search=wb_search, wb_card=wb_card))
    result = asyncio.run(server._search_wildberries("ssd", 5))
    assert calls == [[2124848933]]
    assert len(result) == 2
    assert all(offer.price_rub is None for offer in result)
