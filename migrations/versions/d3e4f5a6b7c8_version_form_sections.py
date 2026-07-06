"""version FormSection per form_version, matching FieldVersion isolation

Revision ID: d3e4f5a6b7c8
Revises: c7d8e9f0a1b2
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("form_sections", sa.Column("form_version_id", sa.Integer(), nullable=True))

    # Backfill existing (pre-versioning) rows to each form's current published version,
    # falling back to the latest version if the form has never been published. Every
    # section row today is shared across all versions of its form, so this assigns the
    # single existing row to one version; older non-current versions' FieldVersion rows
    # will still reference it by section_id, just under a form_version_id label that no
    # longer matches their own -- acceptable for historical data, since going forward
    # every new draft clones its own version-scoped section rows (see FORMBLD/service.py
    # create_new_form_version_draft).
    op.execute(
        """
        UPDATE form_sections fs
        SET form_version_id = COALESCE(
            (SELECT f.current_version_id FROM forms f WHERE f.id = fs.form_id),
            (
                SELECT fv.id FROM form_versions fv
                WHERE fv.form_id = fs.form_id
                ORDER BY fv.version_number DESC
                LIMIT 1
            )
        )
        """
    )

    op.alter_column("form_sections", "form_version_id", nullable=False)
    op.create_foreign_key(
        "form_sections_form_version_id_fkey",
        "form_sections",
        "form_versions",
        ["form_version_id"],
        ["id"],
    )
    op.create_index("idx_form_sections_form_version", "form_sections", ["form_version_id"], unique=False)

    op.drop_index("uq_form_sections_code_per_form", table_name="form_sections")
    op.create_index(
        "uq_form_sections_code_per_version",
        "form_sections",
        ["form_version_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_form_sections_code_per_version", table_name="form_sections")
    op.create_index(
        "uq_form_sections_code_per_form",
        "form_sections",
        ["form_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.drop_index("idx_form_sections_form_version", table_name="form_sections")
    op.drop_constraint("form_sections_form_version_id_fkey", "form_sections", type_="foreignkey")
    op.drop_column("form_sections", "form_version_id")
