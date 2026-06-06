"""add field id to issues

Revision ID: f2a7c6d9e1b3
Revises: 885806e02f47
Create Date: 2026-06-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a7c6d9e1b3"
down_revision: Union[str, Sequence[str], None] = "885806e02f47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("issues", sa.Column("field_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "issues_field_id_fkey",
        "issues",
        "fields",
        ["field_id"],
        ["id"],
    )
    op.create_index("idx_issues_field", "issues", ["field_id"])


def downgrade() -> None:
    op.drop_index("idx_issues_field", table_name="issues")
    op.drop_constraint("issues_field_id_fkey", "issues", type_="foreignkey")
    op.drop_column("issues", "field_id")
