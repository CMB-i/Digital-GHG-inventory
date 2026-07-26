"""Scope value_sets.code uniqueness to non-deleted rows

The original constraint (uq_value_set_code) was a plain unique constraint on
`code`, not scoped to is_deleted = false like other soft-deletable tables in
this schema (e.g. workbooks). That meant once a code was used - even by a
value set that was later soft-deleted - it could never be reused, even
though the UI shows nothing there. This migration replaces the plain unique
constraint with a partial unique index scoped to is_deleted = false, matching
the existing pattern used by workbooks.

Revision ID: b7d8e9f0a1c2
Revises: c3d4e5f6a7b8
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa

revision = 'b7d8e9f0a1c2'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('uq_value_set_code', 'value_sets', type_='unique')
    op.create_index(
        'uq_value_set_code',
        'value_sets',
        ['code'],
        unique=True,
        postgresql_where=sa.text('is_deleted = false'),
    )


def downgrade():
    op.drop_index('uq_value_set_code', table_name='value_sets')
    op.create_unique_constraint('uq_value_set_code', 'value_sets', ['code'])
