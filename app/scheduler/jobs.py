import logging
from datetime import UTC, datetime

from aiogram import Bot

from app.config import Settings
from app.database.engine import session_scope
from app.database.models.enums import NotificationType, SubscriptionStatus
from app.database.repositories import SettingsRepository, SubscriptionRepository
from app.keyboards.payment import payment_failed_keyboard
from app.payments.monobank_client import MonobankClient
from app.services.access_service import AccessService
from app.services.notification_service import NotificationService
from app.services.subscription_service import SubscriptionService
from app.utils.datetime_utils import today_in_tz

logger = logging.getLogger(__name__)


async def run_daily_maintenance(bot: Bot, settings: Settings) -> None:
    await _process_due_charges(bot, settings)
    await _process_cancelled_expirations(bot, settings)
    await _send_expiration_reminders(bot, settings)


async def _process_due_charges(bot: Bot, settings: Settings) -> None:
    now = datetime.now(UTC)
    client = MonobankClient(settings)

    async with session_scope() as session:
        subscription_repo = SubscriptionRepository(session)
        settings_repo = SettingsRepository(session)
        bot_settings = await settings_repo.get_or_create()

        due_subscriptions = await subscription_repo.list_due_for_charge(now)
        logger.info("Processing %s subscriptions due for charge", len(due_subscriptions))

        for subscription in due_subscriptions:
            was_failed = subscription.status == SubscriptionStatus.FAILED
            user = subscription.user
            old_invite_link = subscription.invite_link

            subscription_service = SubscriptionService(session, client)
            outcome = await subscription_service.process_due_charge(subscription)
            notification_service = NotificationService(session, bot)
            access_service = AccessService(bot)

            if outcome.success:
                if was_failed and bot_settings.community_chat_id:
                    invite_link = await access_service.restore_access(
                        bot_settings.community_chat_id,
                        user.telegram_id,
                        name=f"user_{user.telegram_id}",
                    )
                    await subscription_repo.update(user.id, invite_link=invite_link)
                    await notification_service.send(
                        user.id,
                        user.telegram_id,
                        NotificationType.ACCESS_RESTORED,
                        "✅ Оплату успішно проведено! Доступ до спільноти відновлено.\n\n"
                        f"🔗 Нове посилання для вступу: {invite_link}",
                    )
                continue

            if bot_settings.community_chat_id:
                await access_service.kick_user(bot_settings.community_chat_id, user.telegram_id)
                if old_invite_link:
                    await access_service.revoke_invite_link(
                        bot_settings.community_chat_id, old_invite_link
                    )

            await notification_service.send(
                user.id,
                user.telegram_id,
                NotificationType.PAYMENT_FAILED,
                "⚠️ Не вдалося провести оплату підписки, тому доступ до спільноти тимчасово "
                "призупинено.\n\n"
                "Оновіть спосіб оплати, щоб автоматично відновити доступ.",
                reply_markup=payment_failed_keyboard(),
            )


async def _process_cancelled_expirations(bot: Bot, settings: Settings) -> None:
    """Revoke access for CANCELLED subscriptions once their already-paid-for
    period has actually run out -- cancelling stops future billing right
    away (see SubscriptionService.cancel), but access itself continues until
    this point, matching normal "cancel anytime, keep what you paid for"
    subscription behavior.
    """
    now = datetime.now(UTC)

    async with session_scope() as session:
        subscription_repo = SubscriptionRepository(session)
        settings_repo = SettingsRepository(session)
        bot_settings = await settings_repo.get_or_create()

        expired = await subscription_repo.list_cancelled_expired(now)
        logger.info("Processing %s cancelled subscriptions past their end date", len(expired))

        access_service = AccessService(bot)
        notification_service = NotificationService(session, bot)

        for subscription in expired:
            user = subscription.user
            if bot_settings.community_chat_id:
                await access_service.kick_user(bot_settings.community_chat_id, user.telegram_id)
                if subscription.invite_link:
                    await access_service.revoke_invite_link(
                        bot_settings.community_chat_id, subscription.invite_link
                    )

            await subscription_repo.update(user.id, invite_link=None)
            await notification_service.send(
                user.id,
                user.telegram_id,
                NotificationType.SUBSCRIPTION_ENDED,
                "ℹ️ Ваша скасована підписка завершилась, доступ до спільноти закрито. "
                "Ви можете повернутись у будь-який момент через /start.",
            )


async def _send_expiration_reminders(bot: Bot, settings: Settings) -> None:
    today = today_in_tz(settings.timezone)

    async with session_scope() as session:
        settings_repo = SettingsRepository(session)
        bot_settings = await settings_repo.get_or_create()
        if not bot_settings.reminder_days_before:
            return

        subscription_repo = SubscriptionRepository(session)
        candidates = await subscription_repo.list_by_status(SubscriptionStatus.TRIAL)
        candidates += await subscription_repo.list_by_status(SubscriptionStatus.ACTIVE)

        notification_service = NotificationService(session, bot)
        sorted_days = sorted(bot_settings.reminder_days_before)

        for subscription in candidates:
            end_date = (
                subscription.trial_end
                if subscription.status == SubscriptionStatus.TRIAL
                else subscription.subscription_end
            )
            if end_date is None:
                continue

            days_left = (end_date.date() - today).days
            if days_left not in bot_settings.reminder_days_before:
                continue

            notification_type = (
                NotificationType.REMINDER_1D
                if days_left == sorted_days[0]
                else NotificationType.REMINDER_3D
            )
            period_label = "тріал" if subscription.status == SubscriptionStatus.TRIAL else "підписка"

            await notification_service.send(
                subscription.user_id,
                subscription.user.telegram_id,
                notification_type,
                f"⏰ Нагадування: ваш {period_label} завершується через {days_left} дн. "
                f"({end_date.strftime('%d.%m.%Y')}). Переконайтеся, що спосіб оплати актуальний.",
            )
