import asyncio
import json
from types import SimpleNamespace

from yandex_connector import ssr
from catalog_v2.sources import ConnectorSource


def page_with_region(name='Москва', identifier=213):
    # Shape observed in the anonymous page, not a requested/default city.
    point={'regionName':name,'regionId':identifier,'id':identifier}
    return '<noframes data-apiary="patch">'+json.dumps({'collections':{'globalDeliveryPoint':{'GLOBAL_DELIVERY_POINT':point}}})+'</noframes>'


def test_yandex_extracts_only_actual_global_delivery_point():
    assert ssr.search_region(page_with_region())==('Москва','213')
    assert ssr.search_region('<script>{"regionName":"Москва","regionId":213}</script>')==('','')
    assert ssr.search_region(page_with_region()+page_with_region('Омск',66))==('','')
    assert ssr.search_region(page_with_region('',213))==('','')


def test_yandex_parsed_empty_page_still_carries_actual_region():
    parsed=ssr.parse_search(page_with_region())
    assert (parsed['region'],parsed['region_id'])==('Москва','213')


def test_adapter_keeps_source_region_instead_of_request_region(monkeypatch):
    from compare_connector import server
    from compare_connector.models_output import MarketOffer
    from compare_connector.identity import ProductIdentity,OfferEvidence
    offer=MarketOffer(source='yandex_market',product_id='1',title='Kingston NV3 1TB',
        price_rub=5000,region='Москва',region_id='213',
        identity=ProductIdentity(brand='kingston',model='nv3'),evidence=OfferEvidence(condition='used'))
    async def response(*args,**kwargs):
        return SimpleNamespace(offers=[offer],source_outcomes=[SimpleNamespace(status='ok',error_code='',detail='1 priced')])
    monkeypatch.setattr(server,'compare_prices',response)
    async def scenario():
        batch=await ConnectorSource('yandex_market').search('ssd','Омск')
        assert batch.candidates[0][0].region=='Москва'
        assert batch.candidates[0][0].condition=='used'
        assert batch.status.region=='Москва' and batch.status.supports_monitoring
        assert batch.candidates[0][0].delivery.price is None
    asyncio.run(scenario())
