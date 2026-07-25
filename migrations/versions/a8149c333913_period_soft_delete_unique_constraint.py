"""Period soft-delete unique constraint

Revision ID: a8149c333913
Revises: d4a912599210
Create Date: 2026-07-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8149c333913'
down_revision: Union[str, Sequence[str], None] = 'd4a912599210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f('uq_period_site_year_month'), 'reporting_periods', type_='unique')
    op.create_index('uq_period_site_year_month', 'reporting_periods', ['site_id', 'year', 'month'], unique=True, postgresql_where=sa.text('is_deleted = false'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_period_site_year_month', table_name='reporting_periods', postgresql_where=sa.text('is_deleted = false'))
    op.create_unique_constraint(op.f('uq_period_site_year_month'), 'reporting_periods', ['site_id', 'year', 'month'])
