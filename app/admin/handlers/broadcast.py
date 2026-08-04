from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.admin.callback_data import BroadcastCB
from app.admin.keyboards import broadcast_audience_keyboard
from app.services.admin_log_service import AdminLogService
from app.services.broadcast_service import BroadcastService
from app.states.admin_states import BroadcastStates

broadcast_router = Router(name="admin_broadcast")

_AUDIENCE_LABELS = {
    "all": "усіх користувачів",
    "student": "студентів",
    "psychologist": "психологів",
    "supervisor": "супервізорів",
}


@broadcast_router.message(Command("broadcast"))
async def on_broadcast_start(message: Message) -> None:
    await message.answer(
        "📢 Оберіть аудиторію розсилки:", reply_markup=broadcast_audience_keyboard()
    )


@broadcast_router.callback_query(BroadcastCB.filter())
async def on_audience_selected(
    callback: CallbackQuery, callback_data: BroadcastCB, state: FSMContext
) -> None:
    await state.set_state(BroadcastStates.message)
    await state.update_data(audience=callback_data.audience)
    audience_label = _AUDIENCE_LABELS.get(callback_data.audience, callback_data.audience)
    await callback.message.edit_text(
        f"✍️ Введіть текст розсилки для {audience_label} одним повідомленням:"
    )
    await callback.answer()


@broadcast_router.message(BroadcastStates.message)
async def on_broadcast_message(message: Message, state: FSMContext, session, bot: Bot) -> None:
    data = await state.get_data()
    audience = data.get("audience", "all")
    await state.clear()

    role_code = None if audience == "all" else audience
    broadcast_service = BroadcastService(session, bot)
    sent, failed = await broadcast_service.send_to_role(role_code, message.text)

    await AdminLogService(session).log(
        message.from_user.id,
        "broadcast",
        details={"audience": audience, "sent": sent, "failed": failed},
    )

    await message.answer(f"📤 Розсилку завершено.\n✅ Надіслано: {sent}\n❌ Помилок: {failed}")
