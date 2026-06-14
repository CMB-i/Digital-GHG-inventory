"""add workbooks and workbook_forms tables

Revision ID: a1b2c3d4e5f6
Revises: f4c7b8a9d012
Create Date: 2026-06-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9b1c2d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workbooks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_workbooks_code"),
    )
    op.create_index("idx_workbooks_is_active", "workbooks", ["is_active"], unique=False)

    op.create_table(
        "workbook_forms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workbook_id", sa.Integer(), nullable=False),
        sa.Column("form_id", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sheet_label", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"]),
        sa.ForeignKeyConstraint(["workbook_id"], ["workbooks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workbook_id", "form_id", name="uq_workbook_form"),
    )
    op.create_index("idx_workbook_forms_workbook", "workbook_forms", ["workbook_id", "display_order"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_workbook_forms_workbook", table_name="workbook_forms")
    op.drop_table("workbook_forms")
    op.drop_index("idx_workbooks_is_active", table_name="workbooks")
    op.drop_table("workbooks")
