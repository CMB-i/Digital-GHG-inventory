import bcrypt
import secrets
from datetime import datetime, timedelta, timezone

from app.common.validators import (
    ValidationError,
    validate_email,
    validate_full_name,
    validate_phone,
    validate_temporary_password,
)
from app.database import db
from app.modules.AUDITL.service import log_audit
from app.modules.ACCESS.service import count_global_user_managers, get_user_permissions
from app.modules.NOTIFY.service import send_mock_email
from app.modules.USRMGMT.model import PasswordResetOTP, User


OTP_EXPIRY_MINUTES = 10
OTP_RATE_LIMIT_MAX_REQUESTS = 3
OTP_RATE_LIMIT_WINDOW_MINUTES = 15
OTP_MAX_FAILED_ATTEMPTS = 5
RESET_CODE_ERROR = "Invalid or expired reset code."


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


def _utc_now():
    return datetime.now(timezone.utc)


def _normalize_db_datetime(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _generate_otp_code():
    return f"{secrets.randbelow(1000000):06d}"


def request_password_reset_otp(email):
    validated_email = validate_email(email)
    now = _utc_now()
    window_start = now - timedelta(minutes=OTP_RATE_LIMIT_WINDOW_MINUTES)

    recent_count = PasswordResetOTP.query.filter(
        PasswordResetOTP.email == validated_email,
        PasswordResetOTP.created_at >= window_start,
    ).count()
    if recent_count >= OTP_RATE_LIMIT_MAX_REQUESTS:
        raise ValidationError("Too many reset code requests. Try again in 15 minutes.")

    user = User.query.filter_by(email=validated_email, is_deleted=False).one_or_none()
    if not user or not user.is_active:
        return False, None

    PasswordResetOTP.query.filter(
        PasswordResetOTP.email == validated_email,
        PasswordResetOTP.used.is_(False),
    ).update({"used": True, "used_at": now}, synchronize_session=False)

    otp_code = _generate_otp_code()
    reset_otp = PasswordResetOTP(
        user_id=user.id,
        email=validated_email,
        otp_hash=hash_password(otp_code),
        created_at=now,
        expires_at=now + timedelta(minutes=OTP_EXPIRY_MINUTES),
        used=False,
    )
    db.session.add(reset_otp)
    db.session.flush()

    subject = "Digital GHG Inventory password reset code"
    body = (
        f"Your password reset code is {otp_code}.\n\n"
        f"This code expires in {OTP_EXPIRY_MINUTES} minutes. If you did not request it, ignore this email."
    )
    sent, error = send_mock_email(validated_email, subject, body)
    if not sent:
        raise ValidationError(f"Could not send reset code: {error}")
    return True, reset_otp


def reset_password_with_otp(email, otp_code, new_password):
    validated_email = validate_email(email)
    otp_value = (otp_code or "").strip()
    if not otp_value.isdigit() or len(otp_value) != 6:
        raise ValidationError("Enter the 6-digit reset code.")

    validated_password = validate_temporary_password(new_password)
    now = _utc_now()
    reset_otp = PasswordResetOTP.query.filter(
        PasswordResetOTP.email == validated_email,
        PasswordResetOTP.used.is_(False),
    ).order_by(PasswordResetOTP.created_at.desc()).first()

    if not reset_otp:
        raise ValidationError(RESET_CODE_ERROR)
    if _normalize_db_datetime(reset_otp.expires_at) <= now:
        reset_otp.used = True
        reset_otp.used_at = now
        raise ValidationError(RESET_CODE_ERROR)
    if reset_otp.locked_at is not None:
        raise ValidationError(RESET_CODE_ERROR)
    if not verify_password(otp_value, reset_otp.otp_hash):
        reset_otp.failed_attempts = (reset_otp.failed_attempts or 0) + 1
        if reset_otp.failed_attempts >= OTP_MAX_FAILED_ATTEMPTS:
            reset_otp.locked_at = now
            reset_otp.used = True
            reset_otp.used_at = now
        raise ValidationError(RESET_CODE_ERROR)

    user = User.query.filter_by(id=reset_otp.user_id, is_deleted=False).one_or_none()
    if not user or not user.is_active:
        raise ValidationError(RESET_CODE_ERROR)

    user.password_hash = hash_password(validated_password)
    user.session_version = (user.session_version or 0) + 1
    user.updated_by = user.id
    reset_otp.used = True
    reset_otp.used_at = now
    log_audit(
        user.id,
        "user",
        user.id,
        "USER_PASSWORD_RESET",
        metadata={"password_reset": True, "source": "forgot_password"},
    )
    return user


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


def _user_snapshot(user):
    return {
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
    }


def update_user(user_id, full_name, email, phone, actor_id):
    user = User.query.filter_by(id=user_id, is_deleted=False).one_or_none()
    if not user:
        return None
    old_values = _user_snapshot(user)
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
    user.updated_by = actor_id
    log_audit(
        actor_id,
        "user",
        user.id,
        "USER_UPDATED",
        old_values=old_values,
        new_values=_user_snapshot(user),
    )
    return user


def set_temporary_password(user_id, temporary_password, actor_id):
    user = User.query.filter_by(id=user_id, is_deleted=False).one_or_none()
    if not user:
        return None
    user.password_hash = hash_password(validate_temporary_password(temporary_password))
    user.updated_by = actor_id
    log_audit(
        actor_id,
        "user",
        user.id,
        "USER_PASSWORD_RESET",
        metadata={"password_reset": True},
    )
    return user


def can_deactivate_user(user_id):
    """
    Resolved through ACCESS's get_user_permissions()/count_global_user_managers()
    instead of a raw AccessMatrix scan, so this can never quietly disagree with
    the equivalent guard on the permission-matrix side (upsert_access_row) --
    see Consistency Guideline #3.
    """
    user = User.query.filter_by(id=user_id, is_deleted=False).one_or_none()
    if not user or not user.is_active:
        return True

    has_manage_users = get_user_permissions(
        user_id, scope_type="global", entity_type="user"
    ).get("can_manage_users")
    if not has_manage_users:
        return True

    return count_global_user_managers(exclude_user_id=user_id) > 0


def set_user_active(user_id, is_active, actor_id):
    if not is_active and user_id == actor_id:
        return None, "You cannot deactivate your own account."
    user = User.query.filter_by(id=user_id, is_deleted=False).one_or_none()
    if not user:
        return None, "User not found."
    if not is_active and not can_deactivate_user(user_id):
        return None, "Cannot deactivate the last active user with global user-management permission."
    old_values = {"is_active": user.is_active}
    user.is_active = is_active
    user.updated_by = actor_id
    action = "USER_ACTIVATED" if user.is_active else "USER_DEACTIVATED"
    log_audit(
        actor_id,
        "user",
        user.id,
        action,
        old_values=old_values,
        new_values={"is_active": user.is_active},
    )
    return user, None
