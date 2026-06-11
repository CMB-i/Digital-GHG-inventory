"""add workbook field values

Revision ID: 9b1c2d3e4f5a
Revises: f4c7b8a9d012
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9b1c2d3e4f5a"
down_revision: Union[str, Sequence[str], None] = "f4c7b8a9d012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workbook_field_values",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("form_id", sa.Integer(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("field_version_id", sa.Integer(), nullable=False),
        sa.Column("fy_start_year", sa.Integer(), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("numeric_value", sa.Numeric(), nullable=True),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cell_state", sa.String(length=40), server_default="blank_editable", nullable=False),
        sa.Column("is_locked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.Column("delete_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.ForeignKeyConstraint(["field_version_id"], ["field_versions.id"]),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_workbook_field_values_site_fy",
        "workbook_field_values",
        ["site_id", "fy_start_year"],
        unique=False,
    )
    op.create_index(
        "idx_workbook_field_values_field_version",
        "workbook_field_values",
        ["field_version_id"],
        unique=False,
    )
    op.create_index(
        "uq_active_workbook_field_value",
        "workbook_field_values",
        ["site_id", "form_id", "field_version_id", "fy_start_year"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_workbook_field_value", table_name="workbook_field_values")
    op.drop_index("idx_workbook_field_values_field_version", table_name="workbook_field_values")
    op.drop_index("idx_workbook_field_values_site_fy", table_name="workbook_field_values")
    op.drop_table("workbook_field_values")
