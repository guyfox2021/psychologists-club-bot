from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MessageFeedback(Base):
    """One row per tracked message from an eligible author -- lets the
    `message_reaction` handler resolve "who wrote this message" (the Bot API
    has no way to fetch a message's author after the fact) and holds the
    running 🤝/👎 totals used for the negative-feedback admin alert.
    """

    __tablename__ = "message_feedback"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<MessageFeedback message_id={self.message_id} chat_id={self.chat_id}>"
