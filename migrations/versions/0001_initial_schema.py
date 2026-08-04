"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- roles ---------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label_uk", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_index("ix_roles_code", "roles", ["code"])

    # --- users -----------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=True),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    # --- applications ------------------------------------------------------------
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "approved", "rejected", "need_more_docs",
                name="application_status", native_enum=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_status", "applications", ["status"])

    # --- documents -------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "application_id", sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=False),
        sa.Column("telegram_file_unique_id", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_application_id", "documents", ["application_id"])

    # --- payment_tokens -------------------------------------------------------------
    op.create_table(
        "payment_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="wayforpay"),
        sa.Column("rec_token", sa.String(length=255), nullable=False),
        sa.Column("card_mask", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_tokens_user_id", "payment_tokens", ["user_id"])

    # --- payments -----------------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_token_id", sa.Integer(), sa.ForeignKey("payment_tokens.id"), nullable=True),
        sa.Column("order_reference", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="UAH"),
        sa.Column(
            "status",
            sa.Enum(
                "waiting", "success", "failed", "refunded", "cancelled",
                name="payment_status", native_enum=False,
            ),
            nullable=False,
            server_default="waiting",
        ),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "authorization", "trial_charge", "renewal_charge",
                name="payment_transaction_type", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("provider_transaction_id", sa.String(length=255), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("order_reference", name="uq_payments_order_reference"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_order_reference", "payments", ["order_reference"])
    op.create_index("ix_payments_status", "payments", ["status"])

    # --- trials -----------------------------------------------------------------
    op.create_table(
        "trials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trial_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("converted_to_subscription", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trials_user_id", "trials", ["user_id"])

    # --- subscriptions -------------------------------------------------------------
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "waiting", "trial", "active", "expired", "failed", "cancelled",
                name="subscription_status", native_enum=False,
            ),
            nullable=False,
            server_default="waiting",
        ),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_charge_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invite_link", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_subscriptions_user_id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    # --- notifications -------------------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "reminder_3d", "reminder_1d", "payment_failed", "access_restored",
                "application_status", "broadcast",
                name="notification_type", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("sent", "failed", name="notification_status", native_enum=False),
            nullable=False,
            server_default="sent",
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    # --- admin_logs -------------------------------------------------------------
    op.create_table(
        "admin_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column(
            "target_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_logs_admin_telegram_id", "admin_logs", ["admin_telegram_id"])

    # --- settings -----------------------------------------------------------------
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("subscription_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("subscription_currency", sa.String(length=8), nullable=False, server_default="UAH"),
        sa.Column("subscription_duration_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "reminder_days_before", postgresql.ARRAY(sa.Integer()),
            nullable=False, server_default="{3,1}",
        ),
        sa.Column("community_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- seed data -----------------------------------------------------------------
    roles_table = sa.table(
        "roles",
        sa.column("code", sa.String()),
        sa.column("label_uk", sa.String()),
    )
    op.bulk_insert(
        roles_table,
        [
            {"code": "student", "label_uk": "Студент"},
            {"code": "psychologist", "label_uk": "Психолог"},
            {"code": "supervisor", "label_uk": "Супервізор"},
        ],
    )

    settings_table = sa.table(
        "settings",
        sa.column("trial_days", sa.Integer()),
        sa.column("subscription_price", sa.Numeric(10, 2)),
        sa.column("subscription_currency", sa.String()),
        sa.column("subscription_duration_days", sa.Integer()),
        sa.column("reminder_days_before", postgresql.ARRAY(sa.Integer())),
    )
    op.bulk_insert(
        settings_table,
        [
            {
                "trial_days": 14,
                "subscription_price": 500,
                "subscription_currency": "UAH",
                "subscription_duration_days": 30,
                "reminder_days_before": [3, 1],
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_admin_logs_admin_telegram_id", table_name="admin_logs")
    op.drop_table("admin_logs")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_trials_user_id", table_name="trials")
    op.drop_table("trials")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_order_reference", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_payment_tokens_user_id", table_name="payment_tokens")
    op.drop_table("payment_tokens")
    op.drop_index("ix_documents_application_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_user_id", table_name="applications")
    op.drop_table("applications")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_table("roles")
