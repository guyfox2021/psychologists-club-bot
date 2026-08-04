from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Trial


class TrialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: int, trial_start: datetime, trial_end: datetime) -> Trial:
        trial = Trial(user_id=user_id, trial_start=trial_start, trial_end=trial_end)
        self._session.add(trial)
        await self._session.flush()
        return trial

    async def get_latest_by_user(self, user_id: int) -> Trial | None:
        result = await self._session.execute(
            select(Trial)
            .where(Trial.user_id == user_id)
            .order_by(Trial.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_converted(self, trial_id: int) -> None:
        result = await self._session.execute(select(Trial).where(Trial.id == trial_id))
        trial = result.scalar_one_or_none()
        if trial is not None:
            trial.converted_to_subscription = True
            await self._session.flush()
