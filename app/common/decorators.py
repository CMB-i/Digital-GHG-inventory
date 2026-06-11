from functools import wraps

from flask import jsonify, render_template

from app.common.auth import current_user, is_api_request, require_login
from app.common.permissions import has_permission


def require_permission(entity_type, action, scope_site_id_param=None, entity_id_param=None):
    def decorator(view_func):
        @require_login
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = current_user()
            scope_site_id = kwargs.get(scope_site_id_param) if scope_site_id_param else None
            entity_id = kwargs.get(entity_id_param) if entity_id_param else None
            actions = action if isinstance(action, (tuple, list, set)) else (action,)
            allowed = any(
                has_permission(user.id, entity_type, item, scope_site_id, entity_id)
                for item in actions
            )
            if not allowed:
                if is_api_request():
                    return jsonify({"error": "Permission denied."}), 403
                return render_template("no_access.html"), 403
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


login_required = require_login
permission_required = require_permission
