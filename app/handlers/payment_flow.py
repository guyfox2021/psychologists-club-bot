import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Settings
from app.keyboards.callback_data import PaymentCB
from app.keyboards.payment import invoice_link_keyboard
from app.payments.monobank_client import MonobankClient, MonobankError
from app.payments.payment_service import PaymentService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = Router(name="payment_flow")


@router.callback_query(PaymentCB.filter(F.action == "confirm"))
async def on_confirm_payment_method(callback: CallbackQuery, session, settings: Settings) -> None:
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer("Спочатку пройдіть верифікацію через /start.", show_alert=True)
        return

    client = MonobankClient(settings)
    payment_service = PaymentService(session, client)

    try:
        invoice_url = await payment_service.create_authorization_invoice(user.id)
    except MonobankError:
        logger.exception("Failed to create authorization invoice for user %s", user.id)
        await callback.answer(
            "Сталася помилка при створенні рахунку. Спробуйте пізніше або зверніться до адміністратора.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "💳 Перейдіть за посиланням нижче, щоб безпечно підтвердити спосіб оплати картки "
        "через Monobank.\n\n"
        "Кошти не будуть списані сьогодні — це лише верифікація картки. Оплата підключиться "
        "автоматично після завершення безкоштовного пробного періоду.",
        reply_markup=invoice_link_keyboard(invoice_url),
    )
    await callback.answer()


@router.callback_query(PaymentCB.filter(F.action == "retry_later"))
async def on_retry_later(callback: CallbackQuery) -> None:
    await callback.answer(
        "Добре, ми спробуємо провести оплату автоматично ще раз найближчим часом.",
        show_alert=True,
    )
