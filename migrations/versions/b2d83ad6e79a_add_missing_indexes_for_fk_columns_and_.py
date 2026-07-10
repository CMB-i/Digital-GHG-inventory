"""add missing indexes for FK columns and needs_recalc_review

Revision ID: b2d83ad6e79a
Revises: 4578e4926a71
Create Date: 2026-07-10 11:09:35.715049

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d83ad6e79a'
down_revision: Union[str, Sequence[str], None] = '4578e4926a71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # submission_values: FK columns with no index (field_id is the second
    # column of uq_submission_value, which only serves lookups that also
    # filter by submission_id).
    op.create_index("idx_submission_values_field", "submission_values", ["field_id"], unique=False)
    op.create_index("idx_submission_values_field_version", "submission_values", ["field_version_id"], unique=False)
    op.create_index("idx_submission_values_formula_version", "submission_values", ["formula_version_id"], unique=False)
    op.create_index("idx_submission_values_value_set_version", "submission_values", ["value_set_version_id"], unique=False)

    # workflow_level_approvers.scope_site_id: FK with no index at all on this table.
    op.create_index("idx_workflow_level_approvers_scope_site", "workflow_level_approvers", ["scope_site_id"], unique=False)

    # "which X applies to site/user Y" patterns not served by the existing
    # composite indexes/unique constraints on these tables.
    op.create_index("idx_workbook_sites_site", "workbook_sites", ["site_id"], unique=False)
    op.create_index("idx_wss_user", "workbook_site_submitters", ["user_id"], unique=False)

    # Sparse boolean partial index, same pattern as idx_notifications_user_unread.
    op.create_index(
        "idx_submissions_needs_recalc_review",
        "submissions",
        ["needs_recalc_review"],
        unique=False,
        postgresql_where=sa.text("needs_recalc_review = true"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_submissions_needs_recalc_review", table_name="submissions", postgresql_where=sa.text("needs_recalc_review = true"))
    op.drop_index("idx_wss_user", table_name="workbook_site_submitters")
    op.drop_index("idx_workbook_sites_site", table_name="workbook_sites")
    op.drop_index("idx_workflow_level_approvers_scope_site", table_name="workflow_level_approvers")
    op.drop_index("idx_submission_values_value_set_version", table_name="submission_values")
    op.drop_index("idx_submission_values_formula_version", table_name="submission_values")
    op.drop_index("idx_submission_values_field_version", table_name="submission_values")
    op.drop_index("idx_submission_values_field", table_name="submission_values")
