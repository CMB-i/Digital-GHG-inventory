"""Add workbook_site_submitters table

Revision ID: a1b2c3d4e5f9
Revises: a1b2c3d4e5f8
Create Date: 2026-06-14
"""

from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f9'
down_revision = 'a1b2c3d4e5f8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'workbook_site_submitters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workbook_id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workbook_id'], ['workbooks.id']),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workbook_id', 'site_id', 'user_id', name='uq_workbook_site_submitter'),
    )
    op.create_index('idx_wss_workbook_site', 'workbook_site_submitters', ['workbook_id', 'site_id'])


def downgrade():
    op.drop_index('idx_wss_workbook_site', table_name='workbook_site_submitters')
    op.drop_table('workbook_site_submitters')
