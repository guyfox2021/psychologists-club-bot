from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    label_uk: Mapped[str] = mapped_column(String(64), nullable=False)
    # NULL = this role always gets free access, regardless of PAYMENT_REQUIRED
    # (e.g. Supervisor, and Psychologist until/unless the client wants to
    # charge that tier too). Set = the subscription price charged after trial.
    price_uah: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    users: Mapped[list["User"]] = relationship(back_populates="role")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Role id={self.id} code={self.code!r}>"
