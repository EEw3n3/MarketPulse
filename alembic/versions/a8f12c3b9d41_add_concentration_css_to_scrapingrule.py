"""add concentration_css to scrapingrule

Revision ID: a8f12c3b9d41
Revises: 7f77443a475a
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8f12c3b9d41'
down_revision: Union[str, Sequence[str], None] = '7f77443a475a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable concentration_css column to scrapingrule."""
    op.add_column(
        "scrapingrule",
        sa.Column("concentration_css", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Drop concentration_css column from scrapingrule."""
    op.drop_column("scrapingrule", "concentration_css")
