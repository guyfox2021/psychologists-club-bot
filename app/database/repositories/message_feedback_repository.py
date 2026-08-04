from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MessageFeedback


class MessageFeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, chat_id: int, message_id: int) -> MessageFeedback | None:
        result = await self._session.execute(
            select(MessageFeedback).where(
                MessageFeedback.chat_id == chat_id, MessageFeedback.message_id == message_id
            )
        )
        return result.scalar_one_or_none()

    async def ensure_tracked(self, chat_id: int, message_id: int, author_user_id: int) -> MessageFeedback:
        feedback = await self.get(chat_id, message_id)
        if feedback is not None:
            return feedback

        feedback = MessageFeedback(
            chat_id=chat_id, message_id=message_id, author_user_id=author_user_id
        )
        self._session.add(feedback)
        await self._session.flush()
        return feedback

    async def adjust_counts(
        self, chat_id: int, message_id: int, positive_delta: int = 0, negative_delta: int = 0
    ) -> MessageFeedback | None:
        feedback = await self.get(chat_id, message_id)
        if feedback is None:
            return None
        feedback.positive_count += positive_delta
        feedback.negative_count += negative_delta
        await self._session.flush()
        return feedback
