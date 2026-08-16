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
            # Temporary deep diagnostic: dump the full raw payload for any
            # group message without plain text (service messages -- joins,
            # leaves, pins, etc. -- typically have no .text) and for every
            # chat_member update, so we can see exactly what Telegram sends
            # for a real join without guessing from the typed model alone.
            if (
                event.message is not None
                and event.message.chat.type in {"group", "supergroup"}
                and event.message.text is None
            ):
                logger.info(
                    "RAW service-like group message: %s",
                    event.message.model_dump_json(exclude_none=True),
                )
            if event.chat_member is not None:
                logger.info(
                    "RAW chat_member update: %s",
                    event.chat_member.model_dump_json(exclude_none=True),
                )
        return await handler(event, data)
