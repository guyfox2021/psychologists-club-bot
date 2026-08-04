import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import UserRepository

logger = logging.getLogger(__name__)

_SEND_DELAY_SECONDS = 0.05  # keeps us comfortably under Telegram's ~30 msg/sec global limit


class BroadcastService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self._user_repo = UserRepository(session)
        self._bot = bot

    async def send_to_role(self, role_code: str | None, text: str) -> tuple[int, int]:
        """Send `text` to every non-banned user with the given role (None = everyone).

        Returns (sent_count, failed_count).
        """
        telegram_ids = await self._user_repo.list_telegram_ids_by_role(role_code)
        sent = 0
        failed = 0

        for telegram_id in telegram_ids:
            try:
                await self._bot.send_message(telegram_id, text)
                sent += 1
            except TelegramRetryAfter as error:
                await asyncio.sleep(error.retry_after)
                try:
                    await self._bot.send_message(telegram_id, text)
                    sent += 1
                except (TelegramForbiddenError, TelegramBadRequest):
                    failed += 1
            except (TelegramForbiddenError, TelegramBadRequest) as error:
                logger.warning("Broadcast to %s failed: %s", telegram_id, error)
                failed += 1
            await asyncio.sleep(_SEND_DELAY_SECONDS)

        return sent, failed
