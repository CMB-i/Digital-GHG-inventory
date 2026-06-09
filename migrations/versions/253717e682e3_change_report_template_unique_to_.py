"""change_report_template_unique_to_partial_index

Revision ID: 253717e682e3
Revises: f2a7c6d9e1b3
Create Date: 2026-06-08 12:54:07.756234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '253717e682e3'
down_revision: Union[str, Sequence[str], None] = 'f2a7c6d9e1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_report_template_code', 'report_templates', type_='unique')
    op.create_index('uq_report_template_code', 'report_templates', ['code'], unique=True, postgresql_where=sa.text('is_deleted = false'))


def downgrade() -> None:
    op.drop_index('uq_report_template_code', table_name='report_templates', postgresql_where=sa.text('is_deleted = false'))
    op.create_unique_constraint('uq_report_template_code', 'report_templates', ['code'])
