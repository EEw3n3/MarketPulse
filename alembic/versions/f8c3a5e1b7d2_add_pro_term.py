"""add user.pro_until / pro_source and the planchange log

Revision ID: f8c3a5e1b7d2
Revises: e7b2c4d8f1a9
Create Date: 2026-11-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8c3a5e1b7d2"
down_revision: Union[str, Sequence[str], None] = "e7b2c4d8f1a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Pro gets an end date; every change of plan is logged."""
    op.add_column("user", sa.Column("pro_until", sa.DateTime(), nullable=True))
    op.add_column("user", sa.Column("pro_source", sa.String(length=16), nullable=True))
    # Pro given by hand so far: keep it, without an end, as given by an admin.
    op.execute("update \"user\" set pro_source = 'admin' where plan = 'pro'")
    op.create_table(
        "planchange",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("by_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("plan", sa.String(length=16), nullable=False),
        sa.Column("pro_until", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_planchange_user_id", "planchange", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_planchange_user_id", table_name="planchange")
    op.drop_table("planchange")
    op.drop_column("user", "pro_source")
    op.drop_column("user", "pro_until")
