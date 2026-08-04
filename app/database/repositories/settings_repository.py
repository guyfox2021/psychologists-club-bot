from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import BotSettings


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self) -> BotSettings:
        result = await self._session.execute(select(BotSettings).limit(1))
        settings = result.scalar_one_or_none()
        if settings is not None:
            return settings

        # Defensive fallback: the initial migration always seeds one row,
        # but a fresh/non-migrated DB should still not crash the bot.
        settings = BotSettings()
        self._session.add(settings)
        await self._session.flush()
        return settings

    async def update(self, **fields: Any) -> BotSettings:
        settings = await self.get_or_create()
        for field_name, value in fields.items():
            setattr(settings, field_name, value)
        await self._session.flush()
        return settings
