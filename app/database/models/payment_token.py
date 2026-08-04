from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, CreatedAtMixin


class PaymentToken(CreatedAtMixin, Base):
    __tablename__ = "payment_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    provider: Mapped[str] = mapped_column(String(32), default="monobank", nullable=False)
    rec_token: Mapped[str] = mapped_column(String(255), nullable=False)
    card_mask: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payments: Mapped[list["Payment"]] = relationship(back_populates="payment_token")  # noqa: F821

    def __repr__(self) -> str:
        return f"<PaymentToken id={self.id} user_id={self.user_id} active={self.is_active}>"
