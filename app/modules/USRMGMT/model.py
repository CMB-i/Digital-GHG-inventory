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

    __table_args__ = (
        db.UniqueConstraint("email", name="uq_users_email"),
    )
