import hmac
import secrets

from flask import abort, current_app, request, session


CSRF_FIELD_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRFToken"
CSRF_SESSION_KEY = "_csrf_token"
CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def csrf_token():
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def _submitted_token():
    return request.headers.get(CSRF_HEADER_NAME) or request.form.get(CSRF_FIELD_NAME)


def _csrf_enabled():
    if current_app.config.get("CSRF_PROTECTION_ENABLED") is False:
        return False
    if current_app.testing and not current_app.config.get("CSRF_TESTING"):
        return False
    return True


def validate_csrf():
    if request.method not in CSRF_METHODS or not _csrf_enabled():
        return None

    expected = session.get(CSRF_SESSION_KEY)
    provided = _submitted_token()
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        abort(403)
    return None
