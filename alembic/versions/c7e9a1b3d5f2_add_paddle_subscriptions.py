"""add the subscription and paddleevent tables (card payments through Paddle)

Revision ID: c7e9a1b3d5f2
Revises: b5d7e9f1a3c6
Create Date: 2026-11-04 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e9a1b3d5f2"
down_revision: Union[str, Sequence[str], None] = "b5d7e9f1a3c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("paddle_subscription_id", sa.String(length=64), nullable=False),
        sa.Column("paddle_customer_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("term", sa.String(length=8), nullable=True),
        sa.Column("price_id", sa.String(length=64), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at", sa.DateTime(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_subscription_user_id", "subscription", ["user_id"])
    op.create_index("ix_subscription_paddle_subscription_id", "subscription", ["paddle_subscription_id"], unique=True)
    op.create_table(
        "paddleevent",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("subscription_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("result", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("paddleevent")
    op.drop_index("ix_subscription_paddle_subscription_id", table_name="subscription")
    op.drop_index("ix_subscription_user_id", table_name="subscription")
    op.drop_table("subscription")
