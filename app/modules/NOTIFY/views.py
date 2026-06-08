from flask import Blueprint, jsonify, render_template
from app.common.auth import current_user, require_login
from app.common.decorators import require_permission
from app.common.permissions import has_permission
from app.modules.NOTIFY.service import (
    get_recent_notifications,
    get_unread_count,
    mark_as_read,
    mark_all_as_read
)

MODULE_CODE = "NOTIFY"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_login
def index():
    """
    Renders the main notifications page listing all notifications for the user.
    """
    user = current_user()
    # Fetch a larger list for the main page (e.g. 50 recent notifications)
    notifications = get_recent_notifications(user.id, limit=50)

    # Resolve links dynamically
    resolved_notifications = []
    for n in notifications:
        link_url = "#"
        if n.entity_type == "submission":
            if has_permission(user.id, "submission", "approve", scope_site_id=None) or \
               has_permission(user.id, "submission", "reject", scope_site_id=None):
                link_url = f"/module/APPROV/submissions/{n.entity_id}"
            else:
                link_url = f"/module/SUBMIT/submissions/{n.entity_id}"

        resolved_notifications.append({
            "id": n.id,
            "event_type": n.event_type,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at,
            "link_url": link_url
        })

    return render_template(
        "modules/NOTIFY/notifications.html",
        module_code=MODULE_CODE,
        notifications=resolved_notifications
    )


@bp.route("/recent")
@require_login
def recent():
    """
    JSON API returning the 10 most recent notifications for the logged-in user.
    """
    user = current_user()
    notifications = get_recent_notifications(user.id, limit=10)
    data = []
    for n in notifications:
        link_url = "#"
        if n.entity_type == "submission":
            if has_permission(user.id, "submission", "approve", scope_site_id=None) or \
               has_permission(user.id, "submission", "reject", scope_site_id=None):
                link_url = f"/module/APPROV/submissions/{n.entity_id}"
            else:
                link_url = f"/module/SUBMIT/submissions/{n.entity_id}"

        data.append({
            "id": n.id,
            "event_type": n.event_type,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
            "link_url": link_url
        })
    return jsonify({"status": "success", "data": data})


@bp.route("/unread-count")
@require_login
def unread_count():
    """
    JSON API returning the count of unread notifications for the logged-in user.
    """
    user = current_user()
    count = get_unread_count(user.id)
    return jsonify({"status": "success", "data": {"unread_count": count}})


@bp.route("/<int:notification_id>/read", methods=["POST"])
@require_login
def mark_read(notification_id):
    """
    JSON API to mark a specific notification as read.
    """
    user = current_user()
    try:
        mark_as_read(notification_id, user.id)
        return jsonify({"status": "success", "message": "Notification marked as read."})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 403
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/mark-all-read", methods=["POST"])
@require_login
def mark_all_read():
    """
    JSON API to mark all notifications as read for the logged-in user.
    """
    user = current_user()
    try:
        count = mark_all_as_read(user.id)
        return jsonify({
            "status": "success",
            "message": f"All {count} notifications marked as read."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
