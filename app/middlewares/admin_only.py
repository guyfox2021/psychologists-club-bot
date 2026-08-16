from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.services.user_service import UserService


class AdminOnlyMiddleware(BaseMiddleware):
    """Gates a router to admins only. Mount on admin-only routers, not globally."""

    def __init__(self, super_admin_ids: list[int]) -> None:
        self._super_admin_ids = super_admin_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = data.get("event_from_user")
        if telegram_user is None:
            return None

        user_service = UserService(data["session"])
        if not await user_service.is_admin(telegram_user.id, self._super_admin_ids):
            if isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ заборонено.", show_alert=True)
            elif isinstance(event, Message) and event.chat.type == "private":
                # Only reply in DM -- a public "access denied" for an admin
                # command someone typed in the group chat is just clutter and
                # confusion for everyone else there, not useful to anyone.
                await event.answer("⛔ У вас немає доступу до цієї команди.")
            return None

        return await handler(event, data)
