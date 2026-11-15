from wb_connector import server


def test_observed_search_uses_product_price_and_keeps_wallet_separate():
    payload = {"observed_products": [{"id": 123, "name": "SSD", "totalQuantity": 2,
        "sizes": [{"price": {"product": 410600, "basic": 2250000, "wallet": 398200}}]}]}
    items = server._observed_search_items(payload)
    assert items[0]["nm_id"] == 123
    assert items[0]["price_rub"] == 4106
    assert items[0]["price_kind"] == "regular"
    assert items[0]["wallet_price_rub"] is None


def test_observed_search_never_substitutes_basic_or_wallet_for_product():
    payload = {"observed_products": [{"id": 123, "name": "SSD", "sizes": [
        {"price": {"basic": 90000, "wallet": 70000}}]}]}
    assert server._observed_search_items(payload)[0]["price_rub"] is None


def test_observed_search_rejects_missing_identifiers():
    assert server._observed_search_items({"observed_products": [None, {}, {"id": "bad"}]}) == []
