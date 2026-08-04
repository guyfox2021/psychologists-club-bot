from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Application
from app.database.models.enums import ApplicationStatus


class ApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        role_id: int,
        first_name: str,
        last_name: str,
        phone: str,
        email: str,
        city: str,
    ) -> Application:
        application = Application(
            user_id=user_id,
            role_id=role_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            city=city,
            status=ApplicationStatus.PENDING,
        )
        self._session.add(application)
        await self._session.flush()
        return application

    async def get_by_id(self, application_id: int) -> Application | None:
        result = await self._session.execute(
            select(Application)
            .options(selectinload(Application.documents), selectinload(Application.role))
            .where(Application.id == application_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_by_user_id(self, user_id: int) -> Application | None:
        result = await self._session.execute(
            select(Application)
            .options(selectinload(Application.documents), selectinload(Application.role))
            .where(Application.user_id == user_id)
            .order_by(Application.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_status(
        self, status: ApplicationStatus, limit: int = 20, offset: int = 0
    ) -> list[Application]:
        result = await self._session.execute(
            select(Application)
            .options(selectinload(Application.documents), selectinload(Application.role))
            .where(Application.status == status)
            .order_by(Application.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        application_id: int,
        status: ApplicationStatus,
        admin_comment: str | None = None,
        reviewed_by: int | None = None,
        reviewed_at: datetime | None = None,
    ) -> Application | None:
        application = await self.get_by_id(application_id)
        if application is None:
            return None
        application.status = status
        if admin_comment is not None:
            application.admin_comment = admin_comment
        if reviewed_by is not None:
            application.reviewed_by = reviewed_by
        if reviewed_at is not None:
            application.reviewed_at = reviewed_at
        await self._session.flush()
        return application

    async def count_by_status(self, status: ApplicationStatus) -> int:
        result = await self._session.execute(
            select(func.count(Application.id)).where(Application.status == status)
        )
        return result.scalar_one()

    async def has_approved_application(self, user_id: int) -> bool:
        result = await self._session.execute(
            select(func.count(Application.id)).where(
                Application.user_id == user_id, Application.status == ApplicationStatus.APPROVED
            )
        )
        return result.scalar_one() > 0
