import logging

from aiogram import Bot, Router
from aiogram.filters import JOIN_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated

from app.database.repositories import SettingsRepository
from app.services.access_service import AccessService
from app.services.karma_service import KarmaService, build_member_tag
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = Router(name="chat_member")


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
    tag = build_member_tag(user.role.label_uk, karma_points)

    access_service = AccessService(bot)
    await access_service.set_member_tag(event.chat.id, user.telegram_id, tag)
    logger.info("Tagged user %s as %r in chat %s", user.telegram_id, tag, event.chat.id)
