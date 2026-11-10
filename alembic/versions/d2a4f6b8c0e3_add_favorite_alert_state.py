"""favorite: the price and stock state the user was last told about (daily alert digest)

Revision ID: d2a4f6b8c0e3
Revises: c7e9a1b3d5f2
Create Date: 2026-11-10 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2a4f6b8c0e3"
down_revision: Union[str, Sequence[str], None] = "c7e9a1b3d5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """The daily digest compares today's price with the one in the last message,
    so a price that jumps up and back down between two digests sends nothing.
    Skips columns that already exist: a code rollback keeps them (it only
    re-stamps the version), so a second deploy must not fail on them."""
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("favorite")}
    for col in (
        sa.Column("last_alert_price", sa.Numeric(), nullable=True),
        sa.Column("last_alert_in_stock", sa.Boolean(), nullable=True),
        sa.Column("last_alert_at", sa.DateTime(), nullable=True),
    ):
        if col.name not in have:
            op.add_column("favorite", col)


def downgrade() -> None:
    op.drop_column("favorite", "last_alert_at")
    op.drop_column("favorite", "last_alert_in_stock")
    op.drop_column("favorite", "last_alert_price")
