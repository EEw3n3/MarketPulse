"""add user.plan, favorite.alert_threshold_percent and history/group indexes

Revision ID: c3e8b1d4f6a2
Revises: a7c4e2d9b1f3
Create Date: 2026-10-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e8b1d4f6a2"
down_revision: Union[str, Sequence[str], None] = "a7c4e2d9b1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Free/Pro plan per user and an alert threshold per watched bottle."""
    op.add_column("user", sa.Column("plan", sa.String(length=16), nullable=False, server_default="free"))
    op.add_column("favorite", sa.Column("alert_threshold_percent", sa.Numeric(), nullable=True))
    # Product pages, favorites and the catalogue read a bottle's history by
    # product_id; the table had only its primary key.
    op.create_index("ix_pricehistory_product_id_parsed_at", "pricehistory", ["product_id", "parsed_at"])
    op.create_index("ix_product_group_id", "product", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_product_group_id", table_name="product")
    op.drop_index("ix_pricehistory_product_id_parsed_at", table_name="pricehistory")
    op.drop_column("favorite", "alert_threshold_percent")
    op.drop_column("user", "plan")
