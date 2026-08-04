from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database.models.enums import PaymentStatus
from app.database.repositories import PaymentRepository
from app.utils.datetime_utils import format_datetime_human

payments_router = Router(name="admin_payments")

_STATUS_ICONS = {
    PaymentStatus.SUCCESS: "✅",
    PaymentStatus.FAILED: "❌",
    PaymentStatus.WAITING: "⏳",
    PaymentStatus.REFUNDED: "↩️",
    PaymentStatus.CANCELLED: "🚫",
}

_TRANSACTION_LABELS = {
    "authorization": "авторизація",
    "trial_charge": "списання після тріалу",
    "renewal_charge": "продовження",
}


@payments_router.message(Command("payments"))
async def on_payments_list(message: Message, session, settings) -> None:
    payment_repo = PaymentRepository(session)
    payments = await payment_repo.list_recent(limit=20)
    if not payments:
        await message.answer("Платежів ще немає.")
        return

    lines = ["💳 <b>Останні платежі</b>", ""]
    for payment in payments:
        icon = _STATUS_ICONS.get(payment.status, "•")
        transaction_label = _TRANSACTION_LABELS.get(
            payment.transaction_type.value, payment.transaction_type.value
        )
        created_at = format_datetime_human(payment.created_at, settings.timezone)
        lines.append(
            f"{icon} <code>{payment.order_reference}</code> — "
            f"{payment.amount} {payment.currency} ({transaction_label}), {created_at}"
        )

    await message.answer("\n".join(lines))
