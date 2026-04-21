"""add user and userpreferences tables

Revision ID: b2c8e91a4f72
Revises: a8f12c3b9d41
Create Date: 2026-04-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c8e91a4f72"
down_revision: Union[str, Sequence[str], None] = "a8f12c3b9d41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user + userpreferences tables for JWT auth + onboarding state."""
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "userpreferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("monitored_stores", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("interested_brands", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_userpreferences_user_id", "userpreferences", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_userpreferences_user_id", table_name="userpreferences")
    op.drop_table("userpreferences")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
