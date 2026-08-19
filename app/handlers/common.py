import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.keyboards.callback_data import StartCB
from app.keyboards.common import back_to_start_keyboard
from app.services.user_service import UserService
from app.states.common_states import ContactAdminStates

logger = logging.getLogger(__name__)

router = Router(name="common")

FAQ_TEXT = (
    "❓ <b>Часті питання</b>\n\n"
    "<b>Хто може вступити до спільноти?</b>\n"
    "Студенти психологічних спеціальностей, практикуючі психологи та супервізори.\n\n"
    "<b>Чи потрібно платити?</b>\n"
    "Для категорій «Студент» та «Психолог на старті» — так, одразу після підтвердження картки "
    "(пробного періоду немає). Для «Психолог» та «Супервізор» доступ безкоштовний.\n\n"
    "<b>Як скасувати підписку?</b>\n"
    "Командою /cancel_subscription — автоматичне списання зупиниться, а доступ триватиме до "
    "кінця вже оплаченого періоду.\n\n"
    "<b>Скільки триває перевірка заявки?</b>\n"
    "Зазвичай адміністратор розглядає заявку протягом кількох днів.\n\n"
    "<b>Що робити, якщо документи відхилено?</b>\n"
    "Адміністратор повідомить причину — ви зможете подати заявку повторно."
)


@router.callback_query(StartCB.filter(F.action == "faq"))
async def on_faq(callback: CallbackQuery) -> None:
    await callback.message.edit_text(FAQ_TEXT, reply_markup=back_to_start_keyboard())
    await callback.answer()


@router.callback_query(StartCB.filter(F.action == "contact_admin"))
async def on_contact_admin_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ContactAdminStates.message)
    await callback.message.edit_text(
        "✍️ Напишіть ваше повідомлення адміністратору одним повідомленням. "
        "Ми передамо його якнайшвидше."
    )
    await callback.answer()


@router.message(ContactAdminStates.message)
async def on_contact_admin_message(
    message: Message, state: FSMContext, session, bot: Bot, settings: Settings
) -> None:
    await state.clear()
    user_service = UserService(session)
    admin_ids = await user_service.list_all_admin_telegram_ids(settings.super_admin_id_list)

    sender = message.from_user
    header = (
        "✉️ <b>Повідомлення від користувача</b>\n"
        f"👤 {sender.full_name} (@{sender.username or '—'}, id={sender.id})\n\n"
    )
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, header + message.text)
        except (TelegramForbiddenError, TelegramBadRequest) as error:
            logger.warning("Could not forward user message to admin %s: %s", admin_id, error)

    await message.answer("✅ Ваше повідомлення надіслано адміністратору.")
