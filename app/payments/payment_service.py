import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import PaymentStatus, PaymentTransactionType, SubscriptionStatus
from app.database.repositories import (
    PaymentRepository,
    PaymentTokenRepository,
    SettingsRepository,
    SubscriptionRepository,
    TrialRepository,
    UserRepository,
)
from app.payments.monobank_client import MonobankClient, MonobankError
from app.payments.monobank_schemas import MonobankInvoiceStatus
from app.utils.datetime_utils import add_days

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthorizationOutcome:
    success: bool
    user_id: int | None = None
    trial_end: datetime | None = None


class PaymentService:
    """Talks to Monobank Acquiring and persists Payment/PaymentToken rows.

    Subscription/trial *lifecycle* decisions triggered by our own scheduler
    (trial expiry, renewal retries, cancellation) live in the subscription
    service instead -- this service only records what Monobank told us.
    """

    def __init__(self, session: AsyncSession, client: MonobankClient) -> None:
        self._session = session
        self._client = client
        self._payment_repo = PaymentRepository(session)
        self._token_repo = PaymentTokenRepository(session)
        self._subscription_repo = SubscriptionRepository(session)
        self._trial_repo = TrialRepository(session)
        self._settings_repo = SettingsRepository(session)
        self._user_repo = UserRepository(session)

    @staticmethod
    def _new_order_reference(prefix: str, user_id: int) -> str:
        return f"{prefix}-{user_id}-{uuid.uuid4().hex[:10]}"

    async def create_authorization_invoice(self, user_id: int) -> str:
        """Start card tokenization. Returns the Monobank hosted invoice page URL.

        Monobank's `verification` payment type is a genuine zero-charge hold --
        no need to charge-then-refund like the WayForPay integration this replaces.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise MonobankError(f"User {user_id} does not exist")

        wallet_hint = self._new_order_reference("auth", user_id)
        response = await self._client.create_verification_invoice(
            order_reference=wallet_hint, client_email=user.email
        )

        await self._payment_repo.create(
            user_id=user_id,
            order_reference=response.invoice_id,
            amount=Decimal("0"),
            currency="UAH",
            transaction_type=PaymentTransactionType.AUTHORIZATION,
        )
        return response.page_url

    async def handle_authorization_result(
        self, callback: MonobankInvoiceStatus
    ) -> AuthorizationOutcome:
        """Process the webhook fired after the user completes the hosted invoice."""
        if callback.invoice_id is None:
            logger.warning("Monobank webhook payload is missing invoiceId")
            return AuthorizationOutcome(success=False)

        payment = await self._payment_repo.get_by_order_reference(callback.invoice_id)
        if payment is None:
            logger.warning("Unknown invoiceId in Monobank callback: %s", callback.invoice_id)
            return AuthorizationOutcome(success=False)

        if not callback.is_success:
            if callback.is_final_failure:
                await self._payment_repo.update_status(
                    callback.invoice_id, PaymentStatus.FAILED, raw_response=callback.model_dump()
                )
            return AuthorizationOutcome(success=False, user_id=payment.user_id)

        await self._payment_repo.update_status(
            callback.invoice_id, PaymentStatus.SUCCESS, raw_response=callback.model_dump()
        )

        card_token = callback.wallet_data.card_token if callback.wallet_data else None
        card_mask = callback.payment_info.masked_pan if callback.payment_info else None
        if card_token:
            now = datetime.now(UTC)
            await self._token_repo.deactivate_all_for_user(payment.user_id, now)
            await self._token_repo.create(
                user_id=payment.user_id,
                rec_token=card_token,
                card_mask=card_mask,
                provider="monobank",
            )

        bot_settings = await self._settings_repo.get_or_create()
        trial_start = datetime.now(UTC)
        trial_end = add_days(trial_start, bot_settings.trial_days)

        await self._trial_repo.create(payment.user_id, trial_start, trial_end)
        await self._subscription_repo.get_or_create(payment.user_id)
        await self._subscription_repo.update(
            payment.user_id,
            status=SubscriptionStatus.TRIAL,
            trial_end=trial_end,
            next_charge_at=trial_end,
            retry_count=0,
        )

        return AuthorizationOutcome(success=True, user_id=payment.user_id, trial_end=trial_end)

    async def charge_subscription(
        self, user_id: int, transaction_type: PaymentTransactionType
    ) -> MonobankInvoiceStatus:
        """Synchronously charge the user's saved card (trial-end or renewal).

        Amount is the user's *role* price (`Role.price_uah`) when set -- each
        paid role can have its own price -- falling back to the old single
        global `settings.subscription_price` for anyone whose role has no
        price configured (shouldn't normally happen: such roles are granted
        free access at approval time and never reach a real charge, but this
        keeps the charge from crashing outright if that invariant ever breaks).
        """
        token = await self._token_repo.get_active_by_user(user_id)
        if token is None:
            raise MonobankError(f"User {user_id} has no active payment token")

        user = await self._user_repo.get_by_id(user_id)
        bot_settings = await self._settings_repo.get_or_create()
        amount = (
            user.role.price_uah
            if user and user.role and user.role.price_uah is not None
            else bot_settings.subscription_price
        )
        currency = bot_settings.subscription_currency
        order_reference = self._new_order_reference("charge", user_id)

        await self._payment_repo.create(
            user_id=user_id,
            order_reference=order_reference,
            amount=amount,
            currency=currency,
            transaction_type=transaction_type,
            payment_token_id=token.id,
        )

        response = await self._client.charge_by_token(
            card_token=token.rec_token,
            amount=float(amount),
            currency=currency,
        )

        await self._payment_repo.update_status(
            order_reference,
            PaymentStatus.SUCCESS if response.is_success else PaymentStatus.FAILED,
            provider_transaction_id=response.invoice_id,
            raw_response=response.model_dump(),
        )
        return response
