"""add form_id to formulas

Revision ID: d4a912599210
Revises: b2d83ad6e79a
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4a912599210"
down_revision: Union[str, Sequence[str], None] = "b2d83ad6e79a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("formulas", sa.Column("form_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "formulas_form_id_fkey",
        "formulas",
        "forms",
        ["form_id"],
        ["id"],
    )
    op.create_index("idx_formulas_form", "formulas", ["form_id"])

    # No backfill: a formula can be (and often is) referenced by fields on more
    # than one sheet, so there is no single correct form_id to infer for
    # existing rows -- any heuristic (e.g. "the first field that references
    # this formula's current_version_id") could silently misattribute a
    # formula shared across sheets. Existing formulas are left form_id = NULL
    # and simply won't be sheet-scoped in the Formula Builder / picker; only
    # formulas created after this migration get a form_id at creation time.


def downgrade() -> None:
    op.drop_index("idx_formulas_form", table_name="formulas")
    op.drop_constraint("formulas_form_id_fkey", "formulas", type_="foreignkey")
    op.drop_column("formulas", "form_id")
