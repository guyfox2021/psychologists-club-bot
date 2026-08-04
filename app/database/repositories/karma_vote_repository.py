from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import KarmaVote
from app.database.models.enums import KarmaReactionType


class KarmaVoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, message_id: int, voter_user_id: int) -> KarmaVote | None:
        result = await self._session.execute(
            select(KarmaVote).where(
                KarmaVote.message_id == message_id, KarmaVote.voter_user_id == voter_user_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        message_id: int,
        chat_id: int,
        author_user_id: int,
        voter_user_id: int,
        reaction_type: KarmaReactionType,
    ) -> None:
        stmt = insert(KarmaVote).values(
            message_id=message_id,
            chat_id=chat_id,
            author_user_id=author_user_id,
            voter_user_id=voter_user_id,
            reaction_type=reaction_type,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["message_id", "voter_user_id"],
            set_={"reaction_type": reaction_type},
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete(self, message_id: int, voter_user_id: int) -> None:
        await self._session.execute(
            delete(KarmaVote).where(
                KarmaVote.message_id == message_id, KarmaVote.voter_user_id == voter_user_id
            )
        )
        await self._session.flush()
