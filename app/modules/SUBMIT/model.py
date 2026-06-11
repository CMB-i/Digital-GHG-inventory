from sqlalchemy.dialects.postgresql import JSONB

from app.common.models import FullLifecycleMixin, LifecycleMixin, SoftDeleteMixin, utc_now
from app.database import db


class Submission(FullLifecycleMixin, db.Model):
    __tablename__ = "submissions"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False)
    form_version_id = db.Column(db.Integer, db.ForeignKey("form_versions.id"), nullable=False)
    reporting_period_id = db.Column(db.Integer, db.ForeignKey("reporting_periods.id"), nullable=False)
    workflow_version_id = db.Column(db.Integer, db.ForeignKey("workflow_versions.id"), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey("submission_packages.id"), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Draft", server_default="Draft")
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_locked = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    last_status_changed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    current_level = db.Column(db.Integer, nullable=True)
    parent_submission_id = db.Column(db.Integer, db.ForeignKey("submissions.id"), nullable=True)
    anomaly_flag = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    anomaly_notes = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.Index(
            "uq_active_submission",
            "site_id",
            "form_id",
            "reporting_period_id",
            unique=True,
            postgresql_where=db.text("is_deleted = false"),
        ),
        db.Index("idx_submissions_period", "reporting_period_id"),
        db.Index("idx_submissions_package", "package_id"),
        db.Index("idx_submissions_site_form", "site_id", "form_id"),
        db.Index("idx_submissions_status", "status"),
    )


class SubmissionPackage(FullLifecycleMixin, db.Model):
    __tablename__ = "submission_packages"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    period_id = db.Column(db.Integer, db.ForeignKey("reporting_periods.id"), nullable=False)
    package_type = db.Column(db.String(50), nullable=False, default="monthly_workbook", server_default="monthly_workbook")
    status = db.Column(db.String(30), nullable=False, default="Draft", server_default="Draft")
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    current_level = db.Column(db.Integer, nullable=True)
    final_approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    final_approved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    description = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(JSONB, nullable=True)

    __table_args__ = (
        db.Index("idx_submission_packages_site_period", "site_id", "period_id"),
        db.Index("idx_submission_packages_status", "status"),
    )


class SubmissionValue(LifecycleMixin, db.Model):
    __tablename__ = "submission_values"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submissions.id"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("fields.id"), nullable=False)
    field_version_id = db.Column(db.Integer, db.ForeignKey("field_versions.id"), nullable=False)
    raw_value = db.Column(db.Text, nullable=True)
    calculated_value = db.Column(db.Numeric, nullable=True)
    formula_version_id = db.Column(db.Integer, db.ForeignKey("formula_versions.id"), nullable=True)
    value_set_version_id = db.Column(db.Integer, db.ForeignKey("value_set_versions.id"), nullable=True)
    formula_inputs_snapshot = db.Column(JSONB, nullable=True)
    formula_eval_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cell_state = db.Column(db.String(30), nullable=False, default="blank_editable", server_default="blank_editable")
    is_locked = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    remark = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("submission_id", "field_id", name="uq_submission_value"),
        db.Index("idx_sub_values_submission", "submission_id"),
        db.Index("idx_submission_values_cell_state", "cell_state"),
    )


class SubmissionValueIssue(FullLifecycleMixin, db.Model):
    __tablename__ = "submission_value_issues"

    id = db.Column(db.Integer, primary_key=True)
    submission_value_id = db.Column(db.Integer, db.ForeignKey("submission_values.id"), nullable=False)
    raised_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    issue_text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Open", server_default="Open")

    __table_args__ = (
        db.Index("idx_submission_value_issues_value", "submission_value_id"),
        db.Index("idx_submission_value_issues_status", "status"),
    )


class WorkbookFieldValue(FullLifecycleMixin, db.Model):
    __tablename__ = "workbook_field_values"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("fields.id"), nullable=False)
    field_version_id = db.Column(db.Integer, db.ForeignKey("field_versions.id"), nullable=False)
    fy_start_year = db.Column(db.Integer, nullable=False)
    value_text = db.Column(db.Text, nullable=True)
    numeric_value = db.Column(db.Numeric, nullable=True)
    value_json = db.Column(JSONB, nullable=True)
    cell_state = db.Column(db.String(40), nullable=False, default="blank_editable", server_default="blank_editable")
    is_locked = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    remark = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.Index("idx_workbook_field_values_site_fy", "site_id", "fy_start_year"),
        db.Index("idx_workbook_field_values_field_version", "field_version_id"),
        db.Index(
            "uq_active_workbook_field_value",
            "site_id",
            "form_id",
            "field_version_id",
            "fy_start_year",
            unique=True,
            postgresql_where=db.text("is_deleted = false"),
        ),
    )


class ProofDocument(SoftDeleteMixin, db.Model):
    __tablename__ = "proof_documents"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submissions.id"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("fields.id"), nullable=True)
    original_name = db.Column(db.String(255), nullable=False)
    storage_key = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_size_bytes = db.Column(db.Integer, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.Index("idx_proof_docs_submission", "submission_id"),
        db.Index("idx_proof_docs_field", "field_id", postgresql_where=db.text("field_id IS NOT NULL")),
    )
