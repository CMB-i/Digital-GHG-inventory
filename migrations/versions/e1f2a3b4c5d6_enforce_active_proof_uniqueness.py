"""enforce one active proof per submission field

Revision ID: e1f2a3b4c5d6
Revises: 6a7b8c9d0e1f
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "6a7b8c9d0e1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY submission_id, field_id
                    ORDER BY uploaded_at DESC, id DESC
                ) AS rn
            FROM proof_documents
            WHERE is_deleted = false
              AND field_id IS NOT NULL
        )
        UPDATE proof_documents
        SET
            is_deleted = true,
            deleted_at = now(),
            delete_reason = 'Superseded by active proof uniqueness migration'
        FROM ranked
        WHERE proof_documents.id = ranked.id
          AND ranked.rn > 1
        """
    )
    op.create_index(
        "uq_active_proof_document_submission_field",
        "proof_documents",
        ["submission_id", "field_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND field_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_proof_document_submission_field", table_name="proof_documents")
