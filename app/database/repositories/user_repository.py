from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Role, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(
            select(User).options(selectinload(User.role)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(User).options(selectinload(User.role)).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            return user

        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def update_profile(self, user_id: int, **fields: Any) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            return
        for field_name, value in fields.items():
            setattr(user, field_name, value)
        await self._session.flush()

    async def set_admin(self, telegram_id: int, is_admin: bool) -> bool:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            return False
        user.is_admin = is_admin
        await self._session.flush()
        return True

    async def set_banned(self, user_id: int, banned: bool) -> bool:
        user = await self.get_by_id(user_id)
        if user is None:
            return False
        user.is_banned = banned
        await self._session.flush()
        return True

    async def list_admins(self) -> list[User]:
        result = await self._session.execute(
            select(User).where(User.is_admin.is_(True)).order_by(User.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_telegram_ids_by_role(self, role_code: str | None) -> list[int]:
        query = select(User.telegram_id).where(User.is_banned.is_(False))
        if role_code is not None:
            query = query.join(User.role).where(Role.code == role_code)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_with_role(self) -> list[User]:
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.role_id.is_not(None))
            .order_by(User.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_recent(self, limit: int = 20, offset: int = 0) -> list[User]:
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.role))
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def search_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.get_by_telegram_id(telegram_id)

    async def count_total(self) -> int:
        result = await self._session.execute(select(func.count(User.id)))
        return result.scalar_one()
