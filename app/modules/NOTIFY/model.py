from app.common.models import utc_now, FullLifecycleMixin
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


class UserNotificationPreference(db.Model):
    __tablename__ = "user_notification_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    pref_in_app = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    pref_desktop = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    pref_email = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    pref_whatsapp = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=db.func.now(),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=db.func.now(),
    )


class NotificationConfig(FullLifecycleMixin, db.Model):
    __tablename__ = "notification_configs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    message_template = db.Column(db.Text, nullable=False)
    recipient_type = db.Column(db.String(50), nullable=False, default="role")
    
    # If recipient_type == "role"
    target_entity_type = db.Column(db.String(50), nullable=True)
    target_permission = db.Column(db.String(50), nullable=True)
    
    # If recipient_type == "users" (comma-separated user IDs)
    recipient_user_ids = db.Column(db.Text, nullable=True)
    
    # If recipient_type == "dynamic" (spoc, level_approvers, site_admins)
    dynamic_role = db.Column(db.String(50), nullable=True)
    
    # Comma-separated list of enabled channels, e.g. "in_app,desktop,email,whatsapp"
    channels = db.Column(db.String(100), nullable=False, default="in_app")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")

