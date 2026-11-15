"""Хранилище: SQLite-БД (сессии, кэш, избранное, бюджет LLM)."""
"""One storage contract for the bot and HTTP application."""

import os

from .db import Database


def create_database():
    url = os.getenv("DATABASE_URL", "")
    if url:
        from .postgres import PostgresDatabase
        return PostgresDatabase(url)
    from config import DB_PATH
    return Database(DB_PATH)
