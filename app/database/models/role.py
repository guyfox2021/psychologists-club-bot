from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    label_uk: Mapped[str] = mapped_column(String(64), nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="role")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Role id={self.id} code={self.code!r}>"
