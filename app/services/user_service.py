from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.repositories import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        return await self._repo.get_or_create(telegram_id, username, first_name, last_name)

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._repo.get_by_id(user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self._repo.get_by_telegram_id(telegram_id)

    async def is_admin(self, telegram_id: int, super_admin_ids: list[int]) -> bool:
        if telegram_id in super_admin_ids:
            return True
        user = await self._repo.get_by_telegram_id(telegram_id)
        return user is not None and user.is_admin

    async def update_profile(
        self,
        user_id: int,
        first_name: str,
        last_name: str,
        phone: str,
        email: str,
        city: str,
        role_id: int,
    ) -> None:
        await self._repo.update_profile(
            user_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            city=city,
            role_id=role_id,
        )

    async def set_admin(self, telegram_id: int, is_admin: bool) -> bool:
        return await self._repo.set_admin(telegram_id, is_admin)

    async def ban_user(self, user_id: int) -> bool:
        return await self._repo.set_banned(user_id, True)

    async def unban_user(self, user_id: int) -> bool:
        return await self._repo.set_banned(user_id, False)

    async def change_role(self, user_id: int, role_id: int) -> None:
        await self._repo.update_profile(user_id, role_id=role_id)

    async def list_admins(self) -> list[User]:
        return await self._repo.list_admins()

    async def list_all_admin_telegram_ids(self, super_admin_ids: list[int]) -> set[int]:
        admins = await self._repo.list_admins()
        return {admin.telegram_id for admin in admins} | set(super_admin_ids)

    async def list_recent(self, limit: int = 20, offset: int = 0) -> list[User]:
        return await self._repo.list_recent(limit=limit, offset=offset)

    async def search_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self._repo.search_by_telegram_id(telegram_id)

    async def count_total(self) -> int:
        return await self._repo.count_total()
