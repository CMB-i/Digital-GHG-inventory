"""add_formula_context

Revision ID: ebe157521644
Revises: 64ed524a4239
Create Date: 2026-07-26 21:09:58.211695

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ebe157521644'
down_revision: Union[str, Sequence[str], None] = '64ed524a4239'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "formulas",
        sa.Column("context", sa.String(length=20), nullable=False, server_default="field"),
    )


def downgrade() -> None:
    op.drop_column("formulas", "context")
