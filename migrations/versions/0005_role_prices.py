"""per-role subscription price (student, psychologist_starter)

Revision ID: 0005_role_prices
Revises: 0004_psychologist_starter
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_role_prices"
down_revision: Union[str, None] = "0004_psychologist_starter"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

roles_table = sa.table(
    "roles",
    sa.column("code", sa.String()),
    sa.column("price_uah", sa.Numeric(10, 2)),
)

# $5 / $7 converted to UAH at ~45 UAH/USD (Monobank's own published rate at
# the time this was set up), rounded to a clean number. Adjust directly in
# the DB (or via a future /settings UI) if the rate/pricing changes.
_PRICES = {"student": 225, "psychologist_starter": 315}


def upgrade() -> None:
    op.add_column("roles", sa.Column("price_uah", sa.Numeric(10, 2), nullable=True))
    for code, price in _PRICES.items():
        op.execute(
            roles_table.update().where(roles_table.c.code == code).values(price_uah=price)
        )


def downgrade() -> None:
    op.drop_column("roles", "price_uah")
