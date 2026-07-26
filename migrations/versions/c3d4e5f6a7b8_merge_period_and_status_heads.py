"""Merge heads: collapse_reopened_status_into_open + period_soft_delete_unique_constraint

Pre-existing issue found while adding an unrelated migration: these two
migrations were merged to main independently, both branching off
d4a912599210, without a reconciling merge migration. No schema changes here,
this just joins the two heads back into one line so alembic upgrade has a
single target again.

Revision ID: c3d4e5f6a7b8
Revises: 4e52328f2156, a8149c333913
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = ('4e52328f2156', 'a8149c333913')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
