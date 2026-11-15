import asyncio
from types import SimpleNamespace
from models import Product
from matcher.matcher import arbiter_confirm,find_counterpart


def test_legacy_comparison_cannot_override_variant_conflict():
    target=Product(marketplace='wb',ext_id='1',title='Kingston NV3 1TB',price=5000,url='')
    bad=Product(marketplace='yandex',ext_id='2',title='Kingston NV3 500GB',price=3000,url='')
    good=Product(marketplace='yandex',ext_id='3',title='SSD Kingston NV3 1 ТБ',price=5500,url='')
    assert find_counterpart(target,[bad,good])==good
    assert not asyncio.run(arbiter_confirm(SimpleNamespace(real=False),target,bad)).same
    assert asyncio.run(arbiter_confirm(SimpleNamespace(real=False),target,good)).same
