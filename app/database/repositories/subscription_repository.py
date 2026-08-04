from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Subscription
from app.database.models.enums import SubscriptionStatus


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: int) -> Subscription | None:
        result = await self._session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(Subscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int) -> Subscription:
        subscription = await self.get_by_user_id(user_id)
        if subscription is not None:
            return subscription

        subscription = Subscription(user_id=user_id, status=SubscriptionStatus.WAITING)
        self._session.add(subscription)
        await self._session.flush()
        return subscription

    async def update(self, user_id: int, **fields: Any) -> Subscription | None:
        subscription = await self.get_by_user_id(user_id)
        if subscription is None:
            return None
        for field_name, value in fields.items():
            setattr(subscription, field_name, value)
        await self._session.flush()
        return subscription

    async def list_by_status(self, status: SubscriptionStatus) -> list[Subscription]:
        result = await self._session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(Subscription.status == status)
            .order_by(Subscription.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_due_for_charge(self, before: datetime) -> list[Subscription]:
        # FAILED is included so a previously failed charge keeps retrying
        # automatically on its next scheduled attempt (see SubscriptionService).
        result = await self._session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(
                Subscription.status.in_(
                    [
                        SubscriptionStatus.TRIAL,
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.FAILED,
                    ]
                ),
                Subscription.next_charge_at.is_not(None),
                Subscription.next_charge_at <= before,
            )
        )
        return list(result.scalars().all())

    async def count_by_status(self, status: SubscriptionStatus) -> int:
        result = await self._session.execute(
            select(func.count(Subscription.id)).where(Subscription.status == status)
        )
        return result.scalar_one()
