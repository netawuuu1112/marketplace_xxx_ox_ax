"""Read source reviews without treating a network failure as an empty review pool."""
import hashlib
import json
from urllib.parse import urlsplit

from models import Review


class ReviewsUnavailable(RuntimeError):
    pass


async def connector_reviews(product, limit):
    native_id = product.ext_id
    if not native_id.isascii() or not native_id.isdigit() or not 0 < len(native_id) <= 32 or int(native_id) <= 0:
        raise ReviewsUnavailable('Invalid native product id')
    limit = max(1, min(limit, 100))
    if product.marketplace == 'yandex':
        from yandex_connector.server import yandex_card
        response = await yandex_card(native_id, include_reviews=True)
        bound = urlsplit(response.url)
        requested_card = bound.scheme == 'https' and bound.hostname == 'market.yandex.ru' and bound.path.rstrip('/').split('/')[-1] == native_id
        if response.product_id != native_id and response.sku_id != native_id and not requested_card:
            raise ReviewsUnavailable('Product identity mismatch')
        rows = response.reviews[:limit]
        known_count = response.review_count or 0
    elif product.marketplace == 'wb':
        from wb_connector.server import wb_root_info, wb_reviews
        root = await wb_root_info(int(native_id))
        if root.imt_id <= 0:
            raise ReviewsUnavailable('Missing review root')
        response = await wb_reviews(root.imt_id, limit=limit)
        if response.imt_id != root.imt_id:
            raise ReviewsUnavailable('Review pool identity mismatch')
        rows = response.feedbacks[:limit]
        known_count = max(response.feedback_count or 0, response.pool_size)
    else:
        raise ReviewsUnavailable('Unsupported review source')
    result = []
    seen = set()
    for row in rows:
        if row.rating not in range(1, 6):
            continue
        content = dict(author=getattr(row, 'author', getattr(row, 'user', '')),
                       date=row.date or '', text=getattr(row, 'comment', getattr(row, 'text', '')),
                       pros=row.pros, cons=row.cons, rating=row.rating)
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
        if digest in seen:
            continue
        seen.add(digest)
        result.append(Review(product_market=product.marketplace, product_id=native_id,
                             review_id=digest, scope='variant_group',
                             photos=getattr(row, 'photos', []), **content))
    if (rows or known_count > 0) and not result:
        raise ReviewsUnavailable('Review pool has no usable rated reviews')
    return result
