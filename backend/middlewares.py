"""Middleware: троттлинг (защита от спама) и логирование апдейтов."""
from __future__ import annotations

import logging
import time

import config
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)

_last_seen: dict[int, float] = {}


class ThrottlingMiddleware(BaseMiddleware):
    """Не чаще одного события от пользователя в THROTTLE_MIN_INTERVAL с.

    Работает и для сообщений, и для inline-колбэков (у CallbackQuery есть
    from_user). Отброшенный колбэк получает пустой answer — Telegram гасит
    «крутящуюся» кнопку, но хендлер повторно не вызывается.
    """

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = getattr(event, "from_user", None)
        if user is not None:
            now = time.monotonic()
            last = _last_seen.get(user.id, 0.0)
            if now - last < config.THROTTLE_MIN_INTERVAL:
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer()
                    except Exception:  # pragma: no cover
                        pass
                return None
            _last_seen[user.id] = now
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Пишет в лог все входящие сообщения и колбэки."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        from llm.usage import user_id
        principal=getattr(getattr(event,'from_user',None),'id',None)
        logger.info('Telegram %s from %s',type(event).__name__,principal)
        token=user_id.set(principal)
        try:
            return await handler(event,data)
        finally:
            user_id.reset(token)
