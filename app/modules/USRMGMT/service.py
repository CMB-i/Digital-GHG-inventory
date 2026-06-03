import bcrypt

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
