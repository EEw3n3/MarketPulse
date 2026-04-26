"""add favorite (user watchlist) table

Revision ID: d4e7a9c21b88
Revises: b2c8e91a4f72
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e7a9c21b88"
down_revision: Union[str, Sequence[str], None] = "b2c8e91a4f72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create favorite table — per-user watchlist entries pinned to products."""
    op.create_table(
        "favorite",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("product.id"), nullable=False),
        sa.Column("alert_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("price_when_added", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "product_id", name="uq_favorite_user_product"),
    )
    op.create_index("ix_favorite_user_id", "favorite", ["user_id"])
    op.create_index("ix_favorite_product_id", "favorite", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_favorite_product_id", table_name="favorite")
    op.drop_index("ix_favorite_user_id", table_name="favorite")
    op.drop_table("favorite")
