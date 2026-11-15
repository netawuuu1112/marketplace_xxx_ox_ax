"""Product-bound monitoring, measured history and a durable notification outbox.

Telegram has no idempotency key for sendMessage: a lost acknowledgement is
ambiguous. Such deliveries become uncertain and are never automatically resent;
the in-app notification remains durable. Expired sending rows follow the same rule.
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

import aiohttp
from pydantic import BaseModel, ConfigDict, Field, model_validator
from telegram_transport import build_notification_connector

logger = logging.getLogger(__name__)
Interval = Literal[15, 30, 60, 180, 360, 720, 1440]


class WatchRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    drop_amount: int | None = Field(default=None, gt=0, strict=True)
    drop_percent: float | None = Field(default=None, gt=0, le=100)
    historical_low: bool = False
    low_30: bool = False
    low_90: bool = False
    back_in_stock: bool = False
    cheaper_source: bool = False


class WatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    product_id: str = Field(min_length=1, max_length=200)
    offer_id: str | None = None
    mode: Literal["offer", "minimum"] = "minimum"
    region: str = Field(min_length=1, max_length=200)
    sources: list[str] | None = Field(default=None, max_length=20)
    threshold: int | None = Field(default=None, gt=0, strict=True)
    interval_minutes: Interval = 60
    rules: WatchRules = Field(default_factory=WatchRules)
    cooldown_minutes: int = Field(default=60, ge=0, le=43200)

    @model_validator(mode="after")
    def binding(self):
        if self.mode == "offer" and not self.offer_id:
            raise ValueError("Выберите конкретное предложение")
        if self.mode == "minimum" and self.offer_id:
            raise ValueError("offer_id доступен только для режима offer")
        return self


class WatchPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    region: str | None = Field(default=None, min_length=1, max_length=200)
    sources: list[str] | None = Field(default=None, max_length=20)
    threshold: int | None = Field(default=None, gt=0, strict=True)
    interval_minutes: Interval | None = None
    active: bool | None = None
    rules: WatchRules | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0, le=43200)

    @model_validator(mode="after")
    def required_if_present(self):
        for name in self.model_fields_set - {"threshold", "sources"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} не может быть null")
        return self


def evaluate_rules(*, price, previous, threshold, rules, state, now,
                   cooldown_minutes, historic_min, low30, low90,
                   in_stock, source, previous_source):
    """Return newly actionable rules and serializable state; unknowns never reset it."""
    state = copy.deepcopy(state)
    fired = []
    candidates = []
    if in_stock is not None:
        if rules.get("back_in_stock") and in_stock and state.get("in_stock") is False:
            state["restock_pending"] = True
        state["in_stock"] = in_stock
        if not in_stock:
            state.pop("restock_pending", None)
    if price is None or price <= 0:
        return [], state
    if threshold is not None:
        if price > threshold + max(1, threshold // 100):
            state["threshold_latched"] = False
        if price <= threshold and not state.get("threshold_latched"):
            candidates.append("threshold")
    for key in ("drop_amount", "drop_percent"):
        if rules.get(key):
            anchor = state.setdefault(key + "_anchor", previous or price)
            # A genuine recovery rearms the drop from the newly measured high.
            anchor = max(anchor, price)
            state[key + "_anchor"] = anchor
            delta = anchor - price
            if delta > 0 and (delta >= rules[key] if key == "drop_amount" else delta * 100 >= anchor * rules[key]):
                candidates.append(key)
    for key, baseline in (("historical_low", historic_min), ("low_30", low30), ("low_90", low90)):
        if rules.get(key) and baseline is not None and price < baseline:
            state[key + "_pending"] = price
        pending = state.get(key + "_pending")
        if rules.get(key) and pending is not None and price <= pending and price < state.get(key + "_emitted", 10**30):
            candidates.append(key)
    if rules.get("back_in_stock") and state.get("restock_pending") and in_stock:
        candidates.append("back_in_stock")
    if rules.get("cheaper_source") and previous is not None and price < previous and previous_source and source != previous_source:
        state["cheaper_source_pending"] = {"source": source, "price": price}
    pending = state.get("cheaper_source_pending")
    if rules.get("cheaper_source") and pending and source == pending["source"] and price <= pending["price"]:
        candidates.append("cheaper_source")
    last = state.get("last_notified_at")
    allowed = last is None or now >= datetime.fromisoformat(last) + timedelta(minutes=cooldown_minutes)
    if candidates and allowed:
        fired = candidates
        state["last_notified_at"] = now.isoformat()
        state["sequence"] = state.get("sequence", 0) + 1
        for key in fired:
            if key == "threshold":
                state["threshold_latched"] = True
            elif key in ("drop_amount", "drop_percent"):
                state[key + "_anchor"] = price
            elif key in ("historical_low", "low_30", "low_90"):
                state[key + "_emitted"] = price
                state.pop(key + "_pending", None)
            elif key == "back_in_stock":
                state.pop("restock_pending", None)
            elif key == "cheaper_source":
                state.pop("cheaper_source_pending", None)
    return fired, state


def _service(db):
    from .service import get_service
    return get_service(db)


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def _watch_json(row):
    data = {key: row[key] for key in ("id", "product_id", "offer_id", "mode", "title", "region", "sources",
            "threshold", "interval_minutes", "active", "last_price", "last_error", "cooldown_minutes", "state")}
    data["rules"] = _json(row["rules"])
    data["last_checked_at"] = row["last_checked_at"].isoformat() if row["last_checked_at"] else None
    return data


async def create_watch(db, user_id: int, payload: WatchCreate) -> dict:
    from .identity import match_variant
    target = await _service(db).get_product(user_id, payload.product_id)
    if not any(offer.region==payload.region for offer in target.offers):
        raise ValueError('Источники не подтвердили регион цены. Наблюдение для выбранного региона пока недоступно.')
    if not target.variant.id or not target.variant.product_id or match_variant(target.variant, target.variant).status != "exact":
        raise ValueError("Не подтверждены модель и характеристики товара")
    offer = next((o for o in target.offers if o.id == payload.offer_id), None)
    if payload.mode == "offer" and (offer is None or offer.match_status != "exact" or not offer.native_id):
        raise ValueError("Выберите подтверждённое предложение этого товара")
    if offer and payload.sources and offer.source not in payload.sources:
        raise ValueError("Выбранная площадка не входит в источники наблюдения")
    if offer and offer.currency != "RUB":
        raise ValueError("Наблюдение поддерживает обычные цены в RUB")
    row = await db.pool.fetchrow("""
        INSERT INTO v2_watches(user_id,product_id,variant_id,offer_id,bound_source,bound_native_id,
            mode,title,target_json,region,sources,threshold,interval_minutes,rules,cooldown_minutes)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13,$14::jsonb,$15) RETURNING *
    """, user_id, payload.product_id, target.variant.id, payload.offer_id,
        offer.source if offer else None, offer.native_id if offer else None, payload.mode,
        target.product.title, target.model_dump_json(), payload.region, payload.sources, payload.threshold,
        payload.interval_minutes, payload.rules.model_dump_json(), payload.cooldown_minutes)
    return _watch_json(row)


async def list_watches(db, user_id: int) -> list[dict]:
    rows = await db.pool.fetch("SELECT * FROM v2_watches WHERE user_id=$1 ORDER BY created_at DESC LIMIT 500", user_id)
    result = [_watch_json(row) for row in rows]
    legacy = await db.pool.fetch("SELECT * FROM watchlists WHERE user_id=$1 ORDER BY created_at DESC LIMIT 500", user_id)
    for row in legacy:
        result.append(dict(id=-row["id"], product_id=None, offer_id=None, mode="minimum", title=row["query"],
            region="", sources=row["sources"], threshold=int(row["threshold_rub"] * 100) if row["threshold_rub"] is not None else None,
            interval_minutes=row["interval_minutes"], active=False, last_price=None,
            last_checked_at=row["last_checked_at"].isoformat() if row["last_checked_at"] else None,
            last_error="Выберите конкретный товар для продолжения наблюдения", rules={}, cooldown_minutes=60, state="needs_selection"))
    return result


async def update_watch(db, user_id: int, watch_id: int, payload: WatchPatch) -> dict | None:
    if watch_id < 0:
        exists = await db.pool.fetchval("SELECT id FROM watchlists WHERE id=$1 AND user_id=$2", -watch_id, user_id)
        if exists:
            raise ValueError("Для старого запроса сначала выберите конкретный товар и создайте наблюдение")
        return None
    # Lock against a finishing worker and invalidate its lease on every edit.
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT * FROM v2_watches WHERE id=$1 AND user_id=$2 FOR UPDATE", watch_id, user_id)
            if row is None:
                return None
            data = dict(row)
            for key in payload.model_fields_set:
                value = getattr(payload, key)
                data[key] = value.model_dump() if key == "rules" else value
            if data["mode"] == "offer" and data["sources"] and data["bound_source"] not in data["sources"]:
                raise ValueError("Выбранная площадка не входит в источники наблюдения")
            # Price history from different regions is never mixed; a region/rule edit rearms only future measurements.
            reset = bool(payload.model_fields_set & {"rules", "threshold", "region", "sources"})
            row = await conn.fetchrow("""UPDATE v2_watches SET region=$3,sources=$4,threshold=$5,interval_minutes=$6,
                active=$7,state=$8,rules=$9::jsonb,cooldown_minutes=$10,
                rule_state=CASE WHEN $11 THEN '{}'::jsonb ELSE rule_state END,
                last_price=CASE WHEN $12 THEN NULL ELSE last_price END,
                last_source=CASE WHEN $12 THEN NULL ELSE last_source END,
                lease_token=NULL,lease_until=NULL,next_run_at=now()
                WHERE id=$1 AND user_id=$2 RETURNING *""", watch_id, user_id, data["region"], data["sources"],
                data["threshold"], data["interval_minutes"], data["active"], "active" if data["active"] else "paused",
                json.dumps(_json(data["rules"])), data["cooldown_minutes"], reset, "region" in payload.model_fields_set)
    return _watch_json(row)


async def delete_watch(db, user_id: int, watch_id: int) -> bool:
    if watch_id < 0:
        result = await db.pool.execute("DELETE FROM watchlists WHERE id=$1 AND user_id=$2", -watch_id, user_id)
    else:
        result = await db.pool.execute("DELETE FROM v2_watches WHERE id=$1 AND user_id=$2", watch_id, user_id)
    return result == "DELETE 1"


async def notifications(db, user_id: int) -> list[dict]:
    rows = await db.pool.fetch("""SELECT id,title,body,created_at,read_at FROM v2_alert_events WHERE user_id=$1
        UNION ALL SELECT -id,title,body,created_at,read_at FROM notifications WHERE user_id=$1
        ORDER BY created_at DESC LIMIT 100""", user_id)
    return [dict(id=r["id"], title=r["title"], body=r["body"], created_at=r["created_at"].isoformat(), read=r["read_at"] is not None) for r in rows]


async def history(db, user_id: int, product_id: str, days="30") -> dict:
    if str(days) not in {"7", "30", "90", "all"}:
        raise ValueError("Период должен быть 7, 30, 90 или all")
    product = await _service(db).get_product(user_id, product_id)
    region = next((o.region for o in product.offers if o.region), None)
    if region is None:
        region = await db.pool.fetchval("""SELECT region FROM v2_observations WHERE user_id=$1 AND product_id=$2
            ORDER BY captured_at DESC,id DESC LIMIT 1""", user_id, product_id) or ""
    since = None if str(days) == "all" else datetime.now(timezone.utc) - timedelta(days=int(days))
    rows = await db.pool.fetch("""SELECT captured_at,price,source,offer_id,region,currency,is_winner
        FROM v2_observations WHERE user_id=$1 AND product_id=$2 AND ($3::timestamptz IS NULL OR captured_at >= $3)
        AND region=$4 AND currency='RUB'
        ORDER BY captured_at DESC,id DESC LIMIT 5000""", user_id, product_id, since, region)
    points = [dict(captured_at=r["captured_at"].isoformat(), price=r["price"], source=r["source"], offer_id=r["offer_id"],
                   region=r["region"], currency=r["currency"], is_winner=r["is_winner"]) for r in reversed(rows)]
    aggregate = await db.pool.fetchrow("""SELECT min(price) AS min,max(price) AS max,avg(price) AS average
        FROM v2_observations WHERE user_id=$1 AND product_id=$2 AND ($3::timestamptz IS NULL OR captured_at >= $3)
        AND region=$4 AND currency='RUB'""", user_id, product_id, since, region)
    return {"points": points, "summary": {"min": aggregate["min"], "max": aggregate["max"],
            "average": float(aggregate["average"]) if aggregate["average"] is not None else None}, "region": region, "currency": "RUB"}


async def claim_due_watch(db):
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            return await conn.fetchrow("""UPDATE v2_watches SET lease_token=$1,lease_until=now()+interval '15 minutes'
                WHERE id=(SELECT id FROM v2_watches WHERE active AND state='active' AND next_run_at<=now()
                AND (lease_until IS NULL OR lease_until<=now()) ORDER BY next_run_at,id
                FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *""", uuid4().hex)


def _select_offers(row, target, snapshot):
    from .identity import match_variant
    selected = {}
    for group in snapshot.groups:
        if match_variant(target.variant, group.variant).status != "exact":
            continue
        for offer in group.offers:
            if offer.match_status != "exact" or offer.currency != row["currency"] or offer.region != row["region"]:
                continue
            if row["sources"] and offer.source not in row["sources"]:
                continue
            if row["mode"] == "offer" and (offer.source != row["bound_source"] or offer.native_id != row["bound_native_id"]):
                continue
            selected[(offer.source, offer.native_id)] = offer
    return list(selected.values())


def _alert_body(row, winner, previous, fired, now):
    amount = lambda value: f"{value / 100:,.2f}".replace(",", " ") + " ₽"
    lines = ["🔔 Цена или наличие изменились", row["title"]]
    if previous is not None:
        lines.append("Было: " + amount(previous))
    lines.append("Сейчас: " + amount(winner.price))
    if previous is not None and previous > winner.price:
        lines.append(f"Снижение: {amount(previous-winner.price)} (−{(previous-winner.price)*100/previous:.1f}%)")
    lines.append("Площадка: " + winner.source)
    d = winner.delivery
    if d.confidence == "confirmed" and d.region == row["region"] and d.date_min:
        lines.append("Доставка: " + d.date_min + (" — " + d.date_max if d.date_max and d.date_max != d.date_min else ""))
    if row["threshold"] is not None:
        lines.append("Твой порог: " + amount(row["threshold"]))
    lines.extend(["Проверено: " + now.isoformat(), "Условия: " + ", ".join(fired), winner.url])
    return "\n".join(lines)


async def check_watch(db, row, bot_token: str = "") -> None:
    from .models import ProductGroup, SearchRequest
    if row is None:
        return
    try:
        target = ProductGroup.model_validate(_json(row["target_json"]))
        attributes = " ".join(dict.fromkeys(target.variant.attributes.values()))
        query = (target.product.title[:max(2, 199-len(attributes))] + " " + attributes)[:200]
        snapshot = await _service(db).search(row["user_id"], SearchRequest(query=query, region=row["region"], sources=row["sources"]))
        offers = _select_offers(row, target, snapshot)
        eligible = [o for o in offers if o.price is not None and o.price > 0 and o.in_stock is not False]
        winner = min(eligible, key=lambda o: (o.price, o.source, o.id), default=None)
        known_stock = True if any(o.in_stock is True for o in offers) else False if offers and all(o.in_stock is False for o in offers) else None
        now = datetime.now(timezone.utc)
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow("""SELECT * FROM v2_watches WHERE id=$1 AND lease_token=$2
                    AND lease_until>now() AND active AND state='active' FOR UPDATE""", row["id"], row["lease_token"])
                if current is None:
                    return
                baseline = await conn.fetchrow("""SELECT min(price) AS historic_min,
                    min(price) FILTER(WHERE captured_at>=now()-interval '30 days') AS low30,
                    min(price) FILTER(WHERE captured_at>=now()-interval '90 days') AS low90
                    FROM v2_observations WHERE watch_id=$1 AND region=$2 AND currency=$3 AND is_winner""",
                    row["id"], row["region"], row["currency"])
                fired, state = evaluate_rules(price=winner.price if winner else None, previous=current["last_price"],
                    threshold=current["threshold"], rules=_json(current["rules"]), state=_json(current["rule_state"]),
                    now=now, cooldown_minutes=current["cooldown_minutes"], historic_min=baseline["historic_min"],
                    low30=baseline["low30"], low90=baseline["low90"], in_stock=known_stock,
                    source=winner.source if winner else None, previous_source=current["last_source"])
                for offer in eligible:
                    await conn.execute("""INSERT INTO v2_observations(watch_id,user_id,product_id,variant_id,offer_id,
                        source,price,currency,region,product_url,is_winner,captured_at)
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""", row["id"], row["user_id"],
                        row["product_id"], row["variant_id"], offer.id, offer.source, offer.price, offer.currency,
                        row["region"], offer.url, offer.id == winner.id, now)
                if fired and winner:
                    body = _alert_body(current, winner, current["last_price"], fired, now)
                    await conn.execute("""INSERT INTO v2_alert_events(event_key,watch_id,user_id,title,body,payload)
                        VALUES($1,$2,$3,$4,$5,$6::jsonb) ON CONFLICT(event_key) DO NOTHING""",
                        f"{row['id']}:{row['lease_token']}", row["id"], row["user_id"], "Цена или наличие изменились", body,
                        json.dumps({"rules": fired, "offer_id": winner.id, "url": winner.url, "product_id": row["product_id"],
                                    "price": winner.price, "source": winner.source}, ensure_ascii=False))
                await conn.execute("""UPDATE v2_watches SET rule_state=$3::jsonb,
                    last_price=COALESCE($4,last_price),last_source=COALESCE($5,last_source),last_checked_at=$6,
                    last_success_at=CASE WHEN $4::bigint IS NOT NULL THEN $6 ELSE last_success_at END,last_error=$7,
                    next_run_at=now()+interval '1 minute'*interval_minutes,lease_token=NULL,lease_until=NULL
                    WHERE id=$1 AND lease_token=$2""", row["id"], row["lease_token"], json.dumps(state),
                    winner.price if winner else None, winner.source if winner else None, now,
                    None if winner else "Нет подтверждённой обычной цены выбранного варианта")
    except asyncio.CancelledError:
        raise  # Lease recovery on restart, without recording a fabricated result.
    except Exception as exc:
        logger.warning("V2 watch %s failed: %s", row["id"], type(exc).__name__)
        await db.pool.execute("""UPDATE v2_watches SET last_checked_at=now(),last_error=$3,
            next_run_at=now()+interval '1 minute'*interval_minutes,lease_token=NULL,lease_until=NULL
            WHERE id=$1 AND lease_token=$2""", row["id"], row["lease_token"], type(exc).__name__)


async def _send_telegram(token, user_id, body, payload):
    import config
    base = getattr(config, "MINIAPP_URL", "").rstrip("/")
    buttons = [[{"text": "🛒 Купить", "url": payload["url"]}]]
    if base:
        buttons += [[{"text": "📊 История цены", "url": base + "/?product=" + payload["product_id"] + "&view=history"},
                     {"text": "⚙️ Настроить отслеживание", "url": base + "/?section=watching"}]]
    connector = build_notification_connector()
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": user_id, "text": body, "reply_markup": {"inline_keyboard": buttons}},
                timeout=aiohttp.ClientTimeout(total=45 if connector else 10)) as response:
            response.raise_for_status()
            result = await response.json()
            if not result.get("ok"):
                raise RuntimeError("Telegram rejected notification")
            return result["result"]["message_id"]


async def deliver_one(db, token: str) -> bool:
    if not token:
        return False
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            # A crash after send but before its acknowledgement cannot safely be retried.
            await conn.execute("""UPDATE v2_alert_events SET delivery_state='uncertain',delivery_error='send acknowledgement unknown'
                WHERE delivery_state='sending' AND send_started_at<now()-interval '2 minutes'""")
            row = await conn.fetchrow("""UPDATE v2_alert_events SET delivery_state='sending',send_started_at=now()
                WHERE id=(SELECT id FROM v2_alert_events WHERE delivery_state='pending' AND user_id>0
                ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *""")
    if row is None:
        return False
    try:
        message_id = await _send_telegram(token, row["user_id"], row["body"], _json(row["payload"]))
        await db.pool.execute("""UPDATE v2_alert_events SET delivery_state='sent',sent_at=now(),telegram_message_id=$2
            WHERE id=$1 AND delivery_state='sending'""", row["id"], message_id)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        await db.pool.execute("""UPDATE v2_alert_events SET delivery_state='uncertain',delivery_error=$2
            WHERE id=$1 AND delivery_state='sending'""", row["id"], type(exc).__name__)
        logger.warning("V2 alert %s delivery uncertain: %s", row["id"], type(exc).__name__)
    return True


async def run_worker(db, token: str = "") -> None:
    while True:
        try:
            delivered = await deliver_one(db, token)
            row = await claim_due_watch(db)
            if row:
                await check_watch(db, row)
            elif not delivered:
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("V2 worker iteration failed: %s", type(exc).__name__)
            await asyncio.sleep(15)
