"""add user.google_sub; the password becomes optional (Google sign-in)

Revision ID: a2d4f6b8c1e3
Revises: f8c3a5e1b7d2
Create Date: 2026-11-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2d4f6b8c1e3"
down_revision: Union[str, Sequence[str], None] = "f8c3a5e1b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.create_index("ix_user_google_sub", "user", ["google_sub"], unique=True)
    op.alter_column("user", "hashed_password", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Accounts without a password get an unusable one (nobody can sign in with it).
    op.execute("update \"user\" set hashed_password = '!' where hashed_password is null")
    op.alter_column("user", "hashed_password", existing_type=sa.String(), nullable=False)
    op.drop_index("ix_user_google_sub", table_name="user")
    op.drop_column("user", "google_sub")
