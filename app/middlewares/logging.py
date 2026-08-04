import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Logs a one-line summary of every incoming Telegram update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            user = data.get("event_from_user")
            logger.info(
                "Update %s type=%s from telegram_id=%s",
                event.update_id,
                event.event_type,
                user.id if user else None,
            )
        return await handler(event, data)
