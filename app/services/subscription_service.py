import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Subscription
from app.database.models.enums import PaymentTransactionType, SubscriptionStatus
from app.database.repositories import SettingsRepository, SubscriptionRepository, TrialRepository
from app.payments.monobank_client import MonobankClient, MonobankError
from app.payments.payment_service import PaymentService
from app.utils.datetime_utils import add_days

logger = logging.getLogger(__name__)

_RETRY_INTERVAL_DAYS = 1


@dataclass(frozen=True)
class ChargeOutcome:
    success: bool
    user_id: int
    subscription_end: datetime | None = None
    retry_count: int = 0


class SubscriptionService:
    """Owns subscription lifecycle transitions triggered by the scheduler.

    Payment-gateway interaction itself is delegated to `PaymentService`; this
    service decides what a charge result *means* for the subscription record
    (extend it, mark it failed and schedule a retry, etc).
    """

    def __init__(self, session: AsyncSession, client: MonobankClient) -> None:
        self._session = session
        self._payment_service = PaymentService(session, client)
        self._subscription_repo = SubscriptionRepository(session)
        self._trial_repo = TrialRepository(session)
        self._settings_repo = SettingsRepository(session)

    async def process_due_charge(self, subscription: Subscription) -> ChargeOutcome:
        transaction_type = (
            PaymentTransactionType.TRIAL_CHARGE
            if subscription.status == SubscriptionStatus.TRIAL
            else PaymentTransactionType.RENEWAL_CHARGE
        )

        try:
            response = await self._payment_service.charge_subscription(
                subscription.user_id, transaction_type
            )
        except MonobankError:
            logger.exception("Charge failed for user %s", subscription.user_id)
            return await self._mark_failed(subscription)

        if response.is_success:
            return await self._mark_active(subscription)
        return await self._mark_failed(subscription)

    async def _mark_active(self, subscription: Subscription) -> ChargeOutcome:
        bot_settings = await self._settings_repo.get_or_create()
        now = datetime.now(UTC)
        subscription_end = add_days(now, bot_settings.subscription_duration_days)

        await self._subscription_repo.update(
            subscription.user_id,
            status=SubscriptionStatus.ACTIVE,
            subscription_start=now,
            subscription_end=subscription_end,
            next_charge_at=subscription_end,
            retry_count=0,
        )

        if subscription.status == SubscriptionStatus.TRIAL:
            trial = await self._trial_repo.get_latest_by_user(subscription.user_id)
            if trial is not None:
                await self._trial_repo.mark_converted(trial.id)

        return ChargeOutcome(success=True, user_id=subscription.user_id, subscription_end=subscription_end)

    async def _mark_failed(self, subscription: Subscription) -> ChargeOutcome:
        retry_count = subscription.retry_count + 1
        next_retry_at = datetime.now(UTC) + timedelta(days=_RETRY_INTERVAL_DAYS)

        await self._subscription_repo.update(
            subscription.user_id,
            status=SubscriptionStatus.FAILED,
            retry_count=retry_count,
            next_charge_at=next_retry_at,
        )
        return ChargeOutcome(success=False, user_id=subscription.user_id, retry_count=retry_count)
