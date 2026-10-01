"""add card_type to product

Revision ID: f5a1c3d9e2b7
Revises: e3f1a2b7c904
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a1c3d9e2b7"
down_revision: Union[str, Sequence[str], None] = "e3f1a2b7c904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add product.card_type ("perfume" | "gift_set")."""
    op.add_column("product", sa.Column("card_type", sa.String(), nullable=False, server_default="perfume"))
    op.create_index("ix_product_card_type", "product", ["card_type"])


def downgrade() -> None:
    op.drop_index("ix_product_card_type", table_name="product")
    op.drop_column("product", "card_type")
