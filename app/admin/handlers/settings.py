import asyncio
from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.admin.callback_data import RolePriceCB, SettingsAdminCB
from app.admin.keyboards import role_price_select_keyboard, settings_menu_keyboard
from app.config import Settings
from app.database.models import BotSettings, Role
from app.database.repositories import RoleRepository, UserRepository
from app.services.access_service import AccessService
from app.services.karma_service import KarmaService, build_member_tag
from app.services.settings_service import ChannelValidationError, SettingsService
from app.states.admin_states import SettingsStates

_TAG_SYNC_DELAY_SECONDS = 1.0  # SetChatMemberTag has a tight per-chat rate limit

settings_router = Router(name="admin_settings")


def _format_settings(
    bot_settings: BotSettings,
    roles: list[Role] | None = None,
    payment_required: bool | None = None,
) -> str:
    reminders = ", ".join(str(day) for day in bot_settings.reminder_days_before) or "—"
    channel = str(bot_settings.community_chat_id) if bot_settings.community_chat_id else "не налаштовано"
    price_section = ""
    if roles is not None:
        role_price_lines = "\n".join(
            f"  • {role.label_uk}: <b>{role.price_uah} {bot_settings.subscription_currency}</b>"
            if role.price_uah is not None
            else f"  • {role.label_uk}: безкоштовно"
            for role in roles
        )
        price_section = f"💵 Ціни за роллю (списується одразу, без тріалу):\n{role_price_lines}\n"
    payment_section = ""
    if payment_required is not None:
        payment_state = "увімкнена" if payment_required else "вимкнена"
        payment_section = f"💳 Оплата: <b>{payment_state}</b> (PAYMENT_REQUIRED)\n"
    return (
        "⚙️ <b>Налаштування</b>\n\n"
        f"📅 Тріал: <b>{bot_settings.trial_days}</b> днів (не використовується — оплата без тріалу)\n"
        f"{payment_section}"
        f"{price_section}"
        f"📆 Тривалість підписки: <b>{bot_settings.subscription_duration_days}</b> днів\n"
        f"🔔 Нагадування за (днів до): <b>{reminders}</b>\n"
        f"📢 Канал спільноти: <b>{channel}</b>"
    )


@settings_router.message(Command("settings"))
async def on_settings_menu(message: Message, session, settings: Settings) -> None:
    settings_service = SettingsService(session)
    bot_settings = await settings_service.get_settings()
    role_repo = RoleRepository(session)
    roles = await role_repo.list_all()
    await message.answer(
        _format_settings(bot_settings, roles, settings.payment_required),
        reply_markup=settings_menu_keyboard(),
    )


@settings_router.message(Command("id"))
async def on_show_chat_id(message: Message) -> None:
    """Reveal the numeric chat ID -- handy for private groups/channels whose invite
    links Telegram's Bot API cannot resolve directly (only @username or a numeric ID
    work for get_chat). Send /id inside the target group/channel to read it off here."""
    await message.answer(f"🆔 Chat ID: <code>{message.chat.id}</code>")


@settings_router.message(Command("sync_tags"))
async def on_sync_tags(message: Message, session, bot: Bot) -> None:
    """Re-apply member tags for every user who has a role in our DB.

    Tags are normally only ever set reactively (on join, on a karma-changing
    reaction, on a manual role change in /search) -- there was never a way to
    backfill tags for members who joined before those code paths existed, or
    whose tag-set attempt silently failed (e.g. the USER_NOT_PARTICIPANT race
    on join) and was never retried. This command re-syncs everyone at once.
    """
    settings_service = SettingsService(session)
    bot_settings = await settings_service.get_settings()
    if bot_settings.community_chat_id is None:
        await message.answer("⚠️ Спільнота ще не підключена. Спочатку налаштуйте /settings.")
        return

    user_repo = UserRepository(session)
    users = await user_repo.list_with_role()
    if not users:
        await message.answer("У базі немає користувачів з призначеною роллю.")
        return

    await message.answer(f"🔄 Оновлюю теги для {len(users)} користувачів...")

    karma_service = KarmaService(session)
    access_service = AccessService(bot)
    tagged = 0
    skipped = 0
    for user in users:
        karma_points = await karma_service.get_karma_points(user.id)
        tag = build_member_tag(user.role.code, user.role.label_uk, karma_points)
        success = await access_service.set_member_tag(
            bot_settings.community_chat_id, user.telegram_id, tag
        )
        if success:
            tagged += 1
        else:
            skipped += 1
        await asyncio.sleep(_TAG_SYNC_DELAY_SECONDS)

    await message.answer(
        f"✅ Готово.\nОновлено тегів: {tagged}\n"
        f"Пропущено (не в групі, адмін/творець чату, або помилка): {skipped}"
    )


@settings_router.callback_query(SettingsAdminCB.filter(F.action == "trial_days"))
async def on_edit_trial_days(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.trial_days)
    await callback.message.edit_text("Введіть нову кількість днів тріалу (ціле число):")
    await callback.answer()


@settings_router.callback_query(SettingsAdminCB.filter(F.action == "price"))
async def on_edit_price(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.price)
    await callback.message.edit_text("Введіть нову ціну підписки, наприклад 500 або 499.99:")
    await callback.answer()


@settings_router.callback_query(SettingsAdminCB.filter(F.action == "role_prices"))
async def on_edit_role_prices(callback: CallbackQuery, session) -> None:
    role_repo = RoleRepository(session)
    roles = await role_repo.list_all()
    await callback.message.edit_text(
        "Оберіть роль, ціну якої хочете змінити:", reply_markup=role_price_select_keyboard(roles)
    )
    await callback.answer()


@settings_router.callback_query(RolePriceCB.filter())
async def on_role_price_select(
    callback: CallbackQuery, callback_data: RolePriceCB, state: FSMContext
) -> None:
    await state.set_state(SettingsStates.role_price)
    await state.update_data(role_id=callback_data.role_id)
    await callback.message.edit_text(
        "Введіть нову ціну для цієї ролі в грн (наприклад 225), або 0 щоб зробити роль безкоштовною:"
    )
    await callback.answer()


@settings_router.message(SettingsStates.role_price)
async def on_role_price_input(message: Message, state: FSMContext, session, settings: Settings) -> None:
    data = await state.get_data()
    role_id = data.get("role_id")
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price < 0:
            raise InvalidOperation
    except InvalidOperation:
        await message.answer("⚠️ Введіть невід'ємне число, наприклад 225 або 0.")
        return

    role_repo = RoleRepository(session)
    role = await role_repo.update_price(role_id, price if price > 0 else None)
    await state.clear()
    if role is None:
        await message.answer("Роль не знайдено.")
        return

    price_text = f"{role.price_uah} грн" if role.price_uah is not None else "безкоштовно"
    settings_service = SettingsService(session)
    bot_settings = await settings_service.get_settings()
    roles = await role_repo.list_all()
    await message.answer(
        f"✅ Ціну для ролі «{role.label_uk}» оновлено: {price_text}.\n\n"
        + _format_settings(bot_settings, roles, settings.payment_required)
    )


@settings_router.callback_query(SettingsAdminCB.filter(F.action == "duration"))
async def on_edit_duration(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.duration)
    await callback.message.edit_text("Введіть тривалість підписки у днях (ціле число):")
    await callback.answer()


@settings_router.callback_query(SettingsAdminCB.filter(F.action == "reminders"))
async def on_edit_reminders(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.reminders)
    await callback.message.edit_text(
        "Введіть дні нагадувань до завершення підписки через кому, наприклад: 3,1"
    )
    await callback.answer()


@settings_router.callback_query(SettingsAdminCB.filter(F.action == "channel"))
async def on_edit_channel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.channel)
    await callback.message.edit_text(
        "Надішліть username (@channel), ID (-100...) або запрошувальне посилання каналу спільноти.\n"
        "Бот вже має бути доданий туди адміністратором."
    )
    await callback.answer()


@settings_router.message(SettingsStates.trial_days)
async def on_trial_days_input(message: Message, state: FSMContext, session) -> None:
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть додатне ціле число.")
        return

    settings_service = SettingsService(session)
    bot_settings = await settings_service.update_trial_days(days)
    await state.clear()
    await message.answer(
        f"✅ Тріал оновлено: {days} днів.\n\n" + _format_settings(bot_settings),
        reply_markup=settings_menu_keyboard(),
    )


@settings_router.message(SettingsStates.price)
async def on_price_input(message: Message, state: FSMContext, session) -> None:
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer("⚠️ Введіть коректну суму, наприклад 500 або 499.99.")
        return

    settings_service = SettingsService(session)
    bot_settings = await settings_service.update_subscription_price(price)
    await state.clear()
    await message.answer(
        f"✅ Ціну підписки оновлено: {price} {bot_settings.subscription_currency}.\n\n"
        + _format_settings(bot_settings),
        reply_markup=settings_menu_keyboard(),
    )


@settings_router.message(SettingsStates.duration)
async def on_duration_input(message: Message, state: FSMContext, session) -> None:
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть додатне ціле число.")
        return

    settings_service = SettingsService(session)
    bot_settings = await settings_service.update_subscription_duration(days)
    await state.clear()
    await message.answer(
        f"✅ Тривалість підписки оновлено: {days} днів.\n\n" + _format_settings(bot_settings),
        reply_markup=settings_menu_keyboard(),
    )


@settings_router.message(SettingsStates.reminders)
async def on_reminders_input(message: Message, state: FSMContext, session) -> None:
    try:
        days = sorted(
            {int(part.strip()) for part in message.text.split(",") if part.strip()},
            reverse=True,
        )
        if not days or any(day <= 0 for day in days):
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть дні через кому, наприклад: 3,1")
        return

    settings_service = SettingsService(session)
    bot_settings = await settings_service.update_reminder_days(days)
    await state.clear()
    await message.answer(
        "✅ Розклад нагадувань оновлено.\n\n" + _format_settings(bot_settings),
        reply_markup=settings_menu_keyboard(),
    )


@settings_router.message(SettingsStates.channel)
async def on_channel_input(message: Message, state: FSMContext, session, bot: Bot) -> None:
    settings_service = SettingsService(session)
    try:
        bot_settings = await settings_service.change_community_channel(bot, message.text)
    except ChannelValidationError as error:
        await message.answer(f"⚠️ {error}")
        return

    await state.clear()
    await message.answer(
        "✅ Канал спільноти оновлено.\n\n" + _format_settings(bot_settings),
        reply_markup=settings_menu_keyboard(),
    )
