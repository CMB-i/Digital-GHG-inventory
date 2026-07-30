"""harden login redirects and password reset

Revision ID: 6a7b8c9d0e1f
Revises: 2b1c8a22f8dc
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a7b8c9d0e1f"
down_revision: Union[str, Sequence[str], None] = "2b1c8a22f8dc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "password_reset_otps",
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("password_reset_otps", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("password_reset_otps", "locked_at")
    op.drop_column("password_reset_otps", "failed_attempts")
    op.drop_column("users", "session_version")
