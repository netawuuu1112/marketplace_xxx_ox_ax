"""HTTP-API для Mini App (PRD: один backend, два рендерера).

Эндпоинты (тот же код, что и в чате — общие сессии и кэш):
  GET /api/search?q=…&markets=ozon,yandex&initData=…
  GET /api/reviews?marketplace=…&ext_id=…&initData=…
  GET /api/compare?q=…&initData=…
  GET /api/budget
  GET /api/stats        (uptime, p95 latency, счётчики — метрики ТЗ §5)
  GET /health

Аутентификация:
  1) Telegram initData валидируется подписью HMAC-SHA256 (секрет =
     HMAC_SHA256(bot_token, "WebAppData")) — пользователь берётся из апдейта;
  2) если задан SHOPPER_API_TOKEN — Mini App шлёт его в X-API-Token;
  3) при невалидном initData и SHOPPER_API_ALLOW_ANON=1 (локальная разработка)
     используется user_id из query.

Контракт ответов совпадает с типами в miniapp/src/types.ts.

Метрики (ТЗ §5): каждый запрос замеряется тайминг-мидлварью, p95 latency
считается по скользящему окну из последних 1000 запросов на путь; /api/stats
отдаёт uptime, число запросов и p95 по каждому эндпоинту.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import base64
import binascii
from collections import defaultdict, deque
from urllib.parse import parse_qsl

from aiohttp import web
from aiohttp.web import AppKey

import config
import telemetry
from llm.gateway import BudgetExceeded
from models import Product, Review

logger = logging.getLogger(__name__)

# ── метрики (ТЗ §5): uptime, счётчики, p95 latency ───────────────
APP_START = time.monotonic()
_REQUESTS = {"total": 0}
_LATENCY: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))


def _p95(dq: deque[float]) -> float:
    if not dq:
        return 0.0
    values = sorted(dq)
    idx = min(len(values) - 1, int(len(values) * 0.95))
    return values[idx]


# ── валидация initData ────────────────────────────────────────────

def parse_init_data(init_data: str, bot_token: str) -> int | None:
    """Возвращает user_id из Telegram initData или None (подпись не сошлась).

    Схема Telegram: data_check_string = строки 'k=v' по алфавиту через \n;
    секрет = HMAC-SHA256(bot_token, "WebAppData"); подпись = hex(HMAC-SHA256).
    """
    if not init_data or not bot_token:
        return None
    try:
        params = dict(parse_qsl(init_data))
    except Exception:
        return None
    received = params.pop("hash", "")
    if not received:
        return None
    try:
        auth_date = int(params.get("auth_date", "0"))
    except ValueError:
        return None
    if not auth_date or abs(time.time() - auth_date) > 86400:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return None
    try:
        user = json.loads(params.get("user", "{}"))
        return int(user.get("id"))
    except (ValueError, TypeError):
        return None


def _resolve_user(request: web.Request) -> int:
    """user_id: initData → (dev) query user_id."""
    user_id = parse_init_data(request.headers.get("X-Telegram-Init-Data", ""), config.BOT_TOKEN)
    if user_id is not None:
        return user_id
    if _valid_web_session(request.cookies.get("mf_session", "")):
        return -1
    if config.API_ALLOW_ANON:
        raw = request.query.get("user_id", "")
        if raw.isdigit():
            return int(raw)
    raise web.HTTPUnauthorized(text="initData невалиден или user_id не передан")


def _valid_web_session(token: str) -> bool:
    secret = os.getenv("WEB_SESSION_SECRET", "")
    if not secret or not token:
        return False
    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return data.get("sub") == "admin" and int(data.get("exp", 0)) > time.time()
    except (ValueError, TypeError, binascii.Error):
        return False


def _telegram_admin(request: web.Request) -> bool:
    user_id = parse_init_data(request.headers.get("X-Telegram-Init-Data", ""), config.BOT_TOKEN)
    raw = os.getenv("TELEGRAM_ADMIN_IDS", "")
    return user_id is not None and str(user_id) in {x.strip() for x in raw.split(",") if x.strip()}


def _require_superadmin(request: web.Request) -> None:
    if not (_valid_web_session(request.cookies.get("mf_session", "")) or _telegram_admin(request)):
        raise web.HTTPForbidden(text="Требуются права администратора")


async def _require_admin(request: web.Request) -> None:
    if _valid_web_session(request.cookies.get("mf_session", "")) or _telegram_admin(request):
        return
    user_id = _resolve_user(request)
    db = request.app[CTX_KEY].db
    role = await db.pool.fetchval("SELECT role FROM users WHERE id=$1", user_id) if hasattr(db, "pool") else None
    if role != "admin":
        raise web.HTTPForbidden(text="Требуются права Admin")


async def handle_login(request: web.Request) -> web.Response:
    password = os.getenv("WEB_ADMIN_PASSWORD", "")
    secret = os.getenv("WEB_SESSION_SECRET", "")
    if not password or not secret:
        raise web.HTTPServiceUnavailable(text="Web login is not configured")
    data = await request.json()
    supplied = str(data.get("password", ""))[:256]
    if not hmac.compare_digest(supplied, password):
        raise web.HTTPUnauthorized(text="Неверный пароль")
    payload = base64.urlsafe_b64encode(json.dumps({
        "sub": "admin", "exp": int(time.time()) + 86400,
    }).encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    response = web.json_response({"role": "super_admin"})
    response.set_cookie("mf_session", payload + "." + signature,
                        max_age=86400, httponly=True, samesite="Lax",
                        secure=os.getenv("WEB_COOKIE_SECURE", "0") == "1")
    return response


async def handle_me(request: web.Request) -> web.Response:
    user_id = _resolve_user(request)
    db = request.app[CTX_KEY].db
    if user_id > 0 and hasattr(db, "pool"):
        await db.pool.execute("INSERT INTO users(id) VALUES($1) ON CONFLICT(id) DO NOTHING", user_id)
    admin = _valid_web_session(request.cookies.get("mf_session", "")) or _telegram_admin(request)
    if admin:
        role = "super_admin"
    else:
        role = await db.pool.fetchval("SELECT role FROM users WHERE id=$1", user_id) if hasattr(db, "pool") else None
        role = role or "user"
    return web.json_response({"role": role})


async def handle_logout(request: web.Request) -> web.Response:
    response = web.json_response({"ok": True})
    response.del_cookie("mf_session")
    return response


def _markets(raw: str) -> list[str] | None:
    chosen = [m for m in raw.split(",") if m in ("ozon", "yandex", "wb")]
    return chosen or None


def _serialize_review(r: Review) -> dict:
    """Поле review_id → id (контракт Mini App)."""
    return {
        "id": r.review_id,
        "rating": r.rating,
        "author": r.author,
        "date": r.date,
        "text": r.text,
        "pros": r.pros or None,
        "cons": r.cons or None,
        "bought_here": r.bought_here,
    }


# ── хендлеры ──────────────────────────────────────────────────────

async def handle_search(request: web.Request) -> web.Response:
    ctx = request.app[CTX_KEY]
    q = request.query.get("q", "").strip()
    if not q:
        raise web.HTTPBadRequest(text="Параметр q обязателен")
    user_id = _resolve_user(request)
    t0 = time.monotonic()
    state = await ctx.db.get_session(user_id)
    outcome = await ctx.orch.search_with_constraints(
        user_id, q, state, None,
        markets=_markets(request.query.get("markets", "both")))
    processing_ms = round((time.monotonic() - t0) * 1000, 1)
    return web.json_response({
        "products": [p.model_dump() for p in outcome.top],
        "constraints": outcome.constraints.model_dump(),
        "verdicts": {ext: [v.model_dump() for v in a.verdicts]
                     for ext, a in outcome.analyses.items()},
        "processing_ms": processing_ms,
        "semantic": _semantic_state(ctx),
    })


async def handle_reviews(request: web.Request) -> web.Response:
    ctx = request.app[CTX_KEY]
    market = request.query.get("marketplace", "")
    ext_id = request.query.get("ext_id", "")
    if market not in ("ozon", "yandex", "wb") or not ext_id:
        raise web.HTTPBadRequest(text="marketplace/ext_id обязательны")
    user_id = _resolve_user(request)

    state = await ctx.db.get_session(user_id)
    product = next((p for p in state.last_results
                    if p.marketplace == market and p.ext_id == ext_id), None)
    if product is None:
        product = Product(marketplace=market, ext_id=ext_id,
                          title="", price=0, url="")
    reviews = await ctx.orch._load_reviews(product)
    return web.json_response({"reviews": [_serialize_review(r) for r in reviews]})


async def handle_compare(request: web.Request) -> web.Response:
    ctx = request.app[CTX_KEY]
    q = request.query.get("q", "").strip()
    if not q:
        raise web.HTTPBadRequest(text="Параметр q обязателен")
    _resolve_user(request)
    candidates = await ctx.orch.search_candidates(q, _markets(request.query.get("markets", "both")))
    from matcher.matcher import compare_across_all
    rows = []
    for target in candidates[:3]:
        # одна строка на товар: цены со всех площадок, где нашёлся тот же товар
        result = await compare_across_all(ctx.llm, target, candidates)
        if result is not None:
            rows.append(result.model_dump())
    return web.json_response({"rows": rows})


async def handle_budget(request: web.Request) -> web.Response:
    ctx = request.app[CTX_KEY]
    _resolve_user(request)
    return web.json_response(await ctx.llm.budget_info())


def _semantic_state(ctx) -> str:
    """Статус семантического слоя для /diag и ответов API."""
    embedder = getattr(getattr(ctx.orch, "_reranker", None), "_embedder", None)
    if embedder is None:
        return "off"
    if not embedder.available:
        return f"degraded ({embedder.last_error})"
    return "on"


async def handle_stats(request: web.Request) -> web.Response:
    """Метрики (ТЗ §5): uptime, запросы, p95 latency по эндпоинтам."""
    ctx = request.app[CTX_KEY]
    _resolve_user(request)
    freshness = await ctx.db.cache_freshness()
    return web.json_response({
        "uptime_s": round(time.monotonic() - APP_START, 1),
        "requests": _REQUESTS["total"],
        "p95_ms": {p: round(_p95(dq), 1) for p, dq in _LATENCY.items()},
        "samples": {p: len(dq) for p, dq in _LATENCY.items()},
        "semantic": _semantic_state(ctx),
        "demo": config.DEMO_MODE,
        # Data Freshness (ТЗ §5): цель <= 1 ч (3600 c)
        "data_freshness": {
            **freshness,
            "target_s": 3600,
            # пустой кэш (None) — нет данных, значит нет и устаревших
            "ok": (freshness["newest_age_s"] is None
                    or freshness["newest_age_s"] <= 3600),
        },
        # Coverage (ТЗ §5): успешность парсинга по площадкам
        "coverage": ctx.orch.market_stats(),
    })


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({
        "ok": True,
        "service": "marketfusion-ai",
        "uptime_s": round(time.monotonic() - APP_START, 1),
        "demo": config.DEMO_MODE,
    })


async def handle_marketplace_search(request: web.Request) -> web.Response:
    """Search the vendored multi-market connector through the shared API."""
    _resolve_user(request)
    query = request.query.get("q", "").strip()
    if len(query) < 2 or len(query) > 200:
        raise web.HTTPBadRequest(text="q must contain 2–200 characters")
    from compare_connector.server import compare_prices

    raw_sources = request.query.get("sources", "")
    sources = [x.strip() for x in raw_sources.split(",") if x.strip()] or None
    result = await compare_prices(query, per_source_limit=5, sources=sources)
    return web.json_response(result.model_dump(mode="json"))


async def handle_list_favorites(request: web.Request) -> web.Response:
    user_id = _resolve_user(request)
    products = await request.app[CTX_KEY].db.list_favorites(user_id)
    return web.json_response({"products": [p.model_dump() for p in products]})


async def handle_add_favorite(request: web.Request) -> web.Response:
    user_id = _resolve_user(request)
    try:
        product = Product.model_validate(await request.json())
    except Exception:
        raise web.HTTPBadRequest(text="Некорректный товар")
    added = await request.app[CTX_KEY].db.add_favorite(user_id, product)
    return web.json_response({"added": added})


async def handle_remove_favorite(request: web.Request) -> web.Response:
    user_id = _resolve_user(request)
    try:
        product = Product.model_validate(await request.json())
    except Exception:
        raise web.HTTPBadRequest(text="Некорректный товар")
    await request.app[CTX_KEY].db.remove_favorite(user_id, product)
    return web.json_response({"ok": True})


def _monitor_db(request: web.Request):
    db = request.app[CTX_KEY].db
    if not hasattr(db, "pool"):
        raise web.HTTPServiceUnavailable(text="Monitoring requires PostgreSQL")
    return db


async def handle_list_watches(request: web.Request) -> web.Response:
    from monitoring import list_watches
    return web.json_response({"watches": await list_watches(_monitor_db(request), _resolve_user(request))})


async def handle_create_watch(request: web.Request) -> web.Response:
    from monitoring import create_watch
    user_id = _resolve_user(request)
    try:
        data = await request.json()
        watch = await create_watch(_monitor_db(request), user_id,
                                   str(data.get("query", "")),
                                   float(data["threshold_rub"]) if data.get("threshold_rub") is not None else None,
                                   int(data.get("interval_minutes", 60)),
                                   data.get("sources"))
    except (ValueError, TypeError) as exc:
        raise web.HTTPBadRequest(text=str(exc))
    return web.json_response(watch, status=201)


async def handle_delete_watch(request: web.Request) -> web.Response:
    from monitoring import delete_watch
    deleted = await delete_watch(_monitor_db(request), _resolve_user(request),
                                 int(request.match_info["watch_id"]))
    if not deleted:
        raise web.HTTPNotFound()
    return web.json_response({"ok": True})


async def handle_price_history(request: web.Request) -> web.Response:
    from monitoring import price_history
    rows = await price_history(_monitor_db(request), _resolve_user(request),
                               int(request.match_info["watch_id"]))
    return web.json_response({"history": rows})


async def handle_notifications(request: web.Request) -> web.Response:
    from monitoring import list_notifications
    rows = await list_notifications(_monitor_db(request), _resolve_user(request))
    return web.json_response({"notifications": rows})


async def handle_ai_providers(request: web.Request) -> web.Response:
    from ai_settings import list_providers
    _require_superadmin(request)
    return web.json_response({"providers": await list_providers(_monitor_db(request))})


async def handle_ai_provider_save(request: web.Request) -> web.Response:
    from ai_settings import save_provider
    _require_superadmin(request)
    data = await request.json()
    try:
        await save_provider(_monitor_db(request), str(data.get("name", "")),
                            str(data.get("base_url", "")), str(data.get("model_id", "")),
                            str(data["api_key"]) if data.get("api_key") else None,
                            bool(data.get("enabled", True)))
    except (ValueError, RuntimeError) as exc:
        raise web.HTTPBadRequest(text=str(exc))
    await _monitor_db(request).pool.execute(
        "INSERT INTO audit_events(actor_id,action,subject) VALUES($1,$2,$3)",
        _resolve_user(request), "ai.provider.save", str(data.get("name", ""))[:100])
    return web.json_response({"ok": True})


async def handle_ai_provider_delete(request: web.Request) -> web.Response:
    from ai_settings import delete_provider
    _require_superadmin(request)
    await delete_provider(_monitor_db(request), request.match_info["name"])
    await _monitor_db(request).pool.execute(
        "INSERT INTO audit_events(actor_id,action,subject) VALUES($1,$2,$3)",
        _resolve_user(request), "ai.provider.delete", request.match_info["name"][:100])
    return web.json_response({"ok": True})


async def handle_ai_routes(request: web.Request) -> web.Response:
    from ai_settings import list_routes
    _require_superadmin(request)
    return web.json_response({"routes": await list_routes(_monitor_db(request))})


async def handle_ai_route_save(request: web.Request) -> web.Response:
    from ai_settings import save_route
    _require_superadmin(request)
    data = await request.json()
    try:
        await save_route(_monitor_db(request), str(data.get("kind", "")),
                         str(data.get("provider_name", "")), str(data.get("model_id", "")))
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc))
    await _monitor_db(request).pool.execute(
        "INSERT INTO audit_events(actor_id,action,subject) VALUES($1,$2,$3)",
        _resolve_user(request), "ai.route.save", str(data.get("kind", ""))[:100])
    return web.json_response({"ok": True})


async def handle_admin_users(request: web.Request) -> web.Response:
    _require_superadmin(request)
    db = _monitor_db(request)
    rows = await db.pool.fetch("""
        SELECT id,role,created_at FROM users ORDER BY created_at DESC LIMIT 200
    """)
    return web.json_response({"users": [
        {"id": r["id"], "role": r["role"], "created_at": r["created_at"].isoformat()}
        for r in rows]})


async def handle_admin_overview(request: web.Request) -> web.Response:
    await _require_admin(request)
    row = await _monitor_db(request).pool.fetchrow("""
        SELECT (SELECT count(*) FROM users) AS users,
               (SELECT count(*) FROM watchlists WHERE active) AS active_watches,
               (SELECT count(*) FROM notifications) AS notifications,
               (SELECT count(*) FROM watchlists WHERE last_error IS NOT NULL) AS failed_watches
    """)
    return web.json_response(dict(row))


async def handle_admin_user_role(request: web.Request) -> web.Response:
    _require_superadmin(request)
    db = _monitor_db(request)
    user_id = int(request.match_info["user_id"])
    data = await request.json()
    role = data.get("role")
    if role not in ("user", "admin") or user_id <= 0:
        raise web.HTTPBadRequest(text="Недопустимая роль или пользователь")
    actor_id = _resolve_user(request)
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                INSERT INTO users(id,role) VALUES($1,$2)
                ON CONFLICT(id) DO UPDATE SET role=excluded.role
            """, user_id, role)
            await conn.execute("""
                INSERT INTO audit_events(actor_id,action,subject) VALUES($1,$2,$3)
            """, actor_id, "user.role.update", f"{user_id}:{role}")
    return web.json_response({"ok": True})


async def handle_admin_audit(request: web.Request) -> web.Response:
    _require_superadmin(request)
    rows = await _monitor_db(request).pool.fetch("""
        SELECT actor_id,action,subject,created_at FROM audit_events
        ORDER BY created_at DESC LIMIT 100
    """)
    return web.json_response({"events": [
        {"actor_id": r["actor_id"], "action": r["action"],
         "subject": r["subject"], "created_at": r["created_at"].isoformat()}
        for r in rows]})


@web.middleware
async def _auth_middleware(request: web.Request, handler):
    if config.API_TOKEN and request.path != "/health":
        token = request.headers.get("X-API-Token", "")
        if not hmac.compare_digest(token, config.API_TOKEN):
            raise web.HTTPUnauthorized(text="Неверный X-API-Token")
    return await handler(request)


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "X-API-Token, X-Telegram-Init-Data, Content-Type",
    }


async def _on_prepare_cors(request: web.Request, response: web.StreamResponse):
    """CORS для Mini App: заголовки на ВСЕХ ответах, включая ошибки
    (HTTPException). Origin в preflight не проверяем — токен авторизации
    (initData / X-API-Token) защищает эндпоинты, cookies не используются."""
    response.headers.update(_cors_headers())


@web.middleware
async def _cors_preflight(request: web.Request, handler):
    """OPTIONS-preflight: короткий ответ с CORS-заголовками."""
    if request.method == "OPTIONS":
        return web.Response(headers=_cors_headers())
    return await handler(request)


@web.middleware
async def _error_middleware(request: web.Request, handler):
    try:
        return await handler(request)
    except BudgetExceeded:
        return web.json_response(
            {"error": "Дневной лимит бесплатных запросов исчерпан "
                      "(50/день; после пополнения от $10 — 1000/день)."},
            status=429)
    except web.HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("API error on %s", request.path)
        return web.json_response({"error": "internal_error"}, status=500)


@web.middleware
async def _timing_middleware(request: web.Request, handler):
    """Замер латентности каждого запроса (метрики ТЗ §5)."""
    t0 = time.monotonic()
    with telemetry.start_span(f"api.request.{request.method}"):
        try:
            return await handler(request)
        finally:
            _REQUESTS["total"] += 1
            _LATENCY[request.path].append((time.monotonic() - t0) * 1000.0)
            telemetry.record_duration_ms((time.monotonic() - t0) * 1000.0)


class ApiContext:
    """Держит ссылки на общие объекты бота (db, llm, orch, matcher)."""

    def __init__(self, db, llm, orch, adapters) -> None:
        self.db = db
        self.llm = llm
        self.orch = orch
        self.adapters = adapters
        # matcher-функция привязывается при создании контекста в bot.py,
        # чтобы web.py не зависел от сигнатуры внутренностей matcher.
        self.matcher = None


CTX_KEY = AppKey("ctx", ApiContext)


def create_app(ctx: ApiContext) -> web.Application:
    app = web.Application(
        middlewares=[_cors_preflight, _auth_middleware, _error_middleware,
                     _timing_middleware])
    app.on_response_prepare.append(_on_prepare_cors)
    app[CTX_KEY] = ctx
    app.router.add_get("/api/search", handle_search)
    app.router.add_post("/api/auth/login", handle_login)
    app.router.add_get("/api/auth/me", handle_me)
    app.router.add_post("/api/auth/logout", handle_logout)
    app.router.add_get("/api/marketplaces/search", handle_marketplace_search)
    app.router.add_get("/api/favorites", handle_list_favorites)
    app.router.add_post("/api/favorites", handle_add_favorite)
    app.router.add_delete("/api/favorites", handle_remove_favorite)
    app.router.add_get("/api/watches", handle_list_watches)
    app.router.add_post("/api/watches", handle_create_watch)
    app.router.add_delete("/api/watches/{watch_id:\\d+}", handle_delete_watch)
    app.router.add_get("/api/watches/{watch_id:\\d+}/history", handle_price_history)
    app.router.add_get("/api/notifications", handle_notifications)
    app.router.add_get("/api/admin/ai/providers", handle_ai_providers)
    app.router.add_put("/api/admin/ai/providers", handle_ai_provider_save)
    app.router.add_delete("/api/admin/ai/providers/{name}", handle_ai_provider_delete)
    app.router.add_get("/api/admin/ai/routes", handle_ai_routes)
    app.router.add_put("/api/admin/ai/routes", handle_ai_route_save)
    app.router.add_get("/api/admin/users", handle_admin_users)
    app.router.add_get("/api/admin/overview", handle_admin_overview)
    app.router.add_put("/api/admin/users/{user_id:\\d+}/role", handle_admin_user_role)
    app.router.add_get("/api/admin/audit", handle_admin_audit)
    app.router.add_get("/api/reviews", handle_reviews)
    app.router.add_get("/api/compare", handle_compare)
    app.router.add_get("/api/budget", handle_budget)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_get("/health", handle_health)
    return app


async def _run_standalone() -> None:
    """Запуск только HTTP-API (без поллинга бота) для публичного
    развёртывания. Mini App в этом режиме работает против демо-адаптеров
    и реального LLM (если задан OPENROUTER_API_KEY)."""
    import asyncio

    from adapters import build_adapters
    from core.orchestrator import Orchestrator
    from llm.gateway import LLMGateway
    from storage import create_database

    db = create_database()
    await db.connect()
    llm = LLMGateway(db)
    orch = Orchestrator(db, llm, build_adapters())
    from matcher.matcher import compare_across_markets

    ctx = ApiContext(db, llm, orch, orch._adapters)
    ctx.matcher = lambda target, candidates: compare_across_markets(
        llm, target, candidates)
    app = create_app(ctx)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.API_PORT)
    await site.start()
    logger.info("HTTP-API автономно: http://0.0.0.0:%d (LLM: %s, демо: %s)",
                config.API_PORT, llm.provider_name, config.DEMO_MODE)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await db.close()
        await llm.aclose()
        await orch.aclose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_run_standalone())
