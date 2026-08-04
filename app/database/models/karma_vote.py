from sqlalchemy import BigInteger, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin
from app.database.models.enums import KarmaReactionType


class KarmaVote(TimestampMixin, Base):
    """One row per (message, voter) -- the voter's current 🤝/👎 reaction.

    Updated in place when a reaction changes, deleted when removed, so this
    table always mirrors Telegram's own current reaction state exactly.
    """

    __tablename__ = "karma_votes"
    __table_args__ = (
        UniqueConstraint("message_id", "voter_user_id", name="uq_karma_votes_message_voter"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    voter_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reaction_type: Mapped[KarmaReactionType] = mapped_column(
        Enum(KarmaReactionType, name="karma_reaction_type", native_enum=False), nullable=False
    )

    def __repr__(self) -> str:
        return f"<KarmaVote message_id={self.message_id} voter_user_id={self.voter_user_id}>"
