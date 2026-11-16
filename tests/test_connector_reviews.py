import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import config
from core.orchestrator import Orchestrator
from models import Product


def orchestrator():
    instance = object.__new__(Orchestrator)
    instance._db = SimpleNamespace(cache_get_reviews=AsyncMock(return_value=None), cache_set_reviews=AsyncMock())
    instance._adapters = []
    return instance


def test_yandex_reviews_use_current_connector_without_legacy_adapter(monkeypatch):
    from yandex_connector import server
    from yandex_connector.models_output import YandexCardResponse, YandexReview
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    monkeypatch.setattr(server, 'yandex_card', AsyncMock(return_value=YandexCardResponse(
        product_id='123', reviews=[YandexReview(author='Buyer', rating=4, comment='Real text', pros='Fast')]
    )))
    instance = orchestrator()
    product = Product(marketplace='yandex', ext_id='123', title='SSD', price=1, url='')
    reviews = asyncio.run(instance._load_reviews(product))
    assert len(reviews) == 1
    assert reviews[0].text == 'Real text'
    assert reviews[0].pros == 'Fast'
    assert reviews[0].bought_here is False


def test_wb_reviews_resolve_variant_root_and_label_shared_pool(monkeypatch):
    from wb_connector import server
    from wb_connector.models_output import WbRootInfoResponse, WbReviewsResponse, WbReviewItem
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    root = AsyncMock(return_value=WbRootInfoResponse(imt_id=99))
    fetch = AsyncMock(return_value=WbReviewsResponse(imt_id=99, feedbacks=[
        WbReviewItem(rating=5, text='Good', user='Buyer'), WbReviewItem(rating=None, text='No rating')
    ]))
    monkeypatch.setattr(server, 'wb_root_info', root)
    monkeypatch.setattr(server, 'wb_reviews', fetch)
    product = Product(marketplace='wb', ext_id='321', title='SSD', price=1, url='')
    reviews = asyncio.run(orchestrator()._load_reviews(product))
    assert len(reviews) == 1
    root.assert_awaited_once_with(321)
    assert fetch.await_args.args == (99,)
    assert reviews[0].scope == 'variant_group'


def test_failed_reviews_are_not_cached_as_no_reviews(monkeypatch):
    from yandex_connector import server
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    monkeypatch.setattr(server, 'yandex_card', AsyncMock(side_effect=RuntimeError('blocked')))
    instance = orchestrator()
    product = Product(marketplace='yandex', ext_id='123', title='', price=1, url='')
    assert asyncio.run(instance._load_reviews(product)) == []
    instance._db.cache_set_reviews.assert_not_awaited()


def test_yandex_card_url_binds_requested_sku_when_model_id_differs(monkeypatch):
    from yandex_connector import server
    from yandex_connector.models_output import YandexCardResponse, YandexReview
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    monkeypatch.setattr(server, 'yandex_card', AsyncMock(return_value=YandexCardResponse(
        product_id='999', sku_id='888', url='https://market.yandex.ru/card/x/123',
        reviews=[YandexReview(rating=5, comment='Good')]
    )))
    product = Product(marketplace='yandex', ext_id='123', title='', price=1, url='')
    reviews = asyncio.run(orchestrator()._load_reviews(product))
    assert len(reviews) == 1 and reviews[0].scope == 'variant_group'


def test_shared_variant_reviews_cannot_confirm_selected_variant_requirements():
    from models import Review, ReviewAnalysis, RequirementVerdict
    from review.intelligence import analyze_reviews
    review = Review(product_market='wb', product_id='123', review_id='one', rating=5,
                    text='1TB works', scope='variant_group')
    llm = SimpleNamespace(structured=AsyncMock(return_value=ReviewAnalysis(
        product_market='wb', product_id='123', summary='Good',
        verdicts=[RequirementVerdict(requirement='1TB', verdict='confirmed', quote='1TB works', mentions=1)]
    )))
    product = Product(marketplace='wb', ext_id='123', title='SSD 1TB', price=1, url='')
    result = asyncio.run(analyze_reviews(llm, product, [review], ['1TB']))
    assert result.verdicts[0].verdict == 'no_data'
    assert result.verdicts[0].quote == ''
    assert 'другие варианты' in llm.structured.await_args.kwargs['prompt']


def test_unusable_review_pool_is_not_reported_as_genuinely_empty(monkeypatch):
    import pytest
    from review.connectors import ReviewsUnavailable
    from yandex_connector import server
    from yandex_connector.models_output import YandexCardResponse, YandexReview
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    monkeypatch.setattr(server, 'yandex_card', AsyncMock(return_value=YandexCardResponse(
        product_id='123', reviews=[YandexReview(rating=None, comment='Unrated')]
    )))
    product = Product(marketplace='yandex', ext_id='123', title='', price=1, url='')
    with pytest.raises(ReviewsUnavailable):
        asyncio.run(orchestrator()._load_reviews(product, strict=True))


def test_known_review_count_without_accessible_text_is_unavailable(monkeypatch):
    import pytest
    from review.connectors import ReviewsUnavailable
    from yandex_connector import server
    from yandex_connector.models_output import YandexCardResponse
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    monkeypatch.setattr(server, 'yandex_card', AsyncMock(return_value=YandexCardResponse(
        product_id='123', review_count=27, reviews=[]
    )))
    product = Product(marketplace='yandex', ext_id='123', title='', price=1, url='')
    with pytest.raises(ReviewsUnavailable):
        asyncio.run(orchestrator()._load_reviews(product, strict=True))


def test_legacy_ozon_ambiguous_empty_is_not_cached_as_verified_empty(monkeypatch):
    import pytest
    from review.connectors import ReviewsUnavailable
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    instance = orchestrator()
    instance._adapters = [SimpleNamespace(name='ozon', get_reviews=AsyncMock(return_value=[]))]
    product = Product(marketplace='ozon', ext_id='123', title='', price=1, url='')
    with pytest.raises(ReviewsUnavailable):
        asyncio.run(instance._load_reviews(product, strict=True))
    instance._db.cache_set_reviews.assert_not_awaited()


def test_review_prompt_includes_separate_pros_and_cons():
    from models import Review
    from review.intelligence import build_review_prompt
    product = Product(marketplace='yandex', ext_id='123', title='SSD', price=1, url='')
    review = Review(product_market='yandex', product_id='123', review_id='one', rating=4,
                    text='', pros='Fast read', cons='Hot controller')
    prompt = build_review_prompt(product, [review], [])
    assert 'Fast read' in prompt and 'Hot controller' in prompt


def test_reviews_api_distinguishes_unavailable_source_from_empty_reviews(monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer
    from test_v2_api import headers
    from web import ApiContext, create_app
    from yandex_connector import server
    monkeypatch.setattr(config, 'BOT_TOKEN', 'fixture-token')
    monkeypatch.setattr(config, 'API_TOKEN', '')
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    monkeypatch.setattr(server, 'yandex_card', AsyncMock(side_effect=RuntimeError('blocked')))
    instance = orchestrator()
    instance._db.get_session = AsyncMock(return_value=SimpleNamespace(last_results=[]))
    async def scenario():
        async with TestClient(TestServer(create_app(ApiContext(instance._db, None, instance, {})))) as client:
            response = await client.get('/api/reviews?marketplace=yandex&ext_id=123', headers=headers(10))
            assert response.status == 503
    asyncio.run(scenario())
