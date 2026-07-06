"""add calc_status/calc_error_message and needs_recalc_review flag

Revision ID: c7d8e9f0a1b2
Revises: 2fcff837b64e
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "2fcff837b64e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submission_values", sa.Column("calc_status", sa.String(length=20), nullable=True))
    op.add_column("submission_values", sa.Column("calc_error_message", sa.Text(), nullable=True))

    op.add_column(
        "submissions",
        sa.Column("needs_recalc_review", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("submissions", sa.Column("recalc_review_notes", sa.Text(), nullable=True))

    # Backfill calc_status for existing calculated-field rows so old data isn't
    # left ambiguous: a persisted number means "ok", a blank one means "pending"
    # (matches the previous behavior where a blank calculated value simply meant
    # the formula hadn't produced a result yet -- there was no error tracking before).
    op.execute(
        """
        UPDATE submission_values sv
        SET calc_status = CASE WHEN sv.calculated_value IS NOT NULL THEN 'ok' ELSE 'pending' END
        FROM fields f, field_versions fv
        WHERE sv.field_id = f.id
          AND sv.field_version_id = fv.id
          AND fv.field_type = 'calculated'
        """
    )


def downgrade() -> None:
    op.drop_column("submissions", "recalc_review_notes")
    op.drop_column("submissions", "needs_recalc_review")

    op.drop_column("submission_values", "calc_error_message")
    op.drop_column("submission_values", "calc_status")
