from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database.models.enums import ApplicationStatus, UserRoleCode
from app.database.repositories import RoleRepository
from app.keyboards.callback_data import RoleCB, StartCB
from app.keyboards.documents import documents_upload_keyboard
from app.keyboards.role_select import role_select_keyboard
from app.services.application_service import ApplicationService
from app.services.user_service import UserService
from app.states.documents_states import DocumentUploadStates
from app.states.questionnaire_states import QuestionnaireStates

router = Router(name="questionnaire")


@router.callback_query(StartCB.filter(F.action == "verify"))
async def on_start_verification(callback: CallbackQuery, state: FSMContext, session) -> None:
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    application_service = ApplicationService(session)
    application = await application_service.get_latest_for_user(user.id) if user else None

    if application is not None and application.status == ApplicationStatus.PENDING:
        await callback.message.edit_text(
            "⏳ Вашу заявку вже подано і зараз вона на розгляді адміністратора."
        )
        await callback.answer()
        return

    if application is not None and application.status == ApplicationStatus.APPROVED:
        await callback.message.edit_text("✅ Вашу верифікацію вже завершено раніше.")
        await callback.answer()
        return

    if application is not None and application.status == ApplicationStatus.NEED_MORE_DOCS:
        await state.set_state(DocumentUploadStates.uploading)
        await state.update_data(application_id=application.id)
        await callback.message.edit_text(
            "📎 Адміністратор запросив додаткові документи.\n\n"
            f"Коментар: {application.admin_comment or '—'}\n\n"
            "Будь ласка, надішліть файли (PDF, JPG, PNG). "
            "Коли завершите, натисніть «Завершити завантаження»."
        )
        await callback.message.answer("Очікую файли:", reply_markup=documents_upload_keyboard())
        await callback.answer()
        return

    role_repo = RoleRepository(session)
    roles = await role_repo.list_all()
    await state.set_state(QuestionnaireStates.role)
    await callback.message.edit_text(
        "🎓 Оберіть вашу роль у спільноті:", reply_markup=role_select_keyboard(roles)
    )
    await callback.answer()


@router.callback_query(QuestionnaireStates.role, RoleCB.filter())
async def on_role_selected(
    callback: CallbackQuery, callback_data: RoleCB, state: FSMContext
) -> None:
    await state.update_data(role_code=callback_data.code)
    await state.set_state(QuestionnaireStates.first_name)
    await callback.message.edit_text("✏️ Введіть ваше ім'я:")
    await callback.answer()


@router.message(QuestionnaireStates.first_name)
async def on_first_name(message: Message, state: FSMContext) -> None:
    await state.update_data(first_name=message.text.strip())
    await state.set_state(QuestionnaireStates.last_name)
    await message.answer("✏️ Введіть ваше прізвище:")


@router.message(QuestionnaireStates.last_name)
async def on_last_name(message: Message, state: FSMContext) -> None:
    await state.update_data(last_name=message.text.strip())
    await state.set_state(QuestionnaireStates.phone)
    await message.answer("📞 Введіть ваш номер телефону:")


@router.message(QuestionnaireStates.phone)
async def on_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.text.strip())
    await state.set_state(QuestionnaireStates.email)
    await message.answer("✉️ Введіть вашу електронну пошту:")


@router.message(QuestionnaireStates.email)
async def on_email(message: Message, state: FSMContext) -> None:
    await state.update_data(email=message.text.strip())
    await state.set_state(QuestionnaireStates.city)
    await message.answer("🏙 Введіть ваше місто:")


@router.message(QuestionnaireStates.city)
async def on_city(message: Message, state: FSMContext, session) -> None:
    data = await state.update_data(city=message.text.strip())

    user_service = UserService(session)
    user = await user_service.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    role_repo = RoleRepository(session)
    role = await role_repo.get_by_code(data["role_code"])

    await user_service.update_profile(
        user_id=user.id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data["phone"],
        email=data["email"],
        city=data["city"],
        role_id=role.id,
    )

    application_service = ApplicationService(session)
    application = await application_service.create_application(
        user_id=user.id,
        role_code=UserRoleCode(data["role_code"]),
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data["phone"],
        email=data["email"],
        city=data["city"],
    )

    await state.set_state(DocumentUploadStates.uploading)
    await state.update_data(application_id=application.id)

    await message.answer(
        "📎 Дякуємо! Тепер, будь ласка, надішліть документи, що підтверджують вашу кваліфікацію "
        "(PDF, JPG або PNG). Можна надіслати декілька файлів.\n\n"
        "Коли завершите, натисніть «Завершити завантаження».",
        reply_markup=documents_upload_keyboard(),
    )
