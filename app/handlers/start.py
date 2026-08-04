from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.callback_data import StartCB
from app.keyboards.common import welcome_keyboard
from app.services.user_service import UserService

router = Router(name="start")

WELCOME_TEXT = (
    "👋 Вітаємо у закритій спільноті психологів!\n\n"
    "Цей бот проведе вас через верифікацію, після чого ви отримаєте доступ "
    "до закритого каналу спільноти.\n\n"
    "📋 <b>Правила спільноти:</b>\n"
    "— Взаємна повага та конфіденційність\n"
    "— Підтвердження кваліфікації документами\n"
    "— Дотримання етичного кодексу психолога\n\n"
    "🔎 <b>Процес верифікації:</b>\n"
    "1. Анкета (ПІБ, контакти, роль)\n"
    "2. Завантаження підтверджуючих документів\n"
    "3. Розгляд адміністратором\n"
    "4. Підтвердження способу оплати (для студентів/психологів)\n"
    "5. Доступ до спільноти\n\n"
    "Оберіть дію нижче 👇"
)


@router.message(CommandStart())
async def on_start(message: Message, state: FSMContext, session) -> None:
    await state.clear()
    user_service = UserService(session)
    await user_service.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    await message.answer(WELCOME_TEXT, reply_markup=welcome_keyboard())


@router.callback_query(StartCB.filter(F.action == "back"))
async def on_back_to_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=welcome_keyboard())
    await callback.answer()
