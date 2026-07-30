"""enforce one active access matrix row per permission scope

Revision ID: f6a7b8c9d0e2
Revises: e1f2a3b4c5d6
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e2"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY
                        user_id,
                        scope_type,
                        coalesce(scope_site_id, 0),
                        coalesce(scope_region_id, 0),
                        entity_type,
                        coalesce(entity_id, 0)
                    ORDER BY updated_at DESC, id DESC
                ) AS rn
            FROM access_matrix
            WHERE is_deleted = false
        )
        UPDATE access_matrix
        SET
            is_deleted = true,
            deleted_at = now(),
            delete_reason = 'Superseded by active Access Matrix uniqueness migration'
        FROM ranked
        WHERE access_matrix.id = ranked.id
          AND ranked.rn > 1
        """
    )
    op.create_index(
        "uq_active_access_matrix_permission_scope",
        "access_matrix",
        [
            "user_id",
            "scope_type",
            sa.text("coalesce(scope_site_id, 0)"),
            sa.text("coalesce(scope_region_id, 0)"),
            "entity_type",
            sa.text("coalesce(entity_id, 0)"),
        ],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_access_matrix_permission_scope", table_name="access_matrix")
