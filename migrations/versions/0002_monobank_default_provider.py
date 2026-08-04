"""payment_tokens.provider default -> monobank

Revision ID: 0002_monobank_provider
Revises: 0001_initial
Create Date: 2026-07-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_monobank_provider"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "payment_tokens",
        "provider",
        existing_type=sa.String(length=32),
        server_default="monobank",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "payment_tokens",
        "provider",
        existing_type=sa.String(length=32),
        server_default="wayforpay",
        existing_nullable=False,
    )
