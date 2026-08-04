from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AdminLog


class AdminLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        admin_telegram_id: int,
        action: str,
        target_user_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> AdminLog:
        log_entry = AdminLog(
            admin_telegram_id=admin_telegram_id,
            action=action,
            target_user_id=target_user_id,
            details=details,
        )
        self._session.add(log_entry)
        await self._session.flush()
        return log_entry

    async def list_recent(self, limit: int = 50) -> list[AdminLog]:
        result = await self._session.execute(
            select(AdminLog).order_by(AdminLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
