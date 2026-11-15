"""Dedicated monitoring worker. Run exactly once per deployment."""
import asyncio
import logging

import config
from monitoring import run_worker
from storage import create_database
from storage.postgres import PostgresDatabase


async def main() -> None:
    db = create_database()
    if not isinstance(db, PostgresDatabase):
        raise SystemExit("Monitoring requires DATABASE_URL for PostgreSQL")
    await db.connect()
    try:
        await run_worker(db, config.BOT_TOKEN)
    finally:
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
