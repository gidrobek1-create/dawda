import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot.config import config
from bot.database import Database
from bot.handlers import (
    admin_panel as admin_panel_handlers,
    admin_payments as admin_payments_handlers,
    balance as balance_handlers,
    common as common_handlers,
    promo as promo_handlers,
    referral as referral_handlers,
    start as start_handlers,
    topup as topup_handlers,
)
from bot.middlewares.db import DbMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def _setup(db: Database, dp: Dispatcher) -> None:
    await db.connect()
    await db.run_migrations()
    if config.super_admin_ids:
        await db.ensure_super_admins(config.super_admin_ids)

    dp.update.middleware(DbMiddleware(db))

    # Tartib muhim: /bekor va admin javob kutayotgan holatlar
    # asosiy menyu tugmalaridan OLDIN tekshirilishi kerak.
    dp.include_router(common_handlers.router)
    dp.include_router(admin_payments_handlers.router)
    dp.include_router(admin_panel_handlers.router)
    dp.include_router(topup_handlers.router)
    dp.include_router(start_handlers.router)
    dp.include_router(balance_handlers.router)
    dp.include_router(promo_handlers.router)
    dp.include_router(referral_handlers.router)


async def run_polling() -> None:
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    db = Database(config.database_url)

    await _setup(db, dp)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot polling rejimida ishga tushdi")
        await dp.start_polling(bot)
    finally:
        await db.close()


async def run_webhook() -> None:
    """Render kabi platformalarda ishlatiladi: aiohttp server portni tinglaydi,
    Telegram esa yangilanishlarni webhook orqali shu portga yuboradi."""
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    db = Database(config.database_url)

    await _setup(db, dp)

    await bot.set_webhook(
        url=config.webhook_url,
        drop_pending_updates=True,
        secret_token=config.webhook_secret,
    )
    logger.info("Webhook o'rnatildi: %s", config.webhook_url)

    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config.webhook_secret,
    ).register(app, path=config.webhook_path)

    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=config.port)
    await site.start()
    logger.info("Webhook server %s portida ishga tushdi", config.port)

    try:
        await asyncio.Event().wait()  # abadiy ishlab turadi
    finally:
        await bot.delete_webhook()
        await db.close()
        await runner.cleanup()


def main() -> None:
    config.validate()
    if config.webhook_mode:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
