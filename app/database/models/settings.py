from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BotSettings(Base):
    """Single-row table holding business-tunable, admin-configurable settings.

    Named `BotSettings` in code (table is still `settings`, per spec) to avoid
    clashing with `app.config.Settings`, the infra-level env configuration.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    trial_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    subscription_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    subscription_currency: Mapped[str] = mapped_column(String(8), default="UAH", nullable=False)
    subscription_duration_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    reminder_days_before: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), default=list, nullable=False
    )
    community_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<BotSettings trial_days={self.trial_days} price={self.subscription_price}>"
