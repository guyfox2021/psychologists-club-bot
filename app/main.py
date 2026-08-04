import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis

from app.admin.router import admin_router
from app.config import Settings, get_settings
from app.database.engine import dispose_engine, init_engine
from app.handlers.router import user_router
from app.middlewares.admin_only import AdminOnlyMiddleware
from app.middlewares.database import DatabaseMiddleware
from app.middlewares.logging import LoggingMiddleware
from app.middlewares.throttling import ThrottlingMiddleware
from app.payments.webhook_handler import monobank_webhook_handler
from app.scheduler.scheduler import BotScheduler
from app.utils.logger import setup_logging

logger = logging.getLogger(__name__)


def _build_dispatcher(settings: Settings, redis_client: Redis) -> Dispatcher:
    storage = RedisStorage(redis_client)
    dispatcher = Dispatcher(storage=storage, settings=settings)

    # Outer middlewares wrap every update, before routing/filters are checked,
    # so `session` is already in `data` by the time any router's own
    # middlewares (e.g. AdminOnlyMiddleware) run.
    dispatcher.update.outer_middleware(ThrottlingMiddleware(redis_client))
    dispatcher.update.outer_middleware(DatabaseMiddleware())
    dispatcher.update.outer_middleware(LoggingMiddleware())

    admin_only = AdminOnlyMiddleware(settings.super_admin_id_list)
    admin_router.message.middleware(admin_only)
    admin_router.callback_query.middleware(admin_only)

    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)
    return dispatcher


def _build_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def _run_webhook_mode(
    bot: Bot, dispatcher: Dispatcher, settings: Settings, scheduler: BotScheduler
) -> None:
    app = web.Application()
    app["bot"] = bot
    app["settings"] = settings

    SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=settings.webhook_secret_token or None,
    ).register(app, path=settings.webhook_telegram_path)
    app.router.add_post(settings.webhook_monobank_path, monobank_webhook_handler)
    setup_application(app, dispatcher, bot=bot)

    await bot.set_webhook(
        settings.telegram_webhook_url,
        secret_token=settings.webhook_secret_token or None,
        drop_pending_updates=True,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )
    scheduler.start()

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.web_server_host, settings.web_server_port)
    await site.start()
    logger.info(
        "Webhook server listening on %s:%s (Telegram webhook: %s, Monobank webhook: %s)",
        settings.web_server_host,
        settings.web_server_port,
        settings.webhook_telegram_path,
        settings.webhook_monobank_path,
    )

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await runner.cleanup()


async def _run_polling_mode(
    bot: Bot, dispatcher: Dispatcher, settings: Settings, scheduler: BotScheduler
) -> None:
    await bot.delete_webhook(drop_pending_updates=True)

    app = web.Application()
    app["bot"] = bot
    app["settings"] = settings
    app.router.add_post(settings.webhook_monobank_path, monobank_webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.web_server_host, settings.web_server_port)
    await site.start()
    logger.info(
        "Monobank webhook server listening on %s:%s (Telegram updates via long polling)",
        settings.web_server_host,
        settings.web_server_port,
    )

    scheduler.start()
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await runner.cleanup()


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    init_engine(settings)

    bot = _build_bot(settings)
    redis_client = Redis.from_url(settings.redis_url)
    dispatcher = _build_dispatcher(settings, redis_client)
    scheduler = BotScheduler(bot, settings)

    try:
        if settings.use_telegram_webhook:
            await _run_webhook_mode(bot, dispatcher, settings, scheduler)
        else:
            await _run_polling_mode(bot, dispatcher, settings, scheduler)
    finally:
        await bot.session.close()
        await redis_client.aclose()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
