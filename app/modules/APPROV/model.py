from app.common.models import FullLifecycleMixin, utc_now
from app.database import db


class ApprovalAction(FullLifecycleMixin, db.Model):
    __tablename__ = "approval_actions"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submissions.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    level_number = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(30), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    acted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.Index("idx_approval_actions_submission", "submission_id"),
    )


class Issue(FullLifecycleMixin, db.Model):
    __tablename__ = "issues"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submissions.id"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("fields.id"), nullable=True)
    raised_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Open", server_default="Open")
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    blocks_approval = db.Column(db.Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        db.Index("idx_issues_submission", "submission_id"),
        db.Index("idx_issues_field", "field_id"),
    )


class IssueComment(FullLifecycleMixin, db.Model):
    __tablename__ = "issue_comments"

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("issues.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    posted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=db.func.now(),
    )
