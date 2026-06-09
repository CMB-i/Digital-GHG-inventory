"""add site aware workflow routing

Revision ID: a7c9e1d2b4f0
Revises: 253717e682e3
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c9e1d2b4f0"
down_revision: Union[str, Sequence[str], None] = "253717e682e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_levels",
        sa.Column("skip_if_empty", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "workflow_level_approvers",
        sa.Column("scope_site_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "workflow_level_approvers_scope_site_id_fkey",
        "workflow_level_approvers",
        "sites",
        ["scope_site_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "workflow_level_approvers_scope_site_id_fkey",
        "workflow_level_approvers",
        type_="foreignkey",
    )
    op.drop_column("workflow_level_approvers", "scope_site_id")
    op.drop_column("workflow_levels", "skip_if_empty")
