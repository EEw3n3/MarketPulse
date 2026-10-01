"""add promo_price and promo_code to product

Revision ID: a7c4e2d9b1f3
Revises: f5a1c3d9e2b7
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c4e2d9b1f3"
down_revision: Union[str, Sequence[str], None] = "f5a1c3d9e2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Price with a shop promo code, kept next to the regular last_price."""
    op.add_column("product", sa.Column("promo_price", sa.Numeric(), nullable=True))
    op.add_column("product", sa.Column("promo_code", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("product", "promo_code")
    op.drop_column("product", "promo_price")
