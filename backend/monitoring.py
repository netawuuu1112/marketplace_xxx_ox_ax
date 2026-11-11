"""Persistent price watches backed by the application's PostgreSQL database."""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

import aiohttp

from compare_connector.server import compare_prices

logger = logging.getLogger(__name__)
ALLOWED_INTERVALS = {15, 30, 60, 180, 360, 720, 1440}


def _watch_json(row) -> dict:
    return {
        "id": row["id"], "query": row["query"], "sources": row["sources"],
        "threshold_rub": float(row["threshold_rub"]) if row["threshold_rub"] is not None else None,
        "interval_minutes": row["interval_minutes"], "active": row["active"],
        "last_price_rub": float(row["last_price_rub"]) if row["last_price_rub"] is not None else None,
        "last_checked_at": row["last_checked_at"].isoformat() if row["last_checked_at"] else None,
        "next_run_at": row["next_run_at"].isoformat(), "last_error": row["last_error"],
    }


async def list_watches(db, user_id: int) -> list[dict]:
    rows = await db.pool.fetch(
        "SELECT * FROM watchlists WHERE user_id=$1 ORDER BY created_at DESC", user_id)
    return [_watch_json(row) for row in rows]


async def create_watch(db, user_id: int, query: str, threshold: float | None,
                       interval: int, sources: list[str] | None) -> dict:
    query = query.strip()
    if len(query) < 2 or len(query) > 200:
        raise ValueError("Запрос должен содержать от 2 до 200 символов")
    if threshold is not None and (threshold <= 0 or threshold > 100_000_000):
        raise ValueError("Порог цены должен быть положительным")
    if interval not in ALLOWED_INTERVALS:
        raise ValueError("Недопустимый интервал")
    row = await db.pool.fetchrow("""
        INSERT INTO watchlists(user_id,query,threshold_rub,interval_minutes,sources)
        VALUES($1,$2,$3,$4,$5) RETURNING *
    """, user_id, query, Decimal(str(threshold)) if threshold is not None else None,
        interval, sources)
    return _watch_json(row)


async def delete_watch(db, user_id: int, watch_id: int) -> bool:
    result = await db.pool.execute(
        "DELETE FROM watchlists WHERE id=$1 AND user_id=$2", watch_id, user_id)
    return result == "DELETE 1"


async def price_history(db, user_id: int, watch_id: int) -> list[dict]:
    rows = await db.pool.fetch("""
        SELECT h.captured_at,h.price_rub,h.source,h.product_url
        FROM price_history h JOIN watchlists w ON w.id=h.watch_id
        WHERE w.id=$1 AND w.user_id=$2 ORDER BY h.captured_at DESC LIMIT 500
    """, watch_id, user_id)
    return [{"captured_at": r["captured_at"].isoformat(),
             "price_rub": float(r["price_rub"]), "source": r["source"],
             "product_url": r["product_url"]} for r in rows]


async def list_notifications(db, user_id: int) -> list[dict]:
    rows = await db.pool.fetch("""
        SELECT id,title,body,created_at,read_at FROM notifications
        WHERE user_id=$1 ORDER BY created_at DESC LIMIT 100
    """, user_id)
    return [{"id": r["id"], "title": r["title"], "body": r["body"],
             "created_at": r["created_at"].isoformat(),
             "read": r["read_at"] is not None} for r in rows]


async def claim_due_watch(db):
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                SELECT * FROM watchlists WHERE active AND next_run_at<=now()
                ORDER BY next_run_at FOR UPDATE SKIP LOCKED LIMIT 1
            """)
            if row is None:
                return None
            await conn.execute("""
                UPDATE watchlists SET next_run_at=now()+interval '1 minute' * interval_minutes
                WHERE id=$1
            """, row["id"])
            return row


async def check_watch(db, row, bot_token: str = "") -> None:
    watch_id = row["id"]
    try:
        result = await compare_prices(row["query"], per_source_limit=5,
                                      sources=row["sources"])
        offer = result.cheapest_comparable
        if offer is None or offer.price_rub is None:
            raise RuntimeError("Источники не вернули сопоставимую цену")
        price = Decimal(str(offer.price_rub))
        telegram_body = None
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO price_history(watch_id,price_rub,source,product_url)
                    VALUES($1,$2,$3,$4)
                """, watch_id, price, offer.source, offer.url)
                await conn.execute("""
                    UPDATE watchlists SET last_price_rub=$2,last_checked_at=now(),last_error=NULL
                    WHERE id=$1
                """, watch_id, price)
                threshold = row["threshold_rub"]
                previous = row["last_price_rub"]
                if threshold is not None and price <= threshold and (previous is None or previous > threshold):
                    title = "Цена достигла порога"
                    body = f"{row['query']}: {price} ₽ на {offer.source}. {offer.url}"
                    await conn.execute("""
                        INSERT INTO notifications(user_id,title,body) VALUES($1,$2,$3)
                    """, row["user_id"], title, body)
                    if bot_token and row["user_id"] > 0:
                        telegram_body = body
        if telegram_body:
            await _send_telegram(bot_token, row["user_id"], telegram_body)
    except Exception as exc:
        logger.warning("Watch %s failed: %s", watch_id, type(exc).__name__)
        await db.pool.execute("""
            UPDATE watchlists SET last_checked_at=now(),last_error=$2 WHERE id=$1
        """, watch_id, str(exc)[:300])


async def _send_telegram(token: str, user_id: int, body: str) -> None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                    json={"chat_id": user_id, "text": body},
                                    timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
    except Exception:
        logger.warning("Telegram delivery failed for user %s", user_id)


async def run_worker(db, bot_token: str = "") -> None:
    while True:
        row = await claim_due_watch(db)
        if row is None:
            await asyncio.sleep(15)
            continue
        await check_watch(db, row, bot_token)
