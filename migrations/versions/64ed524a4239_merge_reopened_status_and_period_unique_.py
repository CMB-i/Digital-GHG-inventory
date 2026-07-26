"""merge_reopened_status_and_period_unique_heads

Revision ID: 64ed524a4239
Revises: 4e52328f2156, a8149c333913
Create Date: 2026-07-26 21:06:24.604368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64ed524a4239'
down_revision: Union[str, Sequence[str], None] = ('4e52328f2156', 'a8149c333913')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
