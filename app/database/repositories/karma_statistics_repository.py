from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import KarmaStatistics


class KarmaStatisticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, user_id: int) -> KarmaStatistics:
        result = await self._session.execute(
            select(KarmaStatistics).where(KarmaStatistics.user_id == user_id)
        )
        stats = result.scalar_one_or_none()
        if stats is not None:
            return stats

        stats = KarmaStatistics(user_id=user_id)
        self._session.add(stats)
        await self._session.flush()
        return stats

    async def adjust(
        self,
        user_id: int,
        karma_delta: int = 0,
        positive_delta: int = 0,
        negative_delta: int = 0,
    ) -> KarmaStatistics:
        stats = await self.get_or_create(user_id)
        stats.karma_points += karma_delta
        stats.positive_votes += positive_delta
        stats.negative_votes += negative_delta
        await self._session.flush()
        return stats

    async def get_by_id(self, user_id: int) -> KarmaStatistics | None:
        result = await self._session.execute(
            select(KarmaStatistics).where(KarmaStatistics.user_id == user_id)
        )
        return result.scalar_one_or_none()
