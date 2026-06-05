from sqlalchemy.dialects.postgresql import JSONB

from app.common.models import utc_now
from app.database import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(100), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    old_values = db.Column(JSONB, nullable=True)
    new_values = db.Column(JSONB, nullable=True)
    metadata_json = db.Column("metadata", JSONB, nullable=True)
    ip_address = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.Index("idx_audit_logs_entity", "entity_type", "entity_id"),
        db.Index("idx_audit_logs_actor", "actor_user_id"),
        db.Index("idx_audit_logs_created_at", "created_at"),
    )
