"""Read-only probe of the price-alert worker's Telegram transport."""

import asyncio

import aiohttp

import config
from telegram_transport import build_notification_connector


async def main() -> None:
    async with aiohttp.ClientSession(connector=build_notification_connector()) as session:
        async with session.get(
            f"https://api.telegram.org/bot{config.BOT_TOKEN}/getMe",
            timeout=aiohttp.ClientTimeout(total=25),
        ) as response:
            payload = await response.json()
            print(f"worker_transport_ok={response.status == 200 and payload.get('ok') is True}")


asyncio.run(main())
