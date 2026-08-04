from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Application
from app.database.models.enums import ApplicationStatus, UserRoleCode
from app.database.repositories import ApplicationRepository, RoleRepository


class ApplicationService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ApplicationRepository(session)
        self._role_repo = RoleRepository(session)

    async def create_application(
        self,
        user_id: int,
        role_code: UserRoleCode,
        first_name: str,
        last_name: str,
        phone: str,
        email: str,
        city: str,
    ) -> Application:
        role = await self._role_repo.get_by_code(role_code)
        if role is None:
            raise ValueError(f"Role {role_code} is not seeded in the database")
        return await self._repo.create(
            user_id=user_id,
            role_id=role.id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            city=city,
        )

    async def get_application(self, application_id: int) -> Application | None:
        return await self._repo.get_by_id(application_id)

    async def get_latest_for_user(self, user_id: int) -> Application | None:
        return await self._repo.get_latest_by_user_id(user_id)

    async def list_pending(self, limit: int = 20, offset: int = 0) -> list[Application]:
        return await self._repo.list_by_status(ApplicationStatus.PENDING, limit, offset)

    async def approve(
        self, application_id: int, admin_telegram_id: int, reviewed_at: datetime
    ) -> Application | None:
        return await self._repo.update_status(
            application_id,
            ApplicationStatus.APPROVED,
            reviewed_by=admin_telegram_id,
            reviewed_at=reviewed_at,
        )

    async def reject(
        self,
        application_id: int,
        admin_telegram_id: int,
        reason: str,
        reviewed_at: datetime,
    ) -> Application | None:
        return await self._repo.update_status(
            application_id,
            ApplicationStatus.REJECTED,
            admin_comment=reason,
            reviewed_by=admin_telegram_id,
            reviewed_at=reviewed_at,
        )

    async def request_more_documents(
        self,
        application_id: int,
        admin_telegram_id: int,
        comment: str,
        reviewed_at: datetime,
    ) -> Application | None:
        return await self._repo.update_status(
            application_id,
            ApplicationStatus.NEED_MORE_DOCS,
            admin_comment=comment,
            reviewed_by=admin_telegram_id,
            reviewed_at=reviewed_at,
        )

    async def resubmit(self, application_id: int) -> Application | None:
        return await self._repo.update_status(application_id, ApplicationStatus.PENDING)

    async def count_pending(self) -> int:
        return await self._repo.count_by_status(ApplicationStatus.PENDING)
