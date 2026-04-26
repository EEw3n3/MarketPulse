"""add notification preferences to userpreferences

Revision ID: e3f1a2b7c904
Revises: d4e7a9c21b88
Create Date: 2026-04-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f1a2b7c904"
down_revision: Union[str, Sequence[str], None] = "d4e7a9c21b88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add notification channel fields to userpreferences."""
    op.add_column("userpreferences", sa.Column("notification_channels", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("userpreferences", sa.Column("notification_threshold_percent", sa.Numeric(precision=5, scale=2), nullable=False, server_default="5.00"))
    op.add_column("userpreferences", sa.Column("telegram_chat_id", sa.String(length=64), nullable=True))
    op.add_column("userpreferences", sa.Column("telegram_link_token", sa.String(length=64), nullable=True))
    op.add_column("userpreferences", sa.Column("telegram_link_token_expires_at", sa.DateTime(), nullable=True))
    op.create_index("ix_userpreferences_telegram_chat_id", "userpreferences", ["telegram_chat_id"])
    op.create_index("ix_userpreferences_telegram_link_token", "userpreferences", ["telegram_link_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_userpreferences_telegram_link_token", table_name="userpreferences")
    op.drop_index("ix_userpreferences_telegram_chat_id", table_name="userpreferences")
    op.drop_column("userpreferences", "telegram_link_token_expires_at")
    op.drop_column("userpreferences", "telegram_link_token")
    op.drop_column("userpreferences", "telegram_chat_id")
    op.drop_column("userpreferences", "notification_threshold_percent")
    op.drop_column("userpreferences", "notification_channels")
