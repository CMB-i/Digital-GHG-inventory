"""collapse_reopened_status_into_open

Revision ID: 4e52328f2156
Revises: d4a912599210
Create Date: 2026-07-13 15:54:23.402499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e52328f2156'
down_revision: Union[str, Sequence[str], None] = 'd4a912599210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Collapses the REOPENED reporting-period status into OPEN. Every read-site
    already treated the two identically for submitters; REOPENED only ever
    existed as a transition-graph artifact (LOCKED reached OPEN via a
    two-step Lock -> Reopen -> Mark-Open cycle instead of directly). No DDL
    change is needed: reporting_periods.status is a plain VARCHAR(30) with no
    CHECK constraint or Postgres ENUM type.

    reopen_reason/reopened_at/reopened_by are left untouched -- they remain
    the historical "was this period ever reopened" signal now that the status
    value itself no longer distinguishes it (see periods.html's secondary
    badge, keyed off reopened_at).
    """
    op.execute("UPDATE reporting_periods SET status = 'OPEN' WHERE status = 'REOPENED'")


def downgrade() -> None:
    """
    Best-effort only: once collapsed, a period that legitimately cycled back
    to OPEN through the new direct LOCKED -> OPEN transition is
    indistinguishable, by status value alone, from one that was collapsed
    from REOPENED. This reverts every OPEN period that has a reopened_at
    timestamp back to REOPENED, which is correct for rows untouched since the
    upgrade but will over-match any period reopened again after a downgrade
    is eventually needed. Acceptable since a downgrade is only meant to
    accompany rolling back to the code revision that still understands
    REOPENED as a distinct status.
    """
    op.execute(
        "UPDATE reporting_periods SET status = 'REOPENED' "
        "WHERE status = 'OPEN' AND reopened_at IS NOT NULL"
    )
