"""add submission packages and cell state

Revision ID: f4c7b8a9d012
Revises: e3b2c1d4a5f6
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f4c7b8a9d012"
down_revision: Union[str, Sequence[str], None] = "e3b2c1d4a5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "submission_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("package_type", sa.String(length=50), server_default="monthly_workbook", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="Draft", nullable=False),
        sa.Column("submitted_by", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_level", sa.Integer(), nullable=True),
        sa.Column("final_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_approved_by", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(["final_approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["reporting_periods.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_submission_packages_site_period",
        "submission_packages",
        ["site_id", "period_id"],
        unique=False,
    )
    op.create_index("idx_submission_packages_status", "submission_packages", ["status"], unique=False)

    op.add_column("submissions", sa.Column("package_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "submissions_package_id_fkey",
        "submissions",
        "submission_packages",
        ["package_id"],
        ["id"],
    )
    op.create_index("idx_submissions_package", "submissions", ["package_id"], unique=False)

    op.add_column(
        "submission_values",
        sa.Column("cell_state", sa.String(length=30), server_default="blank_editable", nullable=False),
    )
    op.add_column(
        "submission_values",
        sa.Column("is_locked", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("submission_values", sa.Column("remark", sa.Text(), nullable=True))
    op.create_index("idx_submission_values_cell_state", "submission_values", ["cell_state"], unique=False)

    op.execute(
        """
        UPDATE submission_values sv
        SET
            cell_state = CASE
                WHEN NOT (
                    (sv.raw_value IS NOT NULL AND sv.raw_value <> '')
                    OR sv.calculated_value IS NOT NULL
                ) THEN 'blank_editable'
                WHEN s.status = 'Approved' THEN 'approved_locked'
                WHEN s.status IN ('Submitted', 'Resubmitted', 'Under Review') THEN 'submitted'
                WHEN s.status = 'Changes Requested' THEN 'changes_requested'
                ELSE 'draft_filled'
            END,
            is_locked = CASE
                WHEN (
                    (sv.raw_value IS NOT NULL AND sv.raw_value <> '')
                    OR sv.calculated_value IS NOT NULL
                ) AND s.status = 'Approved'
                THEN true
                ELSE false
            END
        FROM submissions s
        WHERE sv.submission_id = s.id
        """
    )

    op.create_table(
        "submission_value_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_value_id", sa.Integer(), nullable=False),
        sa.Column("raised_by", sa.Integer(), nullable=False),
        sa.Column("issue_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="Open", nullable=False),
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
        sa.ForeignKeyConstraint(["raised_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["submission_value_id"], ["submission_values.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_submission_value_issues_value",
        "submission_value_issues",
        ["submission_value_id"],
        unique=False,
    )
    op.create_index(
        "idx_submission_value_issues_status",
        "submission_value_issues",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_submission_value_issues_status", table_name="submission_value_issues")
    op.drop_index("idx_submission_value_issues_value", table_name="submission_value_issues")
    op.drop_table("submission_value_issues")

    op.drop_index("idx_submission_values_cell_state", table_name="submission_values")
    op.drop_column("submission_values", "remark")
    op.drop_column("submission_values", "is_locked")
    op.drop_column("submission_values", "cell_state")

    op.drop_index("idx_submissions_package", table_name="submissions")
    op.drop_constraint("submissions_package_id_fkey", "submissions", type_="foreignkey")
    op.drop_column("submissions", "package_id")

    op.drop_index("idx_submission_packages_status", table_name="submission_packages")
    op.drop_index("idx_submission_packages_site_period", table_name="submission_packages")
    op.drop_table("submission_packages")
