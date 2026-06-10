"""add form sections and field frequency

Revision ID: e3b2c1d4a5f6
Revises: a7c9e1d2b4f0
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3b2c1d4a5f6"
down_revision: Union[str, Sequence[str], None] = "a7c9e1d2b4f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "form_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("form_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column(
            "layout_type",
            sa.String(length=50),
            server_default="monthly_table",
            nullable=False,
        ),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_form_sections_form", "form_sections", ["form_id"], unique=False)
    op.create_index(
        "uq_form_sections_code_per_form",
        "form_sections",
        ["form_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.add_column("field_versions", sa.Column("section_id", sa.Integer(), nullable=True))
    op.add_column(
        "field_versions",
        sa.Column("frequency", sa.String(length=20), server_default="monthly", nullable=False),
    )
    op.create_foreign_key(
        "field_versions_section_id_fkey",
        "field_versions",
        "form_sections",
        ["section_id"],
        ["id"],
    )
    op.create_index("idx_field_versions_section", "field_versions", ["section_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_field_versions_section", table_name="field_versions")
    op.drop_constraint("field_versions_section_id_fkey", "field_versions", type_="foreignkey")
    op.drop_column("field_versions", "frequency")
    op.drop_column("field_versions", "section_id")

    op.drop_index(
        "uq_form_sections_code_per_form",
        table_name="form_sections",
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.drop_index("idx_form_sections_form", table_name="form_sections")
    op.drop_table("form_sections")
