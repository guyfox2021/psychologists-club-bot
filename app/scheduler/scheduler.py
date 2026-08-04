import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Settings
from app.scheduler.jobs import run_daily_maintenance

logger = logging.getLogger(__name__)

_JOB_ID = "daily_subscription_maintenance"
_RUN_HOUR = 4
_RUN_MINUTE = 0


class BotScheduler:
    """Owns the APScheduler instance that drives trial/subscription maintenance."""

    def __init__(self, bot: Bot, settings: Settings) -> None:
        self._bot = bot
        self._settings = settings
        self._scheduler = AsyncIOScheduler(timezone=settings.timezone)

    def start(self) -> None:
        self._scheduler.add_job(
            self._run,
            trigger="cron",
            hour=_RUN_HOUR,
            minute=_RUN_MINUTE,
            id=_JOB_ID,
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Subscription scheduler started (daily at %02d:%02d)", _RUN_HOUR, _RUN_MINUTE)

    async def _run(self) -> None:
        logger.info("Running daily subscription maintenance job")
        try:
            await run_daily_maintenance(self._bot, self._settings)
        except Exception:
            logger.exception("Daily subscription maintenance job failed")

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
