from app.common.models import FullLifecycleMixin
from app.database import db


class User(FullLifecycleMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    session_version = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        db.UniqueConstraint("email", name="uq_users_email"),
    )


class PasswordResetOTP(db.Model):
    __tablename__ = "password_reset_otps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    otp_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    locked_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User")

    __table_args__ = (
        db.Index("idx_password_reset_otps_email_created", "email", "created_at"),
        db.Index("idx_password_reset_otps_user_unused", "user_id", "used"),
    )
