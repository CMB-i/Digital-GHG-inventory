from functools import wraps

from flask import render_template, request

from app.common.auth import current_user, require_login
from app.common.permissions import has_permission


def require_permission(entity_type, action, scope_site_id_param=None, entity_id_param=None):
    def decorator(view_func):
        @require_login
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = current_user()
            scope_site_id = kwargs.get(scope_site_id_param) if scope_site_id_param else None
            
            # Smart site ID resolution for site-scoped checks
            if not scope_site_id:
                if "site_id" in kwargs:
                    scope_site_id = kwargs["site_id"]
                elif request.args.get("site_id"):
                    try:
                        scope_site_id = int(request.args.get("site_id"))
                    except ValueError:
                        pass
                elif request.form.get("site_id"):
                    try:
                        scope_site_id = int(request.form.get("site_id"))
                    except ValueError:
                        pass
                elif request.is_json:
                    try:
                        scope_site_id = request.json.get("site_id")
                    except Exception:
                        pass
            
            # Resolve site_id from submission if submission_id is present
            if not scope_site_id and "submission_id" in kwargs:
                from app.modules.SUBMIT.model import Submission
                sub = Submission.query.get(kwargs["submission_id"])
                if sub:
                    scope_site_id = sub.site_id
            
            # Resolve site_id from period_id / reporting_period_id if present
            if not scope_site_id:
                p_id = kwargs.get("period_id") or kwargs.get("reporting_period_id")
                if p_id:
                    from app.modules.PERIOD.model import ReportingPeriod
                    period = ReportingPeriod.query.get(p_id)
                    if period:
                        scope_site_id = period.site_id

            entity_id = kwargs.get(entity_id_param) if entity_id_param else None
            actions = action if isinstance(action, (tuple, list, set)) else (action,)
            allowed = any(
                has_permission(user.id, entity_type, item, scope_site_id, entity_id)
                for item in actions
            )
            if not allowed:
                return render_template("no_access.html"), 403
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


login_required = require_login
permission_required = require_permission
