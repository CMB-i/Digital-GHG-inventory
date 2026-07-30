"""add password reset otps

Revision ID: 2b1c8a22f8dc
Revises: c0ec81848f3b
Create Date: 2026-07-30 12:34:55.599864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2b1c8a22f8dc"
down_revision: Union[str, Sequence[str], None] = "c0ec81848f3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "password_reset_otps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("otp_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_password_reset_otps_email_created",
        "password_reset_otps",
        ["email", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_password_reset_otps_user_unused",
        "password_reset_otps",
        ["user_id", "used"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_password_reset_otps_user_unused", table_name="password_reset_otps")
    op.drop_index("idx_password_reset_otps_email_created", table_name="password_reset_otps")
    op.drop_table("password_reset_otps")
