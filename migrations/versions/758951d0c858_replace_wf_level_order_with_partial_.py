"""replace_wf_level_order_with_partial_index

Revision ID: 758951d0c858
Revises: 668b2e9d1d97
Create Date: 2026-06-05 13:04:04.439463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '758951d0c858'
down_revision: Union[str, Sequence[str], None] = '668b2e9d1d97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('uq_wf_level_order', 'workflow_levels', type_='unique')
    op.create_index('uq_wf_level_order', 'workflow_levels', ['workflow_version_id', 'level_number'], unique=True, postgresql_where=sa.text('is_deleted = false'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_wf_level_order', table_name='workflow_levels', postgresql_where=sa.text('is_deleted = false'))
    op.create_unique_constraint('uq_wf_level_order', 'workflow_levels', ['workflow_version_id', 'level_number'])
