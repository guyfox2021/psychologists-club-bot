from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class KarmaStatistics(Base):
    """One evolving row per user -- their aggregate karma standing."""

    __tablename__ = "karma_statistics"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    karma_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_votes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_votes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<KarmaStatistics user_id={self.user_id} karma_points={self.karma_points}>"
