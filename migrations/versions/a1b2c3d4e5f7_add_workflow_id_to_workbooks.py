"""add workflow_id to workbooks

Revision ID: a1b2c3d4e5f7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workbooks", sa.Column("workflow_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "workbooks_workflow_id_fkey",
        "workbooks",
        "workflows",
        ["workflow_id"],
        ["id"],
    )
    op.create_index("idx_workbooks_workflow_id", "workbooks", ["workflow_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_workbooks_workflow_id", table_name="workbooks")
    op.drop_constraint("workbooks_workflow_id_fkey", "workbooks", type_="foreignkey")
    op.drop_column("workbooks", "workflow_id")
