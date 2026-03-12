"""unique_productgroup_name

Revision ID: 7f77443a475a
Revises: c20396e07679
Create Date: 2026-03-12 04:02:30.648754

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f77443a475a'
down_revision: Union[str, Sequence[str], None] = 'c20396e07679'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint to productgroup.name."""
    op.create_unique_constraint("uq_productgroup_name", "productgroup", ["name"])


def downgrade() -> None:
    """Remove unique constraint from productgroup.name."""
    op.drop_constraint("uq_productgroup_name", "productgroup", type_="unique")
