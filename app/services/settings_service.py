import logging
from decimal import Decimal

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import BotSettings
from app.database.repositories import SettingsRepository

logger = logging.getLogger(__name__)

_ADMIN_STATUSES = {"administrator", "creator"}


class ChannelValidationError(Exception):
    """Raised when a chat cannot be adopted as the tracked community channel."""


class SettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = SettingsRepository(session)

    async def get_settings(self) -> BotSettings:
        return await self._repo.get_or_create()

    async def update_trial_days(self, days: int) -> BotSettings:
        return await self._repo.update(trial_days=days)

    async def update_subscription_price(self, price: Decimal) -> BotSettings:
        return await self._repo.update(subscription_price=price)

    async def update_subscription_duration(self, days: int) -> BotSettings:
        return await self._repo.update(subscription_duration_days=days)

    async def update_reminder_days(self, days_before: list[int]) -> BotSettings:
        return await self._repo.update(reminder_days_before=sorted(days_before, reverse=True))

    async def change_community_channel(self, bot: Bot, channel_input: str) -> BotSettings:
        channel_input = channel_input.strip()

        try:
            chat = await bot.get_chat(channel_input)
        except TelegramBadRequest as error:
            raise ChannelValidationError(
                "Не вдалося знайти канал. Перевірте посилання/username або ID."
            ) from error

        bot_user = await bot.me()
        try:
            member = await bot.get_chat_member(chat.id, bot_user.id)
        except TelegramBadRequest as error:
            raise ChannelValidationError("Бот не є учасником цього каналу.") from error

        if member.status not in _ADMIN_STATUSES:
            raise ChannelValidationError(
                "Бот повинен бути адміністратором каналу зі створення інвайт-посилань."
            )

        logger.info("Community channel changed to %s (%s)", chat.id, chat.title)
        return await self._repo.update(community_chat_id=chat.id)
