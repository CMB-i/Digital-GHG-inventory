from datetime import datetime, timezone

from app.database import db


def utc_now():
    return datetime.now(timezone.utc)


class CreatedMixin:
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=db.func.now(),
    )
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class UpdateMixin:
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=db.func.now(),
    )
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)


class SoftDeleteMixin:
    is_deleted = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    delete_reason = db.Column(db.Text, nullable=True)


class LifecycleMixin(CreatedMixin, UpdateMixin):
    pass


class FullLifecycleMixin(CreatedMixin, UpdateMixin, SoftDeleteMixin):
    pass
