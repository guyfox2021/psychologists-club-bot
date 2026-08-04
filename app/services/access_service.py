import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


class AccessService:
    """Wraps the Telegram Bot API calls used to manage community chat access."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def create_invite_link(
        self, chat_id: int, name: str | None = None, member_limit: int = 1
    ) -> str:
        invite_link = await self._bot.create_chat_invite_link(
            chat_id=chat_id, name=name, member_limit=member_limit
        )
        return invite_link.invite_link

    async def revoke_invite_link(self, chat_id: int, invite_link: str) -> None:
        try:
            await self._bot.revoke_chat_invite_link(chat_id=chat_id, invite_link=invite_link)
        except TelegramBadRequest as error:
            logger.warning("Could not revoke invite link %s: %s", invite_link, error)

    async def kick_user(self, chat_id: int, telegram_id: int) -> None:
        """Remove a user from the community chat while allowing them to rejoin later."""
        try:
            await self._bot.ban_chat_member(chat_id=chat_id, user_id=telegram_id)
            await self._bot.unban_chat_member(
                chat_id=chat_id, user_id=telegram_id, only_if_banned=True
            )
            logger.info("Kicked user %s from chat %s", telegram_id, chat_id)
        except TelegramBadRequest as error:
            logger.warning("Could not kick user %s from chat %s: %s", telegram_id, chat_id, error)

    async def restore_access(self, chat_id: int, telegram_id: int, name: str | None = None) -> str:
        """Generate a fresh single-use invite link to let the user rejoin."""
        invite_link = await self.create_invite_link(chat_id, name=name, member_limit=1)
        logger.info("Restored access for user %s in chat %s", telegram_id, chat_id)
        return invite_link

    async def set_member_tag(self, chat_id: int, telegram_id: int, tag: str | None) -> None:
        """Set a member's visible tag/label (Bot API 9.5+, `can_manage_tags` right).

        Only applies to regular (non-admin, non-creator) members -- Telegram
        rejects it with CHAT_CREATOR_REQUIRED/similar for admins -- so this is
        best-effort and safe to call speculatively without pre-checking status.
        """
        try:
            await self._bot.set_chat_member_tag(chat_id=chat_id, user_id=telegram_id, tag=tag)
        except TelegramBadRequest as error:
            logger.warning(
                "Could not set tag for user %s in chat %s: %s", telegram_id, chat_id, error
            )
