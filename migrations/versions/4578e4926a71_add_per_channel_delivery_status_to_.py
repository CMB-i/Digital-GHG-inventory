"""add per-channel delivery status to notifications

Revision ID: 4578e4926a71
Revises: 5727b43bcf4f
Create Date: 2026-07-10 10:34:59.717691

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4578e4926a71'
down_revision: Union[str, Sequence[str], None] = '5727b43bcf4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "notifications",
        sa.Column("delivery_status", sa.String(length=20), server_default="sent", nullable=False),
    )
    op.add_column(
        "notifications",
        sa.Column("delivery_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("notifications", "delivery_error")
    op.drop_column("notifications", "delivery_status")
