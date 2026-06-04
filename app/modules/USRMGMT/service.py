import bcrypt
from datetime import datetime, timezone

from app.common.validators import (
    ValidationError,
    validate_email,
    validate_full_name,
    validate_phone,
    validate_temporary_password,
)
from app.database import db
from app.modules.ACCESS.model import AccessMatrix
from app.modules.USRMGMT.model import User


def hash_password(plain_text):
    return bcrypt.hashpw(plain_text.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_text, password_hash):
    if not plain_text or not password_hash:
        return False
    return bcrypt.checkpw(plain_text.encode("utf-8"), password_hash.encode("utf-8"))


def authenticate_user(email, password):
    user = User.query.filter_by(email=(email or "").strip().lower(), is_deleted=False).one_or_none()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def record_successful_login(user):
    user.last_login_at = datetime.now(timezone.utc)


def list_users():
    return User.query.filter_by(is_deleted=False).order_by(User.full_name.asc()).all()


def create_user(full_name, email, phone, temporary_password, actor_id):
    validated_email = validate_email(email)
    if User.query.filter_by(email=validated_email, is_deleted=False).first():
        raise ValidationError("A user with this email already exists.")

    user = User(
        full_name=validate_full_name(full_name),
        email=validated_email,
        phone=validate_phone(phone),
        password_hash=hash_password(validate_temporary_password(temporary_password)),
        is_active=True,
        created_by=actor_id,
    )
    db.session.add(user)
    return user


def update_user(user_id, full_name, email, phone):
    user = User.query.filter_by(id=user_id, is_deleted=False).one_or_none()
    if not user:
        return None
    validated_email = validate_email(email)
    duplicate = (
        User.query.filter(User.email == validated_email, User.id != user_id, User.is_deleted.is_(False))
        .first()
    )
    if duplicate:
        raise ValidationError("A user with this email already exists.")
    user.full_name = validate_full_name(full_name)
    user.email = validated_email
    user.phone = validate_phone(phone)
    return user


def set_temporary_password(user_id, temporary_password):
    user = User.query.filter_by(id=user_id, is_deleted=False).one_or_none()
    if not user:
        return None
    user.password_hash = hash_password(validate_temporary_password(temporary_password))
    return user


def can_deactivate_user(user_id):
    user = User.query.filter_by(id=user_id, is_deleted=False).one_or_none()
    if not user or not user.is_active:
        return True

    manager_count = (
        User.query.join(AccessMatrix, AccessMatrix.user_id == User.id)
        .filter(
            User.is_deleted.is_(False),
            User.is_active.is_(True),
            AccessMatrix.is_deleted.is_(False),
            AccessMatrix.scope_type == "global",
            AccessMatrix.can_manage_users.is_(True),
        )
        .distinct(User.id)
        .count()
    )
    has_manage_users = (
        AccessMatrix.query.filter_by(
            user_id=user_id,
            scope_type="global",
            can_manage_users=True,
            is_deleted=False,
        ).first()
        is not None
    )
    return not (has_manage_users and manager_count <= 1)


def set_user_active(user_id, is_active):
    user = User.query.filter_by(id=user_id, is_deleted=False).one_or_none()
    if not user:
        return None, "User not found."
    if not is_active and not can_deactivate_user(user_id):
        return None, "Cannot deactivate the last active user with global user-management permission."
    user.is_active = is_active
    return user, None
