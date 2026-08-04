from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis

_THROTTLE_WINDOW_MS = 700


class ThrottlingMiddleware(BaseMiddleware):
    """Drops updates from the same user that arrive faster than the throttle window.

    Uses Redis (`SET key value NX PX`) so the limit holds across process restarts and,
    if ever scaled out, across multiple bot instances sharing the same Redis.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        key = f"throttle:{user.id}"
        allowed = await self._redis.set(key, "1", nx=True, px=_THROTTLE_WINDOW_MS)
        if not allowed:
            return None

        return await handler(event, data)
