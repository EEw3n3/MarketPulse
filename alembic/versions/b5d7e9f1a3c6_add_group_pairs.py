"""add productgroup.merged_into_id and the grouppair table (possible duplicates)

Revision ID: b5d7e9f1a3c6
Revises: a2d4f6b8c1e3
Create Date: 2026-11-03 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5d7e9f1a3c6"
down_revision: Union[str, Sequence[str], None] = "a2d4f6b8c1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("productgroup", sa.Column("merged_into_id", sa.Integer(), nullable=True))
    op.create_foreign_key("productgroup_merged_into_id_fkey", "productgroup", "productgroup",
                          ["merged_into_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_productgroup_merged_into_id", "productgroup", ["merged_into_id"])
    op.create_table(
        "grouppair",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_a_id", sa.Integer(), sa.ForeignKey("productgroup.id", ondelete="SET NULL"), nullable=True),
        sa.Column("group_b_id", sa.Integer(), sa.ForeignKey("productgroup.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name_a", sa.String(length=255), nullable=False),
        sa.Column("name_b", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("moved_product_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
    )
    op.create_index("ix_grouppair_group_a_id", "grouppair", ["group_a_id"])
    op.create_index("ix_grouppair_group_b_id", "grouppair", ["group_b_id"])
    op.create_index("ix_grouppair_status", "grouppair", ["status"])


def downgrade() -> None:
    op.drop_index("ix_grouppair_status", table_name="grouppair")
    op.drop_index("ix_grouppair_group_b_id", table_name="grouppair")
    op.drop_index("ix_grouppair_group_a_id", table_name="grouppair")
    op.drop_table("grouppair")
    op.drop_index("ix_productgroup_merged_into_id", table_name="productgroup")
    op.drop_constraint("productgroup_merged_into_id_fkey", "productgroup", type_="foreignkey")
    op.drop_column("productgroup", "merged_into_id")
