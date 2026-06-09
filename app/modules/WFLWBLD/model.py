from app.common.models import CreatedMixin, FullLifecycleMixin
from app.database import db


class Workflow(FullLifecycleMixin, db.Model):
    __tablename__ = "workflows"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(100), nullable=False)
    current_version_id = db.Column(
        db.Integer,
        db.ForeignKey("workflow_versions.id", use_alter=True, name="fk_workflows_current_version_id"),
        nullable=True,
    )

    __table_args__ = (
        db.UniqueConstraint("code", name="uq_workflow_code"),
    )


class WorkflowVersion(CreatedMixin, db.Model):
    __tablename__ = "workflow_versions"

    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey("workflows.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    published_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("workflow_id", "version_number", name="uq_wf_version_number"),
    )


class WorkflowLevel(FullLifecycleMixin, db.Model):
    __tablename__ = "workflow_levels"

    id = db.Column(db.Integer, primary_key=True)
    workflow_version_id = db.Column(db.Integer, db.ForeignKey("workflow_versions.id"), nullable=False)
    level_number = db.Column(db.Integer, nullable=False)
    level_name = db.Column(db.String(100), nullable=False)
    approval_mode = db.Column(db.String(30), nullable=False)
    skip_if_empty = db.Column(db.Boolean, nullable=False, default=False, server_default="false")

    __table_args__ = (
        db.UniqueConstraint("workflow_version_id", "level_number", name="uq_wf_level_order"),
    )


class WorkflowLevelApprover(FullLifecycleMixin, db.Model):
    __tablename__ = "workflow_level_approvers"

    id = db.Column(db.Integer, primary_key=True)
    workflow_level_id = db.Column(db.Integer, db.ForeignKey("workflow_levels.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scope_site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=True)
    sequence_number = db.Column(db.Integer, nullable=True)
