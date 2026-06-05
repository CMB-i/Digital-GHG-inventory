"""add description to value sets

Revision ID: 885806e02f47
Revises: d0ada23f61b0
Create Date: 2026-06-05 19:19:55.153543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '885806e02f47'
down_revision: Union[str, Sequence[str], None] = 'd0ada23f61b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "value_sets",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("value_sets", "description")