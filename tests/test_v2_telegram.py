"""Offline Telegram boundaries: no polling, credentials or Bot API calls."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import bot
from keyboards import product_card_keyboard
from models import Product, SessionState


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(bot.config, "MINIAPP_URL", "https://marketfusion.test/app")
    monkeypatch.setattr(bot.orch, "search_with_constraints", AsyncMock(side_effect=AssertionError("legacy search must not run")))


def run(coro):
    return asyncio.run(coro)


def message(user_id=42, text="SSD"):
    progress = NS(edit_text=AsyncMock(), edit_reply_markup=AsyncMock(), delete=AsyncMock())
    return NS(from_user=NS(id=user_id), chat=NS(id=user_id, type="private"),
              text=text, photo=None, answer=AsyncMock(return_value=progress)), progress


def callback(data, user_id=42, chat_id=42):
    msg, _ = message(chat_id)
    msg.edit_text = AsyncMock()
    return NS(data=data, from_user=NS(id=user_id), message=msg, answer=AsyncMock())


def test_start_sends_one_welcome_and_removes_legacy_reply_keyboard():
    msg, sent = message(text="/start")
    run(bot.cmd_start(msg))
    assert msg.answer.await_count == 1
    markup = msg.answer.call_args.kwargs["reply_markup"]
    assert isinstance(markup, ReplyKeyboardRemove)
    assert not isinstance(markup, ReplyKeyboardMarkup)
    inline = sent.edit_reply_markup.call_args.kwargs["reply_markup"]
    assert isinstance(inline, InlineKeyboardMarkup)
    buttons = [b for row in inline.inline_keyboard for b in row]
    assert len(buttons) == 2
    assert any(b.web_app for b in buttons)


def test_text_handler_does_not_swallow_photos():
    handler = next(h for h in bot.router.message.handlers if h.callback.__name__ == "on_text")
    photo, _ = message(text=None)
    photo.photo = [NS(file_id="offline-photo")]
    accepted, _ = run(handler.check(photo))
    assert not accepted


def test_legacy_card_has_contextual_compare_without_duplicate_home():
    product = Product(marketplace="ozon", ext_id="1", title="SSD", price=1200, url="https://ozon.ru/product/1")
    buttons = [b for row in product_card_keyboard(product).inline_keyboard for b in row]
    assert all("Ozon vs YM" not in b.text for b in buttons)
    assert all(b.callback_data != "menu:main" for b in buttons)


def test_foreign_private_chat_callback_is_rejected_before_session_read(monkeypatch):
    storage = NS(get_session=AsyncMock(return_value=SessionState()))
    monkeypatch.setattr(bot, "db", storage)
    call = callback("compare:ozon:1", chat_id=99)
    run(bot.cb_compare(call))
    assert call.answer.call_args.kwargs.get("show_alert") is True
    assert storage.get_session.await_count == 0


def test_stale_legacy_product_is_rejected(monkeypatch):
    monkeypatch.setattr(bot, "db", NS(get_session=AsyncMock(return_value=SessionState()),
                                     list_favorites=AsyncMock(return_value=[])))
    call = callback("compare:ozon:missing")
    run(bot.cb_compare(call))
    assert call.answer.call_args.kwargs.get("show_alert") is True
    assert call.message.answer.await_count == 0


def test_v2_callback_denies_unowned_product(monkeypatch):
    service = NS(get_product=AsyncMock(side_effect=LookupError("not owned")))
    monkeypatch.setattr(bot, "_catalog_service", lambda: service, raising=False)
    call = callback("v2product:foreign")
    run(bot.cb_v2_product(call))
    assert call.answer.call_args.kwargs.get("show_alert") is True
    assert call.message.edit_text.await_count == 0


def test_malformed_callback_is_answered_without_mutation(monkeypatch):
    monkeypatch.setattr(bot, "db", NS(get_session=AsyncMock(side_effect=AssertionError("must not read"))))
    call = callback("compare:broken")
    run(bot.cb_compare(call))
    assert call.answer.call_args.kwargs.get("show_alert") is True
    assert call.message.answer.await_count == 0


def test_compare_callback_preserves_human_actor(monkeypatch):
    product = Product(marketplace="ozon", ext_id="1", title="SSD", price=1200, url="https://ozon.ru/product/1")
    monkeypatch.setattr(bot, "db", NS(get_session=AsyncMock(return_value=SessionState(last_results=[product]))))
    search = AsyncMock()
    monkeypatch.setattr(bot, "_run_search", search)
    call = callback("compare:ozon:1")
    call.message.from_user.id = 999  # Telegram callback message author is the bot.
    run(bot.cb_compare(call))
    assert search.call_args.kwargs["user_id"] == 42


def test_watch_command_requires_selected_product_instead_of_text_watch(monkeypatch):
    search = AsyncMock()
    monkeypatch.setattr(bot, "_run_search", search)
    msg, _ = message(text="/watch SSD 1TB | 5000")
    run(bot.cmd_watch(msg))
    assert search.await_count == 1
    assert search.call_args.args[1] == "SSD 1TB"


def test_delivery_cost_is_visible_even_when_date_is_unknown():
    best = NS(id="o1", source="wb", currency="RUB", delivery=NS(price=19900, date_min=None, date_max=None, confidence="reported"))
    group = NS(product=NS(title="SSD"), offers=[best], best_price_offer_id="o1", minimum_price=120000,
               minimum_total=None, sources_count=1, match_status="exact")
    rendered = bot._catalog_card_text(group)
    assert "199 ₽" in rendered
    assert "неизвест" in rendered.lower()


def test_not_modified_message_never_creates_duplicate(monkeypatch):
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import EditMessageText
    call = callback("menu:main")
    call.message.edit_text.side_effect = TelegramBadRequest(
        method=EditMessageText(chat_id=42, message_id=1, text="same"), message="Bad Request: message is not modified")
    run(bot._edit_or_answer(call, "same"))
    assert call.message.answer.await_count == 0


def test_telegram_commands_keep_legacy_functions_discoverable():
    client = NS(set_chat_menu_button=AsyncMock(), set_my_commands=AsyncMock())
    run(bot.configure_bot_navigation(client))
    commands = client.set_my_commands.call_args.kwargs["commands"]
    names = {c.command for c in commands}
    assert {"start", "search", "compare", "favorites", "settings", "ask", "watch", "watches", "history", "notifications"} <= names
    assert len(names) == len(commands)
    assert client.set_chat_menu_button.call_args.kwargs["menu_button"].web_app.url.startswith("https://")


def test_legacy_review_callbacks_answer_stale_product(monkeypatch):
    monkeypatch.setattr(bot, "db", NS(get_session=AsyncMock(return_value=SessionState()), list_favorites=AsyncMock(return_value=[])))
    call = callback("back:ozon:gone")
    run(bot.cb_back(call))
    assert call.answer.call_args.kwargs.get("show_alert") is True


def test_catalog_results_preserve_existing_review_and_favorite_actions():
    from keyboards import catalog_product_keyboard
    product = Product(marketplace="ozon", ext_id="1", title="SSD", price=1200, url="https://ozon.ru/product/1")
    offer = NS(id="o1", source="ozon", native_id="1", title="SSD", price=120000, currency="RUB", image_url="",
               rating=4.5, match_status="exact", url=product.url)
    group = NS(product=NS(id="p1", title="SSD", image_url=""), offers=[offer], best_price_offer_id="o1")
    keyboard = catalog_product_keyboard(group, legacy_product=product)
    callbacks = [b.callback_data or "" for row in keyboard.inline_keyboard for b in row]
    assert any(c.startswith("reviews:ozon:") for c in callbacks)
    assert any(c.startswith("fav:ozon:") for c in callbacks)


@pytest.mark.parametrize('source,legacy', [('wildberries','wb'),('yandex_market','yandex'),('ozon','ozon')])
def test_real_catalog_source_names_preserve_legacy_actions(source,legacy):
    from keyboards import catalog_product_keyboard
    offer=NS(id='offer',source=source,native_id='123',title='Kingston NV3 1TB',price=500000,
             url='https://example.com/product/123',image_url=None,rating=4.7)
    group=NS(product=NS(id='product'),offers=[offer],best_price_offer_id='offer')
    product=bot._legacy_catalog_product(group)
    assert product is not None and product.marketplace==legacy
    keyboard=catalog_product_keyboard(group,legacy_product=product)
    callbacks=[b.callback_data or '' for row in keyboard.inline_keyboard for b in row]
    assert any(c.startswith('reviews:'+legacy+':') for c in callbacks)
    assert any(c.startswith('fav:'+legacy+':') for c in callbacks)


def test_catalog_search_edits_status_and_keeps_related_separate(monkeypatch):
    offer = NS(id="o1", source="wb", price=120050, currency="RUB", url="https://www.wildberries.ru/catalog/1/detail.aspx",
               match_status="exact", in_stock=True, condition="new", conditional_prices=[],
               delivery=NS(price=None, date_min=None, date_max=None, confidence="unknown"))
    group = NS(product=NS(id="p1", title="Kingston NV3 1TB", image_url=None),
               offers=[offer], minimum_price=120050, minimum_total=None, sources_count=1,
               best_price_offer_id="o1", best_total_offer_id=None, match_status="exact", reasons=[])
    related = NS(product=NS(id="p2", title="Kingston NV3 500GB", image_url=None))
    snapshot = NS(groups=[group], related=[related], sources=[NS(source="ozon", status="blocked", detail="blocked")],
                  complete=False, status="complete", query="Kingston NV3 1TB")
    service = NS(search=AsyncMock(return_value=snapshot))
    monkeypatch.setattr(bot, "_catalog_service", lambda: service, raising=False)
    monkeypatch.setattr(bot, "db", NS(get_session=AsyncMock(return_value=SessionState()), save_session=AsyncMock()))
    msg, progress = message()
    run(bot._run_search(msg, "Kingston NV3 1TB"))
    assert progress.edit_text.await_count >= 1
    assert progress.delete.await_count == 0
    rendered = "\n".join(str(c.args[0]) for c in progress.edit_text.call_args_list + msg.answer.call_args_list)
    assert "1 200,50" in rendered
    assert "500GB" in rendered and "Похожие" in rendered
    assert "неизвест" in rendered.lower()
    assert "ozon" in rendered.lower()
    assert service.search.call_args.args[0] == 42
