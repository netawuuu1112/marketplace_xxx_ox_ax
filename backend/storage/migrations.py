"""Additive migrations, serialized with application startup DDL."""
from pathlib import Path


async def migrate(conn):
    await conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())')
    for path in sorted((Path(__file__).resolve().parents[1] / 'migrations').glob('*.sql')):
        if not await conn.fetchval('SELECT 1 FROM schema_migrations WHERE name=$1', path.name):
            await conn.execute(path.read_text(encoding='utf-8'))
            await conn.execute('INSERT INTO schema_migrations(name) VALUES($1)', path.name)
