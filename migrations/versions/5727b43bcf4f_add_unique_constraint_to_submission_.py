"""add unique constraint to submission packages

Revision ID: 5727b43bcf4f
Revises: a4b5c6d7e8f9
Create Date: 2026-07-10 09:35:54.526574

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5727b43bcf4f'
down_revision: Union[str, Sequence[str], None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_active_submission_package",
        "submission_packages",
        ["site_id", "period_id", "package_type"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_active_submission_package",
        table_name="submission_packages",
        postgresql_where=sa.text("is_deleted = false"),
    )
