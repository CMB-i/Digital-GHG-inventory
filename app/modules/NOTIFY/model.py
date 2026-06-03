from app.common.models import utc_now
from app.database import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(30), nullable=False, default="in_app", server_default="in_app")
    is_read = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.Index("idx_notifications_user_unread", "user_id", postgresql_where=db.text("is_read = false")),
    )
