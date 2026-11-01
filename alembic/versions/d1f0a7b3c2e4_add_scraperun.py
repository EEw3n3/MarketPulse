"""add scraperun: one row per pass over a shop's catalogue

Revision ID: d1f0a7b3c2e4
Revises: c3e8b1d4f6a2
Create Date: 2026-11-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1f0a7b3c2e4"
down_revision: Union[str, Sequence[str], None] = "c3e8b1d4f6a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Scrape runs, so products a shop stopped listing can be marked sold out."""
    op.create_table(
        "scraperun",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="server"),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("items_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("swept", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_scraperun_shop", "scraperun", ["shop"])
    op.create_index("ix_scraperun_job_id", "scraperun", ["job_id"])
    op.create_index("ix_scraperun_started_at", "scraperun", ["started_at"])
    # The sweep and the freshness checks read a shop's products by last_seen.
    op.create_index("ix_product_search_term_last_seen", "product", ["search_term", "last_seen"])


def downgrade() -> None:
    op.drop_index("ix_product_search_term_last_seen", table_name="product")
    op.drop_index("ix_scraperun_started_at", table_name="scraperun")
    op.drop_index("ix_scraperun_job_id", table_name="scraperun")
    op.drop_index("ix_scraperun_shop", table_name="scraperun")
    op.drop_table("scraperun")
