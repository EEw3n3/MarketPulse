"""add product.page_checked_at / page_price and the pagecheck table

Revision ID: e7b2c4d8f1a9
Revises: d1f0a7b3c2e4
Create Date: 2026-11-01 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b2c4d8f1a9"
down_revision: Union[str, Sequence[str], None] = "d1f0a7b3c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Deals are read again on the shop's product page before they are shown."""
    op.add_column("product", sa.Column("page_checked_at", sa.DateTime(), nullable=True))
    op.add_column("product", sa.Column("page_price", sa.Numeric(), nullable=True))
    op.create_table(
        "pagecheck",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("product.id", ondelete="CASCADE"), nullable=True),
        sa.Column("shop", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="deal"),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("db_price", sa.Numeric(), nullable=True),
        sa.Column("page_price", sa.Numeric(), nullable=True),
        sa.Column("db_in_stock", sa.Boolean(), nullable=True),
        sa.Column("page_in_stock", sa.Boolean(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_pagecheck_product_id", "pagecheck", ["product_id"])
    op.create_index("ix_pagecheck_shop", "pagecheck", ["shop"])
    op.create_index("ix_pagecheck_checked_at", "pagecheck", ["checked_at"])


def downgrade() -> None:
    op.drop_index("ix_pagecheck_checked_at", table_name="pagecheck")
    op.drop_index("ix_pagecheck_shop", table_name="pagecheck")
    op.drop_index("ix_pagecheck_product_id", table_name="pagecheck")
    op.drop_table("pagecheck")
    op.drop_column("product", "page_price")
    op.drop_column("product", "page_checked_at")
