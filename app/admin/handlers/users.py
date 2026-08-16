import logging
from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.admin.callback_data import AdminChangeRoleCB, UserAdminCB
from app.admin.keyboards import role_change_keyboard, user_actions_keyboard
from app.config import Settings
from app.database.models import User
from app.database.models.enums import SubscriptionStatus, UserRoleCode
from app.database.repositories import RoleRepository, SettingsRepository, SubscriptionRepository
from app.services.access_service import AccessService
from app.services.admin_log_service import AdminLogService
from app.services.karma_service import KarmaService, build_member_tag
from app.services.user_service import UserService
from app.utils.datetime_utils import format_datetime_human

logger = logging.getLogger(__name__)

users_router = Router(name="admin_users")


def _format_user_card(user: User, timezone_name: str) -> str:
    role_label = user.role.label_uk if user.role else "—"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "—"
    return (
        f"👤 <b>{full_name}</b>\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Username: @{user.username or '—'}\n"
        f"🎓 Роль: {role_label}\n"
        f"📞 {user.phone or '—'}   ✉️ {user.email or '—'}   🏙 {user.city or '—'}\n"
        f"👑 Адмін: {'так' if user.is_admin else 'ні'}\n"
        f"🚫 Забанений: {'так' if user.is_banned else 'ні'}\n"
        f"📅 Реєстрація: {format_datetime_human(user.created_at, timezone_name)}"
    )


@users_router.message(Command("users"))
async def on_users_list(message: Message, session, settings: Settings) -> None:
    user_service = UserService(session)
    users = await user_service.list_recent(limit=20)
    if not users:
        await message.answer("Користувачів ще немає.")
        return

    lines = ["👥 <b>Останні користувачі</b>", ""]
    for user in users:
        role_label = user.role.label_uk if user.role else "—"
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "—"
        lines.append(f"• <code>{user.telegram_id}</code> — {full_name} ({role_label})")
    lines.append("")
    lines.append("Використайте /search <telegram_id> для деталей та дій.")
    await message.answer("\n".join(lines))


@users_router.message(Command("search"))
async def on_user_search(
    message: Message, command: CommandObject, session, settings: Settings
) -> None:
    if not command.args:
        await message.answer("Використання: /search <telegram_id>")
        return
    try:
        telegram_id = int(command.args.strip())
    except ValueError:
        await message.answer("Telegram ID має бути числом.")
        return

    user_service = UserService(session)
    user = await user_service.search_by_telegram_id(telegram_id)
    if user is None:
        await message.answer("Користувача не знайдено.")
        return

    await message.answer(
        _format_user_card(user, settings.timezone), reply_markup=user_actions_keyboard(user)
    )


async def _refresh_user_card(callback: CallbackQuery, session, settings: Settings, user_id: int) -> None:
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if user is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return
    await callback.message.edit_text(
        _format_user_card(user, settings.timezone), reply_markup=user_actions_keyboard(user)
    )


@users_router.callback_query(UserAdminCB.filter(F.action == "ban"))
async def on_ban_user(
    callback: CallbackQuery, callback_data: UserAdminCB, session, settings: Settings
) -> None:
    user_service = UserService(session)
    await user_service.ban_user(callback_data.user_id)
    await AdminLogService(session).log(
        callback.from_user.id, "ban_user", target_user_id=callback_data.user_id
    )
    await _refresh_user_card(callback, session, settings, callback_data.user_id)
    await callback.answer("Користувача забанено")


@users_router.callback_query(UserAdminCB.filter(F.action == "unban"))
async def on_unban_user(
    callback: CallbackQuery, callback_data: UserAdminCB, session, settings: Settings
) -> None:
    user_service = UserService(session)
    await user_service.unban_user(callback_data.user_id)
    await AdminLogService(session).log(
        callback.from_user.id, "unban_user", target_user_id=callback_data.user_id
    )
    await _refresh_user_card(callback, session, settings, callback_data.user_id)
    await callback.answer("Користувача розбанено")


@users_router.callback_query(UserAdminCB.filter(F.action == "make_admin"))
async def on_make_admin(
    callback: CallbackQuery, callback_data: UserAdminCB, session, settings: Settings
) -> None:
    user_service = UserService(session)
    user = await user_service.get_by_id(callback_data.user_id)
    if user is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return
    await user_service.set_admin(user.telegram_id, True)
    await AdminLogService(session).log(
        callback.from_user.id, "make_admin", target_user_id=callback_data.user_id
    )
    await _refresh_user_card(callback, session, settings, callback_data.user_id)
    await callback.answer("Права адміністратора надано")


@users_router.callback_query(UserAdminCB.filter(F.action == "remove_admin"))
async def on_remove_admin(
    callback: CallbackQuery, callback_data: UserAdminCB, session, settings: Settings
) -> None:
    user_service = UserService(session)
    user = await user_service.get_by_id(callback_data.user_id)
    if user is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return
    await user_service.set_admin(user.telegram_id, False)
    await AdminLogService(session).log(
        callback.from_user.id, "remove_admin", target_user_id=callback_data.user_id
    )
    await _refresh_user_card(callback, session, settings, callback_data.user_id)
    await callback.answer("Права адміністратора знято")


@users_router.callback_query(UserAdminCB.filter(F.action == "change_role"))
async def on_change_role_start(
    callback: CallbackQuery, callback_data: UserAdminCB, session
) -> None:
    role_repo = RoleRepository(session)
    roles = await role_repo.list_all()
    await callback.message.edit_text(
        "🎓 Оберіть нову роль:", reply_markup=role_change_keyboard(callback_data.user_id, roles)
    )
    await callback.answer()


async def _grant_permanent_supervisor_access(session, bot: Bot, user: User) -> str | None:
    """Give a user promoted to Supervisor free, permanent community access.

    Mirrors the auto-grant that happens on application approval (see
    app/admin/handlers/applications.py) for users whose role changes to
    Supervisor *after* the fact via /search -> "Змінити роль". Returns the
    invite link if access was (re)granted, or None if nothing needed to change.
    """
    settings_repo = SettingsRepository(session)
    bot_settings = await settings_repo.get_or_create()
    if bot_settings.community_chat_id is None:
        logger.warning(
            "Community channel is not configured, cannot grant supervisor access to user %s",
            user.id,
        )
        return None

    subscription_repo = SubscriptionRepository(session)
    subscription = await subscription_repo.get_or_create(user.id)
    if subscription.status == SubscriptionStatus.ACTIVE and subscription.subscription_end is None:
        return None  # already has permanent access, nothing to do

    access_service = AccessService(bot)
    invite_link = await access_service.create_invite_link(
        bot_settings.community_chat_id, name=f"user_{user.telegram_id}", member_limit=1
    )
    await subscription_repo.update(
        user.id,
        status=SubscriptionStatus.ACTIVE,
        subscription_start=datetime.now(UTC),
        subscription_end=None,
        invite_link=invite_link,
    )

    try:
        await bot.send_message(
            user.telegram_id,
            "🎉 Вашу роль змінено на Супервізора — ви отримали постійний безкоштовний доступ "
            "до спільноти, без оплати.\n\n"
            f"🔗 Посилання для вступу: {invite_link}",
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning("Could not notify user %s about their new supervisor access", user.id)

    return invite_link


@users_router.callback_query(AdminChangeRoleCB.filter())
async def on_change_role_apply(
    callback: CallbackQuery, callback_data: AdminChangeRoleCB, session, settings: Settings, bot: Bot
) -> None:
    role_repo = RoleRepository(session)
    role = await role_repo.get_by_code(callback_data.role_code)
    if role is None:
        await callback.answer("Роль не знайдено.", show_alert=True)
        return

    user_service = UserService(session)
    user = await user_service.get_by_id(callback_data.user_id)
    if user is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    await user_service.change_role(callback_data.user_id, role.id)
    await AdminLogService(session).log(
        callback.from_user.id,
        "change_role",
        target_user_id=callback_data.user_id,
        details={"role_code": callback_data.role_code},
    )

    # Re-tag if they're already a member of the community chat -- harmless no-op
    # (logged, not raised) if they haven't joined yet or aren't a plain member.
    settings_repo = SettingsRepository(session)
    bot_settings = await settings_repo.get_or_create()
    if bot_settings.community_chat_id is not None:
        karma_service = KarmaService(session)
        karma_points = await karma_service.get_karma_points(user.id)
        access_service = AccessService(bot)
        await access_service.set_member_tag(
            bot_settings.community_chat_id,
            user.telegram_id,
            build_member_tag(role.code, role.label_uk, karma_points),
        )

    answer_text = "Роль оновлено"
    if callback_data.role_code == UserRoleCode.SUPERVISOR.value:
        granted = await _grant_permanent_supervisor_access(session, bot, user)
        if granted:
            answer_text = "Роль оновлено, безкоштовний доступ надано"

    await _refresh_user_card(callback, session, settings, callback_data.user_id)
    await callback.answer(answer_text)
