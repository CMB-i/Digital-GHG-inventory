from functools import wraps

from flask import redirect, request, session, url_for


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    from app.modules.USRMGMT.model import User

    return User.query.filter_by(id=user_id, is_active=True, is_deleted=False).one_or_none()


def require_login(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.full_path))
        return view_func(*args, **kwargs)

    return wrapper
