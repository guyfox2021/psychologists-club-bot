import logging
from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Message

from app.admin.callback_data import AdminReviewCB
from app.admin.keyboards import application_review_keyboard
from app.config import Settings
from app.database.models import Application
from app.database.models.enums import ApplicationStatus, SubscriptionStatus, UserRoleCode
from app.database.repositories import SettingsRepository, SubscriptionRepository
from app.keyboards.common import restart_verification_keyboard
from app.keyboards.documents import documents_upload_keyboard
from app.keyboards.payment import payment_confirmation_keyboard
from app.services.access_service import AccessService
from app.services.admin_log_service import AdminLogService
from app.services.application_service import ApplicationService
from app.services.user_service import UserService
from app.states.admin_states import ApplicationReviewStates
from app.states.documents_states import DocumentUploadStates

logger = logging.getLogger(__name__)

applications_router = Router(name="admin_applications")

_IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}


def format_application_card(application: Application, status_footer: str | None = None) -> str:
    role_label = application.role.label_uk if application.role else "—"
    lines = [
        f"🆕 <b>Заявка #{application.id}</b>",
        "",
        f"👤 {application.first_name} {application.last_name}",
        f"🎓 Роль: {role_label}",
        f"📞 {application.phone}",
        f"✉️ {application.email}",
        f"🏙 {application.city}",
        f"📎 Документів: {len(application.documents)}",
    ]
    if status_footer:
        lines += ["", status_footer]
    return "\n".join(lines)


async def notify_admins_new_application(
    bot: Bot, session, settings: Settings, application: Application
) -> None:
    user_service = UserService(session)
    admin_ids = await user_service.list_all_admin_telegram_ids(settings.super_admin_id_list)
    card_text = format_application_card(application)
    keyboard = application_review_keyboard(application.id)

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, card_text, reply_markup=keyboard)
            for document in application.documents:
                if document.mime_type in _IMAGE_MIME_TYPES:
                    await bot.send_photo(admin_id, document.telegram_file_id)
                else:
                    await bot.send_document(admin_id, document.telegram_file_id)
        except (TelegramForbiddenError, TelegramBadRequest) as error:
            logger.warning(
                "Could not notify admin %s about application %s: %s",
                admin_id,
                application.id,
                error,
            )


@applications_router.message(Command("applications"))
async def on_applications_list(message: Message, session) -> None:
    application_service = ApplicationService(session)
    pending = await application_service.list_pending(limit=10)
    if not pending:
        await message.answer("⏳ Немає заявок на розгляді.")
        return

    await message.answer(f"⏳ Заявок на розгляді: {len(pending)}")
    for application in pending:
        await message.answer(
            format_application_card(application),
            reply_markup=application_review_keyboard(application.id),
        )


async def _grant_free_permanent_access(
    session, bot: Bot, owner, bot_settings, now: datetime, welcome_text: str
) -> str | None:
    """Grant immediate, free, permanent community access (no trial, no payment).

    Used for Supervisors (per spec) and, while `settings.payment_required` is
    turned off, for every approved role. Returns the invite link, or None if
    the community channel isn't configured yet.
    """
    if bot_settings.community_chat_id is None:
        return None

    access_service = AccessService(bot)
    invite_link = await access_service.create_invite_link(
        bot_settings.community_chat_id, name=f"user_{owner.telegram_id}", member_limit=1
    )
    subscription_repo = SubscriptionRepository(session)
    await subscription_repo.get_or_create(owner.id)
    await subscription_repo.update(
        owner.id,
        status=SubscriptionStatus.ACTIVE,
        subscription_start=now,
        subscription_end=None,
        invite_link=invite_link,
    )
    await bot.send_message(owner.telegram_id, welcome_text.format(invite_link=invite_link))
    return invite_link


@applications_router.callback_query(AdminReviewCB.filter(F.action == "approve"))
async def on_approve(
    callback: CallbackQuery, callback_data: AdminReviewCB, session, bot: Bot, settings: Settings
) -> None:
    application_service = ApplicationService(session)
    application = await application_service.get_application(callback_data.application_id)
    if application is None:
        await callback.answer("Заявку не знайдено.", show_alert=True)
        return
    if application.status == ApplicationStatus.APPROVED:
        await callback.answer("Заявку вже схвалено.", show_alert=True)
        return

    now = datetime.now(UTC)
    application = await application_service.approve(application.id, callback.from_user.id, now)

    admin_log_service = AdminLogService(session)
    await admin_log_service.log(
        callback.from_user.id,
        "approve_application",
        target_user_id=application.user_id,
        details={"application_id": application.id},
    )

    user_service = UserService(session)
    owner = await user_service.get_by_id(application.user_id)

    settings_repo = SettingsRepository(session)
    bot_settings = await settings_repo.get_or_create()

    is_supervisor = application.role and application.role.code == UserRoleCode.SUPERVISOR.value

    if is_supervisor or not settings.payment_required:
        welcome_text = (
            "🎉 Вітаємо! Вашу верифікацію успішно завершено.\n\n"
            + (
                "Ви отримали постійний доступ до спільноти як супервізор.\n\n"
                if is_supervisor
                else "Ви отримали доступ до спільноти.\n\n"
            )
            + "🔗 Посилання для вступу: {invite_link}"
        )
        invite_link = await _grant_free_permanent_access(
            session, bot, owner, bot_settings, now, welcome_text
        )
        if invite_link is None:
            await callback.message.edit_text(
                format_application_card(
                    application,
                    "⚠️ Канал спільноти не налаштовано. Використайте /settings.",
                ),
                reply_markup=None,
            )
            await callback.answer()
            return
    else:
        await bot.send_message(
            owner.telegram_id,
            "🎉 Вітаємо! Вашу верифікацію успішно завершено.\n\n"
            "Перед отриманням доступу, будь ласка, підтвердьте спосіб оплати.\n"
            "Кошти не будуть списані сьогодні — оплата почнеться лише після завершення "
            "безкоштовного пробного періоду.",
            reply_markup=payment_confirmation_keyboard(),
        )

    await callback.message.edit_text(
        format_application_card(
            application, f"✅ <b>Схвалено адміністратором {callback.from_user.full_name}</b>"
        ),
        reply_markup=None,
    )
    await callback.answer("Заявку схвалено")


@applications_router.callback_query(AdminReviewCB.filter(F.action == "reject"))
async def on_reject_start(
    callback: CallbackQuery, callback_data: AdminReviewCB, state: FSMContext
) -> None:
    await state.set_state(ApplicationReviewStates.reject_reason)
    await state.update_data(application_id=callback_data.application_id)
    await callback.message.answer("✏️ Введіть причину відхилення заявки:")
    await callback.answer()


@applications_router.message(ApplicationReviewStates.reject_reason)
async def on_reject_reason(message: Message, state: FSMContext, session, bot: Bot) -> None:
    data = await state.get_data()
    application_id = data.get("application_id")
    await state.clear()

    application_service = ApplicationService(session)
    application = await application_service.reject(
        application_id, message.from_user.id, message.text, datetime.now(UTC)
    )
    if application is None:
        await message.answer("Заявку не знайдено.")
        return

    admin_log_service = AdminLogService(session)
    await admin_log_service.log(
        message.from_user.id,
        "reject_application",
        target_user_id=application.user_id,
        details={"application_id": application_id, "reason": message.text},
    )

    user_service = UserService(session)
    owner = await user_service.get_by_id(application.user_id)
    await bot.send_message(
        owner.telegram_id, f"❌ На жаль, вашу заявку відхилено.\n\nПричина: {message.text}"
    )
    await message.answer(f"Заявку #{application_id} відхилено.")


@applications_router.callback_query(AdminReviewCB.filter(F.action == "request_docs"))
async def on_request_docs_start(
    callback: CallbackQuery, callback_data: AdminReviewCB, state: FSMContext
) -> None:
    await state.set_state(ApplicationReviewStates.more_docs_comment)
    await state.update_data(application_id=callback_data.application_id)
    await callback.message.answer("✏️ Введіть коментар щодо необхідних документів:")
    await callback.answer()


@applications_router.message(ApplicationReviewStates.more_docs_comment)
async def on_request_docs_comment(message: Message, state: FSMContext, session, bot: Bot) -> None:
    data = await state.get_data()
    application_id = data.get("application_id")
    await state.clear()

    application_service = ApplicationService(session)
    application = await application_service.request_more_documents(
        application_id, message.from_user.id, message.text, datetime.now(UTC)
    )
    if application is None:
        await message.answer("Заявку не знайдено.")
        return

    admin_log_service = AdminLogService(session)
    await admin_log_service.log(
        message.from_user.id,
        "request_more_documents",
        target_user_id=application.user_id,
        details={"application_id": application_id, "comment": message.text},
    )

    user_service = UserService(session)
    owner = await user_service.get_by_id(application.user_id)

    target_key = StorageKey(bot_id=bot.id, chat_id=owner.telegram_id, user_id=owner.telegram_id)
    target_state = FSMContext(storage=state.storage, key=target_key)
    await target_state.set_state(DocumentUploadStates.uploading)
    await target_state.update_data(application_id=application_id)

    await bot.send_message(
        owner.telegram_id,
        "📎 Адміністратор просить надати додаткові документи.\n\n"
        f"Коментар: {message.text}\n\n"
        "Будь ласка, надішліть додаткові файли (PDF, JPG, PNG). "
        "Коли завершите, натисніть «Завершити завантаження».",
        reply_markup=documents_upload_keyboard(),
    )
    await message.answer(f"Заявку #{application_id} повернуто на доопрацювання.")


@applications_router.callback_query(AdminReviewCB.filter(F.action == "wrong_status"))
async def on_wrong_status_start(
    callback: CallbackQuery, callback_data: AdminReviewCB, state: FSMContext
) -> None:
    await state.set_state(ApplicationReviewStates.wrong_status_comment)
    await state.update_data(application_id=callback_data.application_id)
    await callback.message.answer(
        "✏️ Введіть коментар: який статус підходить цій людині (наприклад, "
        "«Психолог на старті» або «Студент»):"
    )
    await callback.answer()


@applications_router.message(ApplicationReviewStates.wrong_status_comment)
async def on_wrong_status_comment(message: Message, state: FSMContext, session, bot: Bot) -> None:
    """Reject the application with the admin's status-correction comment, then
    offer the applicant a one-tap restart -- reuses the existing REJECTED
    fallthrough in `on_start_verification` (questionnaire.py), which already
    sends anyone whose latest application is REJECTED back to role selection,
    so no changes were needed there.
    """
    data = await state.get_data()
    application_id = data.get("application_id")
    await state.clear()

    application_service = ApplicationService(session)
    application = await application_service.reject(
        application_id, message.from_user.id, message.text, datetime.now(UTC)
    )
    if application is None:
        await message.answer("Заявку не знайдено.")
        return

    admin_log_service = AdminLogService(session)
    await admin_log_service.log(
        message.from_user.id,
        "wrong_status_application",
        target_user_id=application.user_id,
        details={"application_id": application_id, "comment": message.text},
    )

    user_service = UserService(session)
    owner = await user_service.get_by_id(application.user_id)
    await bot.send_message(
        owner.telegram_id,
        "🔄 Адміністратор вважає, що для вас підходить інший статус.\n\n"
        f"Коментар: {message.text}\n\n"
        "Натисніть кнопку нижче, щоб почати заново і обрати підходящий статус.",
        reply_markup=restart_verification_keyboard(),
    )
    await message.answer(f"Заявку #{application_id} позначено як таку, що потребує зміни статусу.")
