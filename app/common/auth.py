from functools import wraps
from urllib.parse import unquote, urlsplit

from flask import jsonify, redirect, request, session, url_for


def is_safe_internal_path(target):
    if not target:
        return False
    if any(char in target for char in ("\r", "\n")):
        return False
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not parts.path.startswith("/") or parts.path.startswith("//"):
        return False
    decoded = target
    for _ in range(3):
        decoded = unquote(decoded)
        if any(char in decoded for char in ("\r", "\n")):
            return False
        if decoded.startswith("//") or decoded.startswith("/\\") or decoded.startswith("\\/") or "\\" in decoded:
            return False
    return True


def is_api_request():
    return request.path.startswith("/api/") or "/api/" in request.path


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    from app.modules.USRMGMT.model import User

    user = User.query.filter_by(id=user_id, is_active=True, is_deleted=False).one_or_none()
    if user and user.session_version != session.get("user_session_version", 0):
        session.clear()
        return None
    return user


def require_login(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            if is_api_request():
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("auth.login", next=request.full_path))
        return view_func(*args, **kwargs)

    return wrapper
