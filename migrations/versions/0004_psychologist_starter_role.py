"""add 'psychologist_starter' role

Revision ID: 0004_psychologist_starter
Revises: 0003_karma_system
Create Date: 2026-08-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_psychologist_starter"
down_revision: Union[str, None] = "0003_karma_system"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

roles_table = sa.table(
    "roles",
    sa.column("code", sa.String()),
    sa.column("label_uk", sa.String()),
)


def upgrade() -> None:
    op.bulk_insert(
        roles_table,
        [{"code": "psychologist_starter", "label_uk": "Психолог на старті"}],
    )


def downgrade() -> None:
    op.execute(roles_table.delete().where(roles_table.c.code == "psychologist_starter"))
