"""Integration check for concurrent service startup against an empty PostgreSQL database."""

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from storage.postgres import PostgresDatabase


def test_concurrent_initializers_create_schema_once():
    base_url = os.getenv("MARKETFUSION_TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("set MARKETFUSION_TEST_DATABASE_URL to run PostgreSQL integration test")

    async def check():
        admin = await asyncpg.connect(base_url)
        database_name = "marketfusion_test_" + uuid4().hex
        parts = urlsplit(base_url)
        test_url = urlunsplit(parts._replace(path="/" + database_name))
        await admin.execute(f'CREATE DATABASE "{database_name}"')
        try:
            start = asyncio.Event()

            async def connect_once():
                db = PostgresDatabase(test_url)
                await start.wait()
                try:
                    await db.connect()
                finally:
                    await db.close()

            tasks = [asyncio.create_task(connect_once()) for _ in range(8)]
            start.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            assert results == [None] * len(tasks)

            probe = await asyncpg.connect(test_url)
            try:
                assert await probe.fetchval("SELECT to_regclass('public.users')") == "users"
                assert await probe.fetchval("SELECT to_regclass('public.watchlists')") == "watchlists"
            finally:
                await probe.close()
        finally:
            await admin.execute(f'DROP DATABASE "{database_name}" WITH (FORCE)')
            await admin.close()

    asyncio.run(check())
