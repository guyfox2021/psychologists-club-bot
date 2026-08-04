from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Settings
from app.database.models.enums import SubscriptionStatus
from app.database.repositories import SubscriptionRepository
from app.utils.datetime_utils import format_datetime_human

subscriptions_router = Router(name="admin_subscriptions")

_STATUS_LABELS = {
    SubscriptionStatus.WAITING: "Очікують оплату",
    SubscriptionStatus.TRIAL: "Пробний період",
    SubscriptionStatus.ACTIVE: "Активні",
    SubscriptionStatus.EXPIRED: "Завершені",
    SubscriptionStatus.FAILED: "Помилка оплати",
    SubscriptionStatus.CANCELLED: "Скасовані",
}


@subscriptions_router.message(Command("subscriptions"))
async def on_subscriptions_overview(message: Message, session, settings: Settings) -> None:
    repo = SubscriptionRepository(session)

    lines = ["📦 <b>Підписки</b>", ""]
    for status, label in _STATUS_LABELS.items():
        count = await repo.count_by_status(status)
        lines.append(f"{label}: <b>{count}</b>")

    lines.append("")
    lines.append("👥 <b>Активні / пробні (останні оновлення)</b>")

    active = await repo.list_by_status(SubscriptionStatus.ACTIVE)
    trial = await repo.list_by_status(SubscriptionStatus.TRIAL)
    for subscription in (active[:5] + trial[:5]):
        end_date = subscription.subscription_end or subscription.trial_end
        end_text = format_datetime_human(end_date, settings.timezone) if end_date else "безстроково"
        lines.append(
            f"• <code>{subscription.user.telegram_id}</code> — "
            f"{_STATUS_LABELS[subscription.status]}, до {end_text}"
        )

    await message.answer("\n".join(lines))
