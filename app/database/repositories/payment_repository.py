from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Payment
from app.database.models.enums import PaymentStatus, PaymentTransactionType


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        order_reference: str,
        amount: Decimal,
        currency: str,
        transaction_type: PaymentTransactionType,
        payment_token_id: int | None = None,
        status: PaymentStatus = PaymentStatus.WAITING,
    ) -> Payment:
        payment = Payment(
            user_id=user_id,
            order_reference=order_reference,
            amount=amount,
            currency=currency,
            transaction_type=transaction_type,
            payment_token_id=payment_token_id,
            status=status,
        )
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def get_by_order_reference(self, order_reference: str) -> Payment | None:
        result = await self._session.execute(
            select(Payment)
            .options(selectinload(Payment.payment_token))
            .where(Payment.order_reference == order_reference)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        order_reference: str,
        status: PaymentStatus,
        provider_transaction_id: str | None = None,
        raw_response: dict | None = None,
    ) -> Payment | None:
        payment = await self.get_by_order_reference(order_reference)
        if payment is None:
            return None
        payment.status = status
        if provider_transaction_id is not None:
            payment.provider_transaction_id = provider_transaction_id
        if raw_response is not None:
            payment.raw_response = raw_response
        await self._session.flush()
        return payment

    async def list_by_user(self, user_id: int, limit: int = 20, offset: int = 0) -> list[Payment]:
        result = await self._session.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_recent(self, limit: int = 20, offset: int = 0) -> list[Payment]:
        result = await self._session.execute(
            select(Payment).order_by(Payment.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def sum_amount_by_status(self, status: PaymentStatus) -> Decimal:
        result = await self._session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == status)
        )
        return result.scalar_one()

    async def count_by_status(self, status: PaymentStatus) -> int:
        result = await self._session.execute(
            select(func.count(Payment.id)).where(Payment.status == status)
        )
        return result.scalar_one()
