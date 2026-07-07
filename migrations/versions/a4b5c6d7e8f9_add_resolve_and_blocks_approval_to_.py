"""add resolve fields and blocks_approval to submission_value_issues

Revision ID: a4b5c6d7e8f9
Revises: d3e4f5a6b7c8
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submission_value_issues", sa.Column("resolved_by", sa.Integer(), nullable=True))
    op.add_column("submission_value_issues", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "submission_value_issues",
        sa.Column("blocks_approval", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_foreign_key(
        "submission_value_issues_resolved_by_fkey",
        "submission_value_issues",
        "users",
        ["resolved_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("submission_value_issues_resolved_by_fkey", "submission_value_issues", type_="foreignkey")
    op.drop_column("submission_value_issues", "blocks_approval")
    op.drop_column("submission_value_issues", "resolved_at")
    op.drop_column("submission_value_issues", "resolved_by")
