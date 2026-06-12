from flask import Blueprint, jsonify, render_template
from app.common.auth import current_user, require_login
from app.common.permissions import has_permission
from app.modules.NOTIFY.service import (
    get_recent_notifications,
    get_unread_count,
    mark_as_read,
    mark_all_as_read
)

MODULE_CODE = "NOTIFY"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


def _resolve_notification_link(notification, user):
    link_url = "#"
    if notification.entity_type == "reporting_period":
        from app.modules.PERIOD.model import ReportingPeriod

        period = ReportingPeriod.query.get(notification.entity_id)
        if not period:
            return link_url
        can_enter = (
            has_permission(user.id, "submission", "create", scope_site_id=period.site_id) or
            has_permission(user.id, "submission", "edit", scope_site_id=period.site_id) or
            has_permission(user.id, "submission", "submit", scope_site_id=period.site_id)
        )
        if not can_enter:
            return link_url
        fy_start = period.year if period.month >= 4 else period.year - 1
        return f"/module/SUBMIT/annual?site_id={period.site_id}&fy={fy_start}&month={period.month}"

    if notification.entity_type != "submission":
        return link_url

    from app.modules.SUBMIT.model import Submission

    submission = Submission.query.get(notification.entity_id)
    if not submission:
        return link_url

    if submission.status == "Changes Requested" and submission.submitted_by == user.id:
        if submission.package_id:
            from app.modules.PERIOD.model import ReportingPeriod

            period = ReportingPeriod.query.get(submission.reporting_period_id)
            if period:
                return (
                    f"/module/SUBMIT/annual?site_id={submission.site_id}"
                    f"&form_id={submission.form_id}&fy={period.year if period.month >= 4 else period.year - 1}"
                    f"&month={period.month}"
                )
        return f"/module/SUBMIT/submissions/{notification.entity_id}"

    if submission.package_id and has_permission(user.id, "submission", "view", scope_site_id=submission.site_id):
        return f"/module/APPROV/packages/{submission.package_id}"

    can_review = (
        has_permission(user.id, "submission", "approve", scope_site_id=submission.site_id) or
        has_permission(user.id, "submission", "reject", scope_site_id=submission.site_id)
    )
    if can_review:
        if submission.package_id:
            return f"/module/APPROV/packages/{submission.package_id}"
        return f"/module/APPROV/submissions/{notification.entity_id}"

    return f"/module/SUBMIT/submissions/{notification.entity_id}"


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
        resolved_notifications.append({
            "id": n.id,
            "event_type": n.event_type,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at,
            "link_url": _resolve_notification_link(n, user)
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
        data.append({
            "id": n.id,
            "event_type": n.event_type,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
            "link_url": _resolve_notification_link(n, user)
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
