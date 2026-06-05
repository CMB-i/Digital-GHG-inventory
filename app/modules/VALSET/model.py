from app.common.models import CreatedMixin, FullLifecycleMixin
from app.database import db


class ValueSet(FullLifecycleMixin, db.Model):
    __tablename__ = "value_sets"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    current_version_id = db.Column(
        db.Integer,
        db.ForeignKey("value_set_versions.id", use_alter=True, name="fk_value_sets_current_version_id"),
        nullable=True,
    )

    __table_args__ = (
        db.UniqueConstraint("code", name="uq_value_set_code"),
    )


class ValueSetVersion(CreatedMixin, db.Model):
    __tablename__ = "value_set_versions"

    id = db.Column(db.Integer, primary_key=True)
    value_set_id = db.Column(db.Integer, db.ForeignKey("value_sets.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Draft", server_default="Draft")
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejected_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rejected_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("value_set_id", "version_number", name="uq_vs_version_number"),
        db.Index("idx_vsv_status", "value_set_id", "status"),
    )


class ValueSetEntry(FullLifecycleMixin, db.Model):
    __tablename__ = "value_set_entries"

    id = db.Column(db.Integer, primary_key=True)
    value_set_version_id = db.Column(db.Integer, db.ForeignKey("value_set_versions.id"), nullable=False)
    entry_code = db.Column(db.String(100), nullable=False)
    entry_label = db.Column(db.String(255), nullable=False)
    display_order = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
