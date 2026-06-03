"""create core schema

Revision ID: 102cdbd1439c
Revises:
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "102cdbd1439c"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email', name='uq_users_email')
    )
    op.create_table('app_config',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('config_key', sa.String(length=100), nullable=False),
    sa.Column('config_value', sa.Text(), nullable=False),
    sa.Column('config_type', sa.String(length=30), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('config_key', name='uq_app_config_key')
    )
    op.create_table('forms',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('current_version_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_forms_code')
    )
    op.create_table('formulas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('code', sa.String(length=100), nullable=False),
    sa.Column('current_version_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_formula_code')
    )
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(length=100), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('channel', sa.String(length=30), server_default='in_app', nullable=False),
    sa.Column('is_read', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sites',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_sites_code'),
    sa.UniqueConstraint('name', name='uq_sites_name')
    )
    op.create_table('value_sets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('code', sa.String(length=100), nullable=False),
    sa.Column('current_version_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_value_set_code')
    )
    op.create_table('workflows',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('code', sa.String(length=100), nullable=False),
    sa.Column('current_version_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_workflow_code')
    )
    op.create_table('access_matrix',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('scope_type', sa.String(length=20), nullable=False),
    sa.Column('scope_site_id', sa.Integer(), nullable=True),
    sa.Column('scope_region_id', sa.Integer(), nullable=True),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('can_view', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_create', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_edit', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_delete', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_submit', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_approve', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_reject', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_reopen', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_export', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_manage_forms', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('can_manage_users', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['scope_site_id'], ['sites.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('fields',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('form_id', sa.Integer(), nullable=False),
    sa.Column('field_code', sa.String(length=100), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('current_version_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('form_id', 'field_code', name='uq_fields_code_per_form')
    )
    op.create_table('form_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('form_id', sa.Integer(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='Draft', nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_by', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ),
    sa.ForeignKeyConstraint(['published_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('form_id', 'version_number', name='uq_form_version_number')
    )
    op.create_table('formula_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('formula_id', sa.Integer(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('expression', sa.Text(), nullable=False),
    sa.Column('tokens', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['formula_id'], ['formulas.id'], ),
    sa.ForeignKeyConstraint(['published_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('formula_id', 'version_number', name='uq_formula_version_number')
    )
    op.create_table('report_templates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('code', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('scope_type', sa.String(length=20), nullable=True),
    sa.Column('scope_site_id', sa.Integer(), nullable=True),
    sa.Column('config_json', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['scope_site_id'], ['sites.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_report_template_code')
    )
    op.create_table('reporting_periods',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('month', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='OPEN', nullable=False),
    sa.Column('deadline', sa.Date(), nullable=True),
    sa.Column('reopen_reason', sa.Text(), nullable=True),
    sa.Column('reopened_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reopened_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['reopened_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('site_id', 'year', 'month', name='uq_period_site_year_month')
    )
    op.create_table('value_set_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('value_set_id', sa.Integer(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='Draft', nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_to', sa.Date(), nullable=True),
    sa.Column('submitted_by', sa.Integer(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('approved_by', sa.Integer(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejected_by', sa.Integer(), nullable=True),
    sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejection_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['rejected_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['value_set_id'], ['value_sets.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('value_set_id', 'version_number', name='uq_vs_version_number')
    )
    op.create_table('workflow_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workflow_id', sa.Integer(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_by', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['published_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('workflow_id', 'version_number', name='uq_wf_version_number')
    )
    op.create_table('field_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('field_name', sa.String(length=255), nullable=False),
    sa.Column('field_type', sa.String(length=50), nullable=False),
    sa.Column('field_config', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('form_version_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ),
    sa.ForeignKeyConstraint(['form_version_id'], ['form_versions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('field_id', 'version_number', name='uq_field_version_number')
    )
    op.create_table('submissions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.Integer(), nullable=False),
    sa.Column('form_id', sa.Integer(), nullable=False),
    sa.Column('form_version_id', sa.Integer(), nullable=False),
    sa.Column('reporting_period_id', sa.Integer(), nullable=False),
    sa.Column('workflow_version_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='Draft', nullable=False),
    sa.Column('submitted_by', sa.Integer(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('approved_by', sa.Integer(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_locked', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('last_status_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('current_level', sa.Integer(), nullable=True),
    sa.Column('parent_submission_id', sa.Integer(), nullable=True),
    sa.Column('anomaly_flag', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('anomaly_notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ),
    sa.ForeignKeyConstraint(['form_version_id'], ['form_versions.id'], ),
    sa.ForeignKeyConstraint(['parent_submission_id'], ['submissions.id'], ),
    sa.ForeignKeyConstraint(['reporting_period_id'], ['reporting_periods.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ),
    sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workflow_version_id'], ['workflow_versions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('value_set_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('value_set_version_id', sa.Integer(), nullable=False),
    sa.Column('entry_code', sa.String(length=100), nullable=False),
    sa.Column('entry_label', sa.String(length=255), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['value_set_version_id'], ['value_set_versions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('workflow_levels',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workflow_version_id', sa.Integer(), nullable=False),
    sa.Column('level_number', sa.Integer(), nullable=False),
    sa.Column('level_name', sa.String(length=100), nullable=False),
    sa.Column('approval_mode', sa.String(length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workflow_version_id'], ['workflow_versions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('workflow_version_id', 'level_number', name='uq_wf_level_order')
    )
    op.create_table('approval_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('submission_id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=False),
    sa.Column('level_number', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=30), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('acted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('issues',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('submission_id', sa.Integer(), nullable=False),
    sa.Column('raised_by', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='Open', nullable=False),
    sa.Column('resolved_by', sa.Integer(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('blocks_approval', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['raised_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('proof_documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('submission_id', sa.Integer(), nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=True),
    sa.Column('original_name', sa.String(length=255), nullable=False),
    sa.Column('storage_key', sa.Text(), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('uploaded_by', sa.Integer(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('submission_values',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('submission_id', sa.Integer(), nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('field_version_id', sa.Integer(), nullable=False),
    sa.Column('raw_value', sa.Text(), nullable=True),
    sa.Column('calculated_value', sa.Numeric(), nullable=True),
    sa.Column('formula_version_id', sa.Integer(), nullable=True),
    sa.Column('value_set_version_id', sa.Integer(), nullable=True),
    sa.Column('formula_inputs_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('formula_eval_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ),
    sa.ForeignKeyConstraint(['field_version_id'], ['field_versions.id'], ),
    sa.ForeignKeyConstraint(['formula_version_id'], ['formula_versions.id'], ),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['value_set_version_id'], ['value_set_versions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('submission_id', 'field_id', name='uq_submission_value')
    )
    op.create_table('workflow_level_approvers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workflow_level_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('sequence_number', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workflow_level_id'], ['workflow_levels.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('issue_comments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('issue_id', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('posted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('delete_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_notifications_user_unread', 'notifications', ['user_id'], unique=False, postgresql_where=sa.text('is_read = false'))
    op.create_index('idx_access_matrix_scope', 'access_matrix', ['scope_type', 'scope_site_id'], unique=False)
    op.create_index('idx_access_matrix_user', 'access_matrix', ['user_id'], unique=False)
    op.create_index('idx_form_versions_form', 'form_versions', ['form_id'], unique=False)
    op.create_index('idx_periods_site_status', 'reporting_periods', ['site_id', 'status'], unique=False)
    op.create_index('idx_vsv_status', 'value_set_versions', ['value_set_id', 'status'], unique=False)
    op.create_index('idx_field_versions_field', 'field_versions', ['field_id'], unique=False)
    op.create_index('idx_submissions_period', 'submissions', ['reporting_period_id'], unique=False)
    op.create_index('idx_submissions_site_form', 'submissions', ['site_id', 'form_id'], unique=False)
    op.create_index('idx_submissions_status', 'submissions', ['status'], unique=False)
    op.create_index('uq_active_submission', 'submissions', ['site_id', 'form_id', 'reporting_period_id'], unique=True, postgresql_where=sa.text('is_deleted = false'))
    op.create_index('idx_approval_actions_submission', 'approval_actions', ['submission_id'], unique=False)
    op.create_index('idx_issues_submission', 'issues', ['submission_id'], unique=False)
    op.create_index('idx_proof_docs_field', 'proof_documents', ['field_id'], unique=False, postgresql_where=sa.text('field_id IS NOT NULL'))
    op.create_index('idx_proof_docs_submission', 'proof_documents', ['submission_id'], unique=False)
    op.create_index('idx_sub_values_submission', 'submission_values', ['submission_id'], unique=False)

    op.create_foreign_key("fk_forms_current_version_id", "forms", "form_versions", ["current_version_id"], ["id"])
    op.create_foreign_key("fk_fields_current_version_id", "fields", "field_versions", ["current_version_id"], ["id"])
    op.create_foreign_key("fk_formulas_current_version_id", "formulas", "formula_versions", ["current_version_id"], ["id"])
    op.create_foreign_key("fk_value_sets_current_version_id", "value_sets", "value_set_versions", ["current_version_id"], ["id"])
    op.create_foreign_key("fk_workflows_current_version_id", "workflows", "workflow_versions", ["current_version_id"], ["id"])



def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint("fk_workflows_current_version_id", "workflows", type_="foreignkey")
    op.drop_constraint("fk_value_sets_current_version_id", "value_sets", type_="foreignkey")
    op.drop_constraint("fk_formulas_current_version_id", "formulas", type_="foreignkey")
    op.drop_constraint("fk_fields_current_version_id", "fields", type_="foreignkey")
    op.drop_constraint("fk_forms_current_version_id", "forms", type_="foreignkey")


    op.drop_index('idx_sub_values_submission', table_name='submission_values')
    op.drop_index('idx_proof_docs_submission', table_name='proof_documents')
    op.drop_index('idx_proof_docs_field', table_name='proof_documents', postgresql_where=sa.text('field_id IS NOT NULL'))
    op.drop_index('idx_issues_submission', table_name='issues')
    op.drop_index('idx_approval_actions_submission', table_name='approval_actions')
    op.drop_index('uq_active_submission', table_name='submissions', postgresql_where=sa.text('is_deleted = false'))
    op.drop_index('idx_submissions_status', table_name='submissions')
    op.drop_index('idx_submissions_site_form', table_name='submissions')
    op.drop_index('idx_submissions_period', table_name='submissions')
    op.drop_index('idx_field_versions_field', table_name='field_versions')
    op.drop_index('idx_vsv_status', table_name='value_set_versions')
    op.drop_index('idx_periods_site_status', table_name='reporting_periods')
    op.drop_index('idx_form_versions_form', table_name='form_versions')
    op.drop_index('idx_access_matrix_user', table_name='access_matrix')
    op.drop_index('idx_access_matrix_scope', table_name='access_matrix')
    op.drop_index('idx_notifications_user_unread', table_name='notifications', postgresql_where=sa.text('is_read = false'))
    op.drop_table('issue_comments')
    op.drop_table('workflow_level_approvers')
    op.drop_table('submission_values')
    op.drop_table('proof_documents')
    op.drop_table('issues')
    op.drop_table('approval_actions')
    op.drop_table('workflow_levels')
    op.drop_table('value_set_entries')
    op.drop_table('submissions')
    op.drop_table('field_versions')
    op.drop_table('workflow_versions')
    op.drop_table('value_set_versions')
    op.drop_table('reporting_periods')
    op.drop_table('report_templates')
    op.drop_table('formula_versions')
    op.drop_table('form_versions')
    op.drop_table('fields')
    op.drop_table('access_matrix')
    op.drop_table('workflows')
    op.drop_table('value_sets')
    op.drop_table('sites')
    op.drop_table('notifications')
    op.drop_table('formulas')
    op.drop_table('forms')
    op.drop_table('app_config')
    op.drop_table('users')
