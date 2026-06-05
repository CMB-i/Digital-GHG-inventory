"""merge audit and phase 5 migration heads

Revision ID: d0ada23f61b0
Revises: 758951d0c858, 8d4f2b7c91a0
Create Date: 2026-06-05 19:18:05.536647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0ada23f61b0'
down_revision: Union[str, Sequence[str], None] = ('758951d0c858', '8d4f2b7c91a0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
