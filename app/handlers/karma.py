import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message, MessageReactionUpdated, ReactionTypeEmoji

from app.config import Settings
from app.database.models import MessageFeedback
from app.database.models.enums import KarmaReactionType
from app.database.repositories import SettingsRepository, UserRepository
from app.services.access_service import AccessService
from app.services.karma_service import KarmaService, build_member_tag
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = Router(name="karma")

_HELPED_EMOJI = "🤝"
_NOT_HELPED_EMOJI = "👎"
_EMOJI_TO_REACTION = {
    _HELPED_EMOJI: KarmaReactionType.HELPED,
    _NOT_HELPED_EMOJI: KarmaReactionType.NOT_HELPED,
}


def _tracked_reaction(reactions: list) -> KarmaReactionType | None:
    """Reduce a Telegram reaction list down to our one tracked 🤝/👎 reaction.

    Any other emoji/custom/paid reaction is ignored entirely, per spec --
    the group's reaction picker is restricted to just these two anyway.
    """
    for reaction in reactions:
        if isinstance(reaction, ReactionTypeEmoji) and reaction.emoji in _EMOJI_TO_REACTION:
            return _EMOJI_TO_REACTION[reaction.emoji]
    return None


def _message_link(chat_id: int, message_id: int) -> str | None:
    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100"):
        return f"https://t.me/c/{chat_id_str[4:]}/{message_id}"
    return None


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def on_group_message(message: Message, session, settings: Settings) -> None:
    """Track messages from eligible authors so later reactions can be attributed
    to them -- the Bot API has no way to look up a message's author after the
    fact, so this has to happen at send time, not at first-reaction time."""
    if message.from_user is None or message.from_user.is_bot:
        return

    settings_repo = SettingsRepository(session)
    bot_settings = await settings_repo.get_or_create()
    if bot_settings.community_chat_id != message.chat.id:
        return

    user_service = UserService(session)
    author = await user_service.get_by_telegram_id(message.from_user.id)

    karma_service = KarmaService(session)
    if not await karma_service.is_eligible_author(author):
        return

    await karma_service.ensure_message_tracked(message.chat.id, message.message_id, author.id)


@router.message_reaction()
async def on_message_reaction(
    event: MessageReactionUpdated, session, bot: Bot, settings: Settings
) -> None:
    if event.user is None or event.user.is_bot:
        return  # anonymous/actor_chat reactions can't be attributed to a verified voter

    settings_repo = SettingsRepository(session)
    bot_settings = await settings_repo.get_or_create()
    if bot_settings.community_chat_id != event.chat.id:
        return

    old_reaction = _tracked_reaction(event.old_reaction)
    new_reaction = _tracked_reaction(event.new_reaction)
    if old_reaction == new_reaction:
        return

    karma_service = KarmaService(session)
    message_feedback = await karma_service.get_message_feedback(event.chat.id, event.message_id)
    if message_feedback is None:
        return  # not authored by an eligible (verified Psychologist/Supervisor) user

    user_repo = UserRepository(session)
    voter = await user_repo.get_by_telegram_id(event.user.id)
    if not await karma_service.is_verified(voter):
        return
    if voter.id == message_feedback.author_user_id:
        return  # no self-voting

    result = await karma_service.apply_reaction_change(
        chat_id=event.chat.id,
        message_id=event.message_id,
        author_user_id=message_feedback.author_user_id,
        voter_user_id=voter.id,
        old_reaction=old_reaction,
        new_reaction=new_reaction,
    )

    if result.karma_changed:
        await _refresh_author_tag(
            bot, session, bot_settings.community_chat_id, message_feedback.author_user_id, result.karma_points
        )

    if result.crossed_threshold:
        await _notify_admins_negative_feedback(bot, session, settings, event, message_feedback)


async def _refresh_author_tag(
    bot: Bot, session, chat_id: int, author_user_id: int, karma_points: int | None
) -> None:
    user_repo = UserRepository(session)
    author = await user_repo.get_by_id(author_user_id)
    if author is None or author.role is None or karma_points is None:
        return

    access_service = AccessService(bot)
    await access_service.set_member_tag(
        chat_id, author.telegram_id, build_member_tag(author.role.label_uk, karma_points)
    )


async def _notify_admins_negative_feedback(
    bot: Bot,
    session,
    settings: Settings,
    event: MessageReactionUpdated,
    message_feedback: MessageFeedback,
) -> None:
    user_repo = UserRepository(session)
    author = await user_repo.get_by_id(message_feedback.author_user_id)
    if author is None:
        return

    author_name = f"{author.first_name or ''} {author.last_name or ''}".strip() or "—"
    link = _message_link(event.chat.id, event.message_id)
    link_line = f"\n🔗 {link}" if link else ""

    text = (
        "⚠️ <b>Повідомлення отримало багато негативних оцінок</b>\n\n"
        f"👤 Автор: {author_name} (@{author.username or '—'}, id={author.telegram_id})\n"
        f"👎 Негативних оцінок: {message_feedback.negative_count}"
        f"{link_line}\n\n"
        "Текст повідомлення — нижче (переслано)."
    )

    user_service = UserService(session)
    admin_ids = await user_service.list_all_admin_telegram_ids(settings.super_admin_id_list)

    for admin_id in admin_ids:
        try:
            await bot.forward_message(
                admin_id, from_chat_id=event.chat.id, message_id=event.message_id
            )
            await bot.send_message(admin_id, text)
        except (TelegramForbiddenError, TelegramBadRequest) as error:
            logger.warning(
                "Could not notify admin %s about negative feedback: %s", admin_id, error
            )
