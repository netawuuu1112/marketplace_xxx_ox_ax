"""PostgreSQL implementation of the shared Smart Shopper storage contract."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import asyncpg

from models import Product, SessionState
from .db import Database


class PostgresDatabase(Database):
    def __init__(self, url: str) -> None:
        self._url = url
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        assert self._pool is not None, "database is not connected"
        return self._pool

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._url, min_size=1, max_size=10)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id BIGINT PRIMARY KEY,
                    state TEXT NOT NULL,
                    updated TIMESTAMPTZ NOT NULL
                );
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id BIGINT NOT NULL,
                    marketplace TEXT NOT NULL,
                    ext_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    price BIGINT NOT NULL,
                    url TEXT NOT NULL,
                    added TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (user_id, marketplace, ext_id)
                );
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at);
                CREATE TABLE IF NOT EXISTS llm_budget (
                    day TEXT PRIMARY KEY,
                    used INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS watchlists (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    query TEXT NOT NULL,
                    sources TEXT[],
                    threshold_rub NUMERIC(12,2),
                    interval_minutes INTEGER NOT NULL DEFAULT 60,
                    active BOOLEAN NOT NULL DEFAULT true,
                    last_price_rub NUMERIC(12,2),
                    last_checked_at TIMESTAMPTZ,
                    next_run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE INDEX IF NOT EXISTS idx_watchlists_due
                    ON watchlists(next_run_at) WHERE active;
                CREATE TABLE IF NOT EXISTS price_history (
                    id BIGSERIAL PRIMARY KEY,
                    watch_id BIGINT NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
                    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    price_rub NUMERIC(12,2) NOT NULL,
                    source TEXT NOT NULL,
                    product_url TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_price_history_watch
                    ON price_history(watch_id,captured_at DESC);
                CREATE TABLE IF NOT EXISTS notifications (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    read_at TIMESTAMPTZ
                );
                CREATE INDEX IF NOT EXISTS idx_notifications_user
                    ON notifications(user_id,created_at DESC);
                CREATE TABLE IF NOT EXISTS ai_providers (
                    name TEXT PRIMARY KEY,
                    base_url TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    api_key_ciphertext TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT true,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS ai_routes (
                    kind TEXT PRIMARY KEY,
                    provider_name TEXT NOT NULL REFERENCES ai_providers(name) ON DELETE CASCADE,
                    model_id TEXT NOT NULL
                );
            """)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def get_session(self, user_id: int) -> SessionState:
        row = await self.pool.fetchrow("SELECT state FROM sessions WHERE user_id=$1", user_id)
        if row is None:
            return SessionState()
        try:
            return SessionState.model_validate_json(row["state"])
        except Exception:
            return SessionState()

    async def save_session(self, user_id: int, state: SessionState) -> None:
        await self.pool.execute("""
            INSERT INTO users(id) VALUES($1) ON CONFLICT(id) DO NOTHING
        """, user_id)
        await self.pool.execute("""
            INSERT INTO sessions(user_id,state,updated) VALUES($1,$2,now())
            ON CONFLICT(user_id) DO UPDATE SET state=excluded.state,updated=excluded.updated
        """, user_id, state.model_dump_json())

    async def cache_get(self, key: str) -> str | None:
        return await self.pool.fetchval(
            "SELECT value FROM cache WHERE key=$1 AND expires_at>now()", key)

    async def cache_set(self, key: str, value: str, ttl_seconds: int) -> None:
        now = datetime.now(timezone.utc)
        await self.pool.execute("""
            INSERT INTO cache(key,value,created_at,expires_at) VALUES($1,$2,$3,$4)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,
            created_at=excluded.created_at,expires_at=excluded.expires_at
        """, key, value, now, now + timedelta(seconds=ttl_seconds))

    async def cache_freshness(self) -> dict:
        row = await self.pool.fetchrow(
            "SELECT count(*) AS n,max(created_at) AS newest FROM cache")
        newest = row["newest"]
        return {"entries": row["n"],
                "newest_age_s": round((datetime.now(timezone.utc)-newest).total_seconds(), 1) if newest else None,
                "newest_at": newest.isoformat() if newest else None}

    async def add_favorite(self, user_id: int, p: Product) -> bool:
        result = await self.pool.execute("""
            INSERT INTO favorites(user_id,marketplace,ext_id,title,price,url,added)
            VALUES($1,$2,$3,$4,$5,$6,now()) ON CONFLICT DO NOTHING
        """, user_id, p.marketplace, p.ext_id, p.title, p.price, p.url)
        return result == "INSERT 0 1"

    async def remove_favorite(self, user_id: int, p: Product) -> None:
        await self.pool.execute(
            "DELETE FROM favorites WHERE user_id=$1 AND marketplace=$2 AND ext_id=$3",
            user_id, p.marketplace, p.ext_id)

    async def list_favorites(self, user_id: int) -> list[Product]:
        rows = await self.pool.fetch("""
            SELECT marketplace,ext_id,title,price,url FROM favorites
            WHERE user_id=$1 ORDER BY added DESC
        """, user_id)
        return [Product(marketplace=r["marketplace"], ext_id=r["ext_id"],
                        title=r["title"], price=r["price"], url=r["url"])
                for r in rows]

    async def budget_used(self, day: str) -> int:
        return await self.pool.fetchval(
            "SELECT used FROM llm_budget WHERE day=$1", day) or 0

    async def budget_increment(self, day: str) -> int:
        return await self.pool.fetchval("""
            INSERT INTO llm_budget(day,used) VALUES($1,1)
            ON CONFLICT(day) DO UPDATE SET used=llm_budget.used+1
            RETURNING used
        """, day)

    async def get_setting(self, key: str, default: str = "") -> str:
        value = await self.pool.fetchval("SELECT value FROM settings WHERE key=$1", key)
        return value if value is not None else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.pool.execute("""
            INSERT INTO settings(key,value) VALUES($1,$2)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, key, value)

    async def stats(self) -> dict:
        return {table: await self.pool.fetchval(f"SELECT count(*) FROM {table}")
                for table in ("sessions", "favorites", "cache")}

    async def cleanup_expired(self) -> int:
        result = await self.pool.execute("DELETE FROM cache WHERE expires_at<=now()")
        return int(result.split()[-1])
