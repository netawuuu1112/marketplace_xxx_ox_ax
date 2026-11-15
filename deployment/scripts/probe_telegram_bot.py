"""Read-only Bot API connectivity probe; prints no token or proxy credentials."""

import asyncio

import config
from telegram_transport import build_bot


async def main() -> None:
    bot = build_bot(config.BOT_TOKEN)
    try:
        me = await asyncio.wait_for(bot.get_me(), timeout=25)
        print(f"bot_get_me_ok={bool(me.id)} username={me.username}")
    finally:
        await bot.session.close()


asyncio.run(main())
