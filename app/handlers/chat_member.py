import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import JOIN_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated, Message

from app.database.repositories import SettingsRepository
from app.services.access_service import AccessService
from app.services.karma_service import KarmaService, build_member_tag
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = Router(name="chat_member")


@router.message(F.new_chat_members)
async def on_join_service_message(message: Message, session, bot: Bot) -> None:
    """Delete the "X joined via invite link" service message to reduce clutter.

    Best-effort: requires the bot to have `can_delete_messages`. Silently logs
    and moves on if deletion fails (e.g. right not granted, or the message was
    already deleted by someone else) rather than raising.
    """
    logger.info(
        "on_join_service_message fired: chat=%s message_id=%s new_chat_members=%s",
        message.chat.id,
        message.message_id,
        [u.id for u in message.new_chat_members] if message.new_chat_members else None,
    )
    settings_repo = SettingsRepository(session)
    bot_settings = await settings_repo.get_or_create()
    if bot_settings.community_chat_id != message.chat.id:
        logger.info(
            "on_join_service_message: chat %s does not match configured community_chat_id %s",
            message.chat.id,
            bot_settings.community_chat_id,
        )
        return

    try:
        await bot.delete_message(message.chat.id, message.message_id)
        logger.info("Deleted join service message %s in chat %s", message.message_id, message.chat.id)
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        logger.warning(
            "Could not delete join service message %s in chat %s: %s",
            message.message_id,
            message.chat.id,
            error,
        )


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_member_joined(event: ChatMemberUpdated, session, bot: Bot) -> None:
    """Tag a newly joined member with their role and current karma.

    Tagging only works for regular members once they've actually joined --
    admins/the creator are rejected by the API, and there's no reliable way to
    tag someone before they're a member -- so this runs on the join event
    itself rather than at invite-link-generation time.
    """
    settings_repo = SettingsRepository(session)
    bot_settings = await settings_repo.get_or_create()
    if bot_settings.community_chat_id != event.chat.id:
        return

    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(event.new_chat_member.user.id)
    if user is None or user.role is None:
        return

    karma_service = KarmaService(session)
    karma_points = await karma_service.get_karma_points(user.id)
    tag = build_member_tag(user.role.code, user.role.label_uk, karma_points)

    access_service = AccessService(bot)
    await access_service.set_member_tag(event.chat.id, user.telegram_id, tag)
    logger.info("Tagged user %s as %r in chat %s", user.telegram_id, tag, event.chat.id)
