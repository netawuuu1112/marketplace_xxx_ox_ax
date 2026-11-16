"""Contextual Telegram actions; the Mini App owns full navigation."""
from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, \
    ReplyKeyboardRemove, WebAppInfo

from models import Product

# Единый колбэк главного меню: используется во всех клавиатурах.
HOME_DATA = "menu:main"


def product_ref(p: Product) -> str:
    """Короткая стабильная ссылка на товар для callback_data Telegram."""
    raw = f"{p.marketplace}:{p.ext_id}".encode("utf-8")
    return hashlib.blake2s(raw, digest_size=6).hexdigest()


# Import compatibility only: never recreate a persistent reply keyboard.
MENU = ReplyKeyboardRemove()


def miniapp_url(**params: str) -> str:
    import config
    parts = urlsplit(config.MINIAPP_URL)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({key: str(value) for key, value in params.items() if value})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def app_keyboard(text: str = "📱 Открыть приложение", **params: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=text, web_app=WebAppInfo(url=miniapp_url(**params)))
    ]])


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔎 Найти товар", callback_data="menu:search"),
        InlineKeyboardButton(text="📱 Открыть приложение", web_app=WebAppInfo(url=miniapp_url())),
    ]])


def catalog_product_keyboard(group, *, details: bool = False, legacy_product: Product | None = None) -> InlineKeyboardMarkup:
    product_id = group.product.id
    rows = [[
        InlineKeyboardButton(text="⚖️ Сравнить цены", callback_data=f"v2product:{product_id}"),
        InlineKeyboardButton(text="🔔 Следить за ценой", callback_data=f"v2watch:{product_id}"),
    ]]
    offer = next((o for o in group.offers if o.id == group.best_price_offer_id), None)
    if offer is None:
        offer = next((o for o in group.offers if o.match_status == "exact"), None)
    if offer and offer.url.startswith(("https://", "http://")):
        rows.append([InlineKeyboardButton(text="🛒 Открыть товар", url=offer.url)])
    if details:
        rows.append([InlineKeyboardButton(text="📱 Все предложения", web_app=WebAppInfo(url=miniapp_url(product=product_id))),
                     InlineKeyboardButton(text="История цен", web_app=WebAppInfo(url=miniapp_url(product=product_id, view="history")))])
    if legacy_product is not None:
        ref = product_ref(legacy_product)
        rows.append([InlineKeyboardButton(text="📝 Отзывы", callback_data=f"reviews:{legacy_product.marketplace}:{ref}"),
                     InlineKeyboardButton(text="⭐ Избранное", callback_data=f"fav:{legacy_product.marketplace}:{ref}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_card_keyboard(p: Product, *, favored: bool = False) -> InlineKeyboardMarkup:
    """Кнопки под карточкой товара (PRD, сценарий 1, шаг 5)."""
    fav = "⭐ Убрать" if favored else "⭐ В избранное"
    ref = product_ref(p)
    kb = [
        [InlineKeyboardButton(text=f"📝 Отзывы ({p.reviews_count})",
                              callback_data=f"reviews:{p.marketplace}:{ref}"),
         InlineKeyboardButton(text="⚖️ Сравнить цены",
                              callback_data=f"compare:{p.marketplace}:{ref}")],
        [InlineKeyboardButton(text=fav,
                              callback_data=f"fav:{p.marketplace}:{ref}"),
         InlineKeyboardButton(text="🔁 Ещё похожие",
                              callback_data=f"more:{ref}")],
        [InlineKeyboardButton(text="🛒 Открыть на Ozon", url=p.url)]
        if p.marketplace == "ozon" else
        [InlineKeyboardButton(text="🛒 Открыть на Яндекс Маркете", url=p.url)]
        if p.marketplace == "yandex" else
        [InlineKeyboardButton(text="🛒 Открыть на Wildberries", url=p.url)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def reviews_keyboard(market: str, ext_id: str, count: int,
                     page: int = 0) -> InlineKeyboardMarkup:
    """Кнопки «Отзыв 1…N» + «Ещё» + «← К товару» + «🏠»."""
    page_size = 5
    start = page * page_size
    items = [
        InlineKeyboardButton(text=str(i), callback_data=f"review_item:{market}:{ext_id}:{i}")
        for i in range(start + 1, min(start + page_size, count) + 1)
    ]
    nav = []
    if start + page_size < count:
        nav.append(InlineKeyboardButton(text="▶️ Ещё отзывы",
                                        callback_data=f"review_more:{market}:{ext_id}:{page + 1}"))
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад",
                                        callback_data=f"review_more:{market}:{ext_id}:{page - 1}"))
    kb = [items]
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="← К товару",
                                    callback_data=f"back:{market}:{ext_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def compare_keyboard(ozon_url: str = "", yandex_url: str = "",
                      wb_url: str = "") -> InlineKeyboardMarkup:
    """Кнопки-ссылки на карточки площадок, участвующих в сравнении."""
    row = []
    if ozon_url:
        row.append(InlineKeyboardButton(text="🛒 Ozon", url=ozon_url))
    if yandex_url:
        row.append(InlineKeyboardButton(text="🛒 Яндекс", url=yandex_url))
    if wb_url:
        row.append(InlineKeyboardButton(text="🛒 WB", url=wb_url))
    rows = [row] if row else []
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(*, profile: str, market: str = "both") -> InlineKeyboardMarkup:
    """Настройки: профиль моделей, выбор площадок, очистка, «🏠»."""
    fast = "✅ " if profile == "fast" else ""
    quality = "✅ " if profile == "quality" else ""
    m_both = "✅ " if market == "both" else ""
    m_ozon = "✅ " if market == "ozon" else ""
    m_ym = "✅ " if market == "yandex" else ""
    m_wb = "✅ " if market == "wb" else ""
    kb = [
        [InlineKeyboardButton(text=f"{fast}Быстро", callback_data="set_profile:fast"),
         InlineKeyboardButton(text=f"{quality}Качественно",
                              callback_data="set_profile:quality")],
        [InlineKeyboardButton(text="🧹 Очистить контекст", callback_data="set_clear")],
        [InlineKeyboardButton(text=f"{m_both}Все площадки", callback_data="set_market:both"),
         InlineKeyboardButton(text=f"{m_ozon}Ozon", callback_data="set_market:ozon")],
        [InlineKeyboardButton(text=f"{m_ym}Яндекс", callback_data="set_market:yandex"),
         InlineKeyboardButton(text=f"{m_wb}WB", callback_data="set_market:wb")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
