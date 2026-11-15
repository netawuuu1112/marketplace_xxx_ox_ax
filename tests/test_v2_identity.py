import pytest
from catalog_v2.identity import identify, match_variant, normalize_query
from catalog_v2.models import DeliveryEstimate, MarketplaceOffer, compare_group, minor_units


def test_russian_query_and_exact_variant():
    assert 'kingston nv3 1tb' == normalize_query('кингстон нв3 терабайт')
    target = identify('Kingston NV3 1TB')
    assert match_variant(target, identify('SSD Kingston NV3 1 ТБ')).status == 'exact'
    for title in ['Kingston NV3 500GB', 'Kingston NV2 1TB', 'Kingston NV3 2TB']:
        assert match_variant(target, identify(title)).status == 'rejected'


def test_similarity_and_missing_properties_do_not_establish_identity():
    assert match_variant(identify('Kingston NV3 1TB'), identify('Kingston NV3')).status != 'exact'
    assert match_variant(identify('Samsung Galaxy S25 256GB'), identify('Samsung Galaxy S25 Ultra 256GB')).status == 'rejected'
    assert match_variant(identify('iPhone 16 Pro 256GB натуральный титан'), identify('iPhone 16 Pro 256GB черный')).status == 'rejected'


def test_price_and_delivered_total_are_distinct_and_unknown_is_not_free():
    variant = identify('Kingston NV3 1TB')
    offers = [MarketplaceOffer(id='a', source='wb', native_id='1', title='a', price=480000,
        delivery=DeliveryEstimate(price=50000, region='Москва', confidence='confirmed')),
        MarketplaceOffer(id='b', source='ym', native_id='2', title='b', price=500000,
        delivery=DeliveryEstimate(price=0, region='Москва', confidence='confirmed')),
        MarketplaceOffer(id='c', source='ozon', native_id='3', title='c', price=490000)]
    group = compare_group(variant, offers, region='Москва')
    assert group.minimum_price == 480000 and group.best_price_offer_id == 'a'
    assert group.minimum_total == 500000 and group.best_total_offer_id == 'b'
    assert compare_group(variant, offers, region='Омск').minimum_total is None


def test_minor_units_are_decimal_and_reject_non_finite_values():
    assert minor_units('12.345') == 1235
    assert minor_units(None) is None
    for value in ['NaN', 'Infinity', '-1', True]:
        with pytest.raises(ValueError): minor_units(value)


def test_aliases_phone_capacity_and_identifiers():
    assert normalize_query('Samsng Galaxy S25 256GB')=='samsung galaxy s25 256gb'
    assert match_variant(identify('Айфон 16 про 256 натуральный титан'),identify('Apple iPhone 16 Pro 256GB natural titanium')).status=='exact'
    assert match_variant(identify('Kingston NV3 1TB',gtin='4006381333931'),identify('SSD',gtin='4006381333931')).status=='exact'
