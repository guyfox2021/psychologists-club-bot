from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import PaymentToken


class PaymentTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        rec_token: str,
        card_mask: str | None = None,
        provider: str = "monobank",
    ) -> PaymentToken:
        token = PaymentToken(
            user_id=user_id, rec_token=rec_token, card_mask=card_mask, provider=provider
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_active_by_user(self, user_id: int) -> PaymentToken | None:
        result = await self._session.execute(
            select(PaymentToken)
            .where(PaymentToken.user_id == user_id, PaymentToken.is_active.is_(True))
            .order_by(PaymentToken.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def deactivate(self, token_id: int, revoked_at: datetime) -> None:
        result = await self._session.execute(
            select(PaymentToken).where(PaymentToken.id == token_id)
        )
        token = result.scalar_one_or_none()
        if token is not None:
            token.is_active = False
            token.revoked_at = revoked_at
            await self._session.flush()

    async def deactivate_all_for_user(self, user_id: int, revoked_at: datetime) -> None:
        result = await self._session.execute(
            select(PaymentToken).where(
                PaymentToken.user_id == user_id, PaymentToken.is_active.is_(True)
            )
        )
        for token in result.scalars().all():
            token.is_active = False
            token.revoked_at = revoked_at
        await self._session.flush()
