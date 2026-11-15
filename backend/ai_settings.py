"""Encrypted provider configuration shared by web, Mini App and bot."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

from cryptography.fernet import Fernet

KINDS = {"constraints", "review", "rank", "arbiter", "freeform", "vision"}


def cipher() -> Fernet:
    raw = os.getenv("LLM_ENCRYPTION_KEY", "")
    if not raw or raw.startswith("replace_with"):
        raise RuntimeError("LLM_ENCRYPTION_KEY is not configured")
    return Fernet(raw.encode())


def validate_base_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Base URL должен быть HTTPS-адресом без логина и пароля")
    return url.rstrip("/")


async def list_providers(db) -> list[dict]:
    rows = await db.pool.fetch("""
        SELECT name,base_url,model_id,enabled,updated_at FROM ai_providers ORDER BY name
    """)
    return [{"name": r["name"], "base_url": r["base_url"],
             "model_id": r["model_id"], "enabled": r["enabled"],
             "updated_at": r["updated_at"].isoformat()} for r in rows]


async def save_provider(db, name: str, base_url: str, model_id: str,
                        api_key: str | None, enabled: bool) -> None:
    name = name.strip().lower()
    model_id = model_id.strip()
    if not name or len(name) > 40 or not all(c.isalnum() or c in "-_" for c in name):
        raise ValueError("Недопустимое имя провайдера")
    if not model_id or len(model_id) > 160:
        raise ValueError("Укажите Model ID")
    base_url = validate_base_url(base_url)
    if api_key:
        encrypted = cipher().encrypt(api_key.encode()).decode()
        await db.pool.execute("""
            INSERT INTO ai_providers(name,base_url,model_id,api_key_ciphertext,enabled)
            VALUES($1,$2,$3,$4,$5)
            ON CONFLICT(name) DO UPDATE SET base_url=excluded.base_url,
            model_id=excluded.model_id,api_key_ciphertext=excluded.api_key_ciphertext,
            enabled=excluded.enabled,updated_at=now()
        """, name, base_url, model_id, encrypted, enabled)
    else:
        result = await db.pool.execute("""
            UPDATE ai_providers SET base_url=$2,model_id=$3,enabled=$4,updated_at=now()
            WHERE name=$1
        """, name, base_url, model_id, enabled)
        if result == "UPDATE 0":
            raise ValueError("Для нового провайдера нужен API Key")


async def delete_provider(db, name: str) -> None:
    await db.pool.execute("DELETE FROM ai_providers WHERE name=$1", name)


async def list_routes(db) -> list[dict]:
    rows = await db.pool.fetch("SELECT kind,provider_name,model_id FROM ai_routes ORDER BY kind")
    return [dict(r) for r in rows]


async def save_route(db, kind: str, provider_name: str, model_id: str) -> None:
    if kind not in KINDS:
        raise ValueError("Неизвестный тип задачи")
    provider = await db.pool.fetchval(
        "SELECT name FROM ai_providers WHERE name=$1 AND enabled", provider_name)
    if not provider:
        raise ValueError("Провайдер не найден или отключён")
    if not model_id or len(model_id) > 160:
        raise ValueError("Укажите Model ID")
    await db.pool.execute("""
        INSERT INTO ai_routes(kind,provider_name,model_id) VALUES($1,$2,$3)
        ON CONFLICT(kind) DO UPDATE SET provider_name=excluded.provider_name,
        model_id=excluded.model_id
    """, kind, provider_name, model_id)
