from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Notification
from app.database.models.enums import NotificationStatus, NotificationType


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        user_id: int,
        notification_type: NotificationType,
        message_text: str,
        status: NotificationStatus = NotificationStatus.SENT,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            message_text=message_text,
            status=status,
        )
        self._session.add(notification)
        await self._session.flush()
        return notification

    async def list_by_user(self, user_id: int, limit: int = 20) -> list[Notification]:
        result = await self._session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.sent_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
