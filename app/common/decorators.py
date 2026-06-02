from functools import wraps

from flask import redirect, url_for


def login_required(view_func):
    # TODO Phase 2: replace with real session/auth enforcement.
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        return view_func(*args, **kwargs)

    return wrapper


def permission_required(permission_code):
    # TODO Phase 3: check module/action permissions from access configuration.
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not permission_code:
                return redirect(url_for("no_access"))
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
