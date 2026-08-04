from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.admin.handlers.applications import notify_admins_new_application
from app.config import Settings
from app.database.models.enums import ApplicationStatus
from app.keyboards.callback_data import DocumentsCB
from app.keyboards.documents import documents_upload_keyboard
from app.services.application_service import ApplicationService
from app.services.verification_service import VerificationService
from app.states.documents_states import DocumentUploadStates
from app.utils.validators import is_allowed_document_mime_type, is_allowed_document_size

router = Router(name="documents")


def _extract_file_info(message: Message) -> tuple[str, str, str | None, int | None] | None:
    if message.document is not None:
        document = message.document
        return document.file_id, document.file_unique_id, document.mime_type, document.file_size
    if message.photo:
        photo = message.photo[-1]
        return photo.file_id, photo.file_unique_id, "image/jpeg", photo.file_size
    return None


@router.message(DocumentUploadStates.uploading, F.document | F.photo)
async def on_document_uploaded(message: Message, state: FSMContext, session) -> None:
    file_info = _extract_file_info(message)
    if file_info is None:
        await message.answer("⚠️ Будь ласка, надішліть файл у форматі PDF, JPG або PNG.")
        return

    file_id, file_unique_id, mime_type, file_size = file_info

    if mime_type is not None and not is_allowed_document_mime_type(mime_type):
        await message.answer("⚠️ Дозволені формати: PDF, JPG, PNG.")
        return
    if not is_allowed_document_size(file_size):
        await message.answer("⚠️ Файл занадто великий (максимум 20 МБ).")
        return

    data = await state.get_data()
    application_id = data.get("application_id")
    if application_id is None:
        await message.answer("⚠️ Сталася помилка стану. Будь ласка, почніть з /start.")
        await state.clear()
        return

    verification_service = VerificationService(session)
    await verification_service.add_document(application_id, file_id, file_unique_id, mime_type)

    await message.answer(
        "✅ Файл отримано. Можете надіслати ще або натиснути «Завершити завантаження».",
        reply_markup=documents_upload_keyboard(),
    )


@router.message(DocumentUploadStates.uploading)
async def on_unsupported_content(message: Message) -> None:
    await message.answer(
        "⚠️ Будь ласка, надішліть документ або фото (PDF, JPG, PNG), "
        "або натисніть «Завершити завантаження».",
        reply_markup=documents_upload_keyboard(),
    )


@router.callback_query(DocumentUploadStates.uploading, DocumentsCB.filter(F.action == "done"))
async def on_documents_done(
    callback: CallbackQuery, state: FSMContext, session, bot: Bot, settings: Settings
) -> None:
    data = await state.get_data()
    application_id = data.get("application_id")
    if application_id is None:
        await callback.answer("Сталася помилка стану.", show_alert=True)
        return

    application_service = ApplicationService(session)
    application = await application_service.get_application(application_id)
    if application is None:
        await callback.answer("Заявку не знайдено.", show_alert=True)
        return

    if not application.documents:
        await callback.answer("Спочатку надішліть хоча б один документ.", show_alert=True)
        return

    if application.status == ApplicationStatus.NEED_MORE_DOCS:
        application = await application_service.resubmit(application_id)

    await state.clear()
    await callback.message.edit_text(
        "✅ Дякуємо! Ваші документи надіслано на розгляд адміністратора. "
        "Ми повідомимо вас, щойно рішення буде прийнято."
    )
    await callback.answer()

    await notify_admins_new_application(bot, session, settings, application)
