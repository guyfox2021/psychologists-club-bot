from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AdminLog
from app.database.repositories import AdminLogRepository


class AdminLogService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = AdminLogRepository(session)

    async def log(
        self,
        admin_telegram_id: int,
        action: str,
        target_user_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> AdminLog:
        return await self._repo.add(admin_telegram_id, action, target_user_id, details)

    async def list_recent(self, limit: int = 50) -> list[AdminLog]:
        return await self._repo.list_recent(limit)
