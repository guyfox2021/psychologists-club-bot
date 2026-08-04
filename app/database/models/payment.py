from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.database.models.enums import PaymentStatus, PaymentTransactionType


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payment_token_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_tokens.id"), nullable=True
    )

    order_reference: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="UAH", nullable=False)

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", native_enum=False),
        default=PaymentStatus.WAITING,
        nullable=False,
        index=True,
    )
    transaction_type: Mapped[PaymentTransactionType] = mapped_column(
        Enum(PaymentTransactionType, name="payment_transaction_type", native_enum=False),
        nullable=False,
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    payment_token: Mapped["PaymentToken | None"] = relationship(  # noqa: F821
        back_populates="payments"
    )

    def __repr__(self) -> str:
        return f"<Payment id={self.id} order_reference={self.order_reference!r} status={self.status}>"
