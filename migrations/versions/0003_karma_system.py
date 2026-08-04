"""karma system: karma_votes, karma_statistics, message_feedback

Revision ID: 0003_karma_system
Revises: 0002_monobank_provider
Create Date: 2026-08-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_karma_system"
down_revision: Union[str, None] = "0002_monobank_provider"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "karma_votes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "author_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "voter_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "reaction_type",
            sa.Enum("helped", "not_helped", name="karma_reaction_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("message_id", "voter_user_id", name="uq_karma_votes_message_voter"),
    )
    op.create_index("ix_karma_votes_message_id", "karma_votes", ["message_id"])
    op.create_index("ix_karma_votes_author_user_id", "karma_votes", ["author_user_id"])
    op.create_index("ix_karma_votes_voter_user_id", "karma_votes", ["voter_user_id"])

    op.create_table(
        "karma_statistics",
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("karma_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("positive_votes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("negative_votes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "message_feedback",
        sa.Column("message_id", sa.BigInteger(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "author_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("positive_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("negative_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_message_feedback_author_user_id", "message_feedback", ["author_user_id"])


def downgrade() -> None:
    op.drop_index("ix_message_feedback_author_user_id", table_name="message_feedback")
    op.drop_table("message_feedback")
    op.drop_table("karma_statistics")
    op.drop_index("ix_karma_votes_voter_user_id", table_name="karma_votes")
    op.drop_index("ix_karma_votes_author_user_id", table_name="karma_votes")
    op.drop_index("ix_karma_votes_message_id", table_name="karma_votes")
    op.drop_table("karma_votes")
