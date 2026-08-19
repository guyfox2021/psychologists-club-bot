from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Role
from app.database.models.enums import UserRoleCode


class RoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: UserRoleCode | str) -> Role | None:
        code_value = code.value if isinstance(code, UserRoleCode) else code
        result = await self._session.execute(select(Role).where(Role.code == code_value))
        return result.scalar_one_or_none()

    async def get_by_id(self, role_id: int) -> Role | None:
        result = await self._session.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Role]:
        result = await self._session.execute(select(Role).order_by(Role.id.asc()))
        return list(result.scalars().all())

    async def update_price(self, role_id: int, price: Decimal | None) -> Role | None:
        role = await self.get_by_id(role_id)
        if role is None:
            return None
        role.price_uah = price
        await self._session.flush()
        return role
