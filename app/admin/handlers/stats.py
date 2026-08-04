from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database.models.enums import ApplicationStatus, PaymentStatus, SubscriptionStatus
from app.database.repositories import (
    ApplicationRepository,
    PaymentRepository,
    SubscriptionRepository,
    UserRepository,
)

stats_router = Router(name="admin_stats")


@stats_router.message(Command("stats"))
async def on_stats(message: Message, session) -> None:
    user_repo = UserRepository(session)
    application_repo = ApplicationRepository(session)
    subscription_repo = SubscriptionRepository(session)
    payment_repo = PaymentRepository(session)

    total_users = await user_repo.count_total()
    pending_applications = await application_repo.count_by_status(ApplicationStatus.PENDING)
    approved_applications = await application_repo.count_by_status(ApplicationStatus.APPROVED)
    rejected_applications = await application_repo.count_by_status(ApplicationStatus.REJECTED)

    trial_subscriptions = await subscription_repo.count_by_status(SubscriptionStatus.TRIAL)
    active_subscriptions = await subscription_repo.count_by_status(SubscriptionStatus.ACTIVE)
    failed_subscriptions = await subscription_repo.count_by_status(SubscriptionStatus.FAILED)

    successful_payments = await payment_repo.count_by_status(PaymentStatus.SUCCESS)
    revenue = await payment_repo.sum_amount_by_status(PaymentStatus.SUCCESS)

    text = (
        "📊 <b>Загальна статистика</b>\n\n"
        f"👥 Користувачів усього: <b>{total_users}</b>\n\n"
        "📄 <b>Заявки</b>\n"
        f"⏳ На розгляді: <b>{pending_applications}</b>\n"
        f"✅ Схвалено: <b>{approved_applications}</b>\n"
        f"❌ Відхилено: <b>{rejected_applications}</b>\n\n"
        "📦 <b>Підписки</b>\n"
        f"🎁 Пробний період: <b>{trial_subscriptions}</b>\n"
        f"✅ Активні: <b>{active_subscriptions}</b>\n"
        f"⚠️ Помилка оплати: <b>{failed_subscriptions}</b>\n\n"
        "💳 <b>Платежі</b>\n"
        f"Успішних: <b>{successful_payments}</b>\n"
        f"Загальний дохід: <b>{revenue}</b>"
    )
    await message.answer(text)
