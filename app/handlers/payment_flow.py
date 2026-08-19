import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.database.models import Subscription
from app.database.models.enums import SubscriptionStatus
from app.database.repositories import SubscriptionRepository
from app.keyboards.callback_data import PaymentCB
from app.keyboards.payment import cancel_subscription_keyboard, invoice_link_keyboard
from app.payments.monobank_client import MonobankClient, MonobankError
from app.payments.payment_service import PaymentService
from app.services.subscription_service import SubscriptionService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = Router(name="payment_flow")

_CANCELLABLE_STATUSES = {SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE}


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

    price_hint = (
        f" ({user.role.price_uah} грн)" if user.role and user.role.price_uah is not None else ""
    )
    await callback.message.edit_text(
        "💳 Перейдіть за посиланням нижче, щоб безпечно підтвердити спосіб оплати картки "
        "через Monobank.\n\n"
        f"⚠️ Одразу після підтвердження картки з неї спишеться оплата{price_hint} — "
        "пробного періоду немає.",
        reply_markup=invoice_link_keyboard(invoice_url),
    )
    await callback.answer()


@router.callback_query(PaymentCB.filter(F.action == "retry_later"))
async def on_retry_later(callback: CallbackQuery) -> None:
    await callback.answer(
        "Добре, ми спробуємо провести оплату автоматично ще раз найближчим часом.",
        show_alert=True,
    )


def _end_date_text(subscription: Subscription) -> str:
    end_date = subscription.subscription_end or subscription.trial_end
    return end_date.strftime("%d.%m.%Y") if end_date else "—"


@router.message(Command("cancel_subscription"))
async def on_cancel_subscription_start(message: Message, session) -> None:
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("Спочатку пройдіть верифікацію через /start.")
        return

    subscription_repo = SubscriptionRepository(session)
    subscription = await subscription_repo.get_by_user_id(user.id)
    if subscription is None or subscription.status not in _CANCELLABLE_STATUSES:
        await message.answer("У вас немає активної платної підписки для скасування.")
        return

    await message.answer(
        "Ви впевнені, що хочете скасувати автоматичне продовження підписки?\n\n"
        f"Доступ до спільноти залишиться активним до {_end_date_text(subscription)}, після "
        "чого нового списання коштів більше не буде.",
        reply_markup=cancel_subscription_keyboard(),
    )


@router.callback_query(PaymentCB.filter(F.action == "cancel_confirm"))
async def on_cancel_subscription_confirm(
    callback: CallbackQuery, session, settings: Settings
) -> None:
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer("Помилка. Спробуйте /start.", show_alert=True)
        return

    client = MonobankClient(settings)
    subscription_service = SubscriptionService(session, client)
    subscription = await subscription_service.cancel(user.id)
    if subscription is None:
        await callback.answer("Підписку не знайдено.", show_alert=True)
        return

    await callback.message.edit_text(
        "✅ Підписку скасовано. Нового автоматичного списання коштів не буде.\n\n"
        f"Доступ до спільноти залишиться активним до {_end_date_text(subscription)}."
    )
    await callback.answer()


@router.callback_query(PaymentCB.filter(F.action == "cancel_abort"))
async def on_cancel_subscription_abort(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Добре, підписку залишено без змін.")
    await callback.answer()
