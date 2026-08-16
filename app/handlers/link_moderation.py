import asyncio
import logging
import re

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message, MessageEntity

from app.database.repositories import SettingsRepository

logger = logging.getLogger(__name__)

router = Router(name="link_moderation")

_EXEMPT_STATUSES = {"creator", "administrator"}
_LINKLIKE_ENTITY_TYPES = {"url", "text_link", "mention"}
_WARNING_TEXT = "Посилання в цій спільноті можуть публікувати лише адміністратори."
_WARNING_AUTO_DELETE_SECONDS = 8

# Backup pass for links Telegram's own entity parser might miss (unusual
# formatting, quoted/forwarded text, etc). Entities are the primary,
# authoritative signal -- this regex only runs when no linklike entity was
# already found.
_DOMAIN_REGEX = re.compile(
    r"(?:https?://|www\.)\S+"
    r"|(?:t\.me|telegram\.me)/\S+"
    r"|\b[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\."
    r"(?:com|net|org|io|me|ua|ru|info|biz|co|tv|app|link|xyz|club|site|online|shop|store|pro|dev|gg)\b"
    r"(?:/\S*)?",
    re.IGNORECASE,
)


def _extract_entity_text(text: str, entity: MessageEntity) -> str:
    return text[entity.offset : entity.offset + entity.length]


def _find_link(message: Message) -> str | None:
    """Best-effort link detection across text/caption + their entities.

    Entities (parsed server-side by Telegram) are checked first and are the
    reliable signal for url/text_link/mention -- this covers http(s)://,
    www., bare domains like example.com, t.me/..., telegram.me/..., invite
    links, and @mentions of external Telegram resources, regardless of which
    message field (text vs caption on photo/video/document/etc) they're in.
    The regex fallback only matters for the rare case Telegram's own parser
    misses something.
    """
    text = message.text or message.caption
    entities = message.entities or message.caption_entities
    if entities and text:
        for entity in entities:
            if entity.type == "text_link" and entity.url:
                return entity.url
            if entity.type in _LINKLIKE_ENTITY_TYPES:
                return _extract_entity_text(text, entity)
    if text:
        match = _DOMAIN_REGEX.search(text)
        if match:
            return match.group(0)
    return None


async def _cleanup_warning(bot: Bot, chat_id: int, message_id: int) -> None:
    await asyncio.sleep(_WARNING_AUTO_DELETE_SECONDS)
    try:
        await bot.delete_message(chat_id, message_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass  # already gone (manually deleted, chat cleared, etc) -- fine either way


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def on_group_message_check_links(message: Message, session, bot: Bot) -> None:
    """Delete link/mention-of-external-resource messages from non-admin members.

    Explicitly defers to the rest of the router chain (karma tracking, etc.)
    via SkipHandler whenever this message isn't something to moderate -- this
    handler never "owns" a message unless it actually deletes it.
    """
    if message.from_user is None or message.from_user.is_bot:
        raise SkipHandler

    settings_repo = SettingsRepository(session)
    bot_settings = await settings_repo.get_or_create()
    if bot_settings.community_chat_id != message.chat.id:
        raise SkipHandler

    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        logger.warning(
            "Could not check chat member status for user %s in chat %s: %s",
            message.from_user.id,
            message.chat.id,
            error,
        )
        raise SkipHandler from None

    if member.status in _EXEMPT_STATUSES:
        raise SkipHandler

    detected_link = _find_link(message)
    if detected_link is None:
        raise SkipHandler

    try:
        await bot.delete_message(message.chat.id, message.message_id)
    except TelegramForbiddenError as error:
        logger.error(
            "Cannot delete link message %s in chat %s -- bot is missing "
            "can_delete_messages rights: %s",
            message.message_id,
            message.chat.id,
            error,
        )
        raise SkipHandler from None
    except TelegramBadRequest as error:
        logger.warning(
            "Could not delete link message %s in chat %s: %s",
            message.message_id,
            message.chat.id,
            error,
        )
        raise SkipHandler from None

    logger.warning(
        "LINK_BLOCKED | %s | %s | %s | %s",
        message.from_user.id,
        message.from_user.username or "-",
        detected_link,
        message.message_id,
    )

    try:
        warning = await bot.send_message(message.chat.id, _WARNING_TEXT)
        asyncio.create_task(_cleanup_warning(bot, message.chat.id, warning.message_id))
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        logger.warning(
            "Could not send link-warning message in chat %s: %s", message.chat.id, error
        )
