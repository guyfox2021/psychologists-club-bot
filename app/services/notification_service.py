import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Notification
from app.database.models.enums import NotificationStatus, NotificationType
from app.database.repositories import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends a Telegram message to a user and records the delivery outcome."""

    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self._repo = NotificationRepository(session)
        self._bot = bot

    async def send(
        self,
        user_id: int,
        user_telegram_id: int,
        notification_type: NotificationType,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Notification:
        status = NotificationStatus.SENT
        try:
            await self._bot.send_message(user_telegram_id, text, reply_markup=reply_markup)
        except TelegramForbiddenError:
            logger.warning("User %s has blocked the bot, notification not delivered", user_telegram_id)
            status = NotificationStatus.FAILED
        except TelegramBadRequest:
            logger.exception("Telegram rejected notification to %s", user_telegram_id)
            status = NotificationStatus.FAILED

        return await self._repo.add(user_id, notification_type, text, status)

    async def list_for_user(self, user_id: int, limit: int = 20) -> list[Notification]:
        return await self._repo.list_by_user(user_id, limit)
