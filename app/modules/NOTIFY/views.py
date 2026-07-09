from datetime import datetime, timezone
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from app.common.auth import current_user, require_login
from app.common.decorators import require_permission
from app.common.permissions import has_permission
from app.database import db
from app.modules.NOTIFY.model import NotificationConfig, UserNotificationPreference
from app.modules.NOTIFY.service import (
    get_recent_notifications,
    get_unread_count,
    mark_as_read,
    mark_all_as_read
)
from app.modules.SUBMIT.service import fy_start_year_for

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
        fy_start = fy_start_year_for(period.year, period.month)
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
                    f"&form_id={submission.form_id}&fy={fy_start_year_for(period.year, period.month)}"
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


@bp.route("/settings", methods=["GET", "POST"])
@require_login
def settings():
    """
    Enables users to manage their notification preferences (In-App, Desktop, Email, WhatsApp).
    """
    user = current_user()
    from app.modules.NOTIFY.service import get_user_preferences
    
    pref = UserNotificationPreference.query.filter_by(user_id=user.id).first()
    
    if request.method == "POST":
        if not pref:
            pref = UserNotificationPreference(user_id=user.id)
            db.session.add(pref)
            
        pref.pref_in_app = request.form.get("pref_in_app") == "on"
        pref.pref_desktop = request.form.get("pref_desktop") == "on"
        pref.pref_email = request.form.get("pref_email") == "on"
        pref.pref_whatsapp = request.form.get("pref_whatsapp") == "on"
        db.session.commit()
        flash("Notification preferences updated.", "success")
        return redirect(url_for("notify.settings"))
        
    if not pref:
        pref = get_user_preferences(user.id)
        
    return render_template(
        "modules/NOTIFY/settings.html",
        module_code=MODULE_CODE,
        pref=pref
    )


@bp.route("/manager")
@require_permission("notification", "view")
def manager():
    """
    Lists notification configurations for administrator review.
    """
    user = current_user()
    configs = NotificationConfig.query.filter_by(is_deleted=False).order_by(NotificationConfig.id.asc()).all()
    
    from app.modules.USRMGMT.model import User
    all_users = User.query.filter_by(is_deleted=False, is_active=True).order_by(User.full_name.asc()).all()
    
    perm_create = has_permission(user.id, "notification", "create")
    perm_edit = has_permission(user.id, "notification", "edit")
    perm_delete = has_permission(user.id, "notification", "delete")
    
    return render_template(
        "modules/NOTIFY/manager.html",
        module_code=MODULE_CODE,
        configs=configs,
        all_users=all_users,
        perm_create=perm_create,
        perm_edit=perm_edit,
        perm_delete=perm_delete
    )


@bp.route("/manager/create", methods=["POST"])
@require_permission("notification", "create")
def manager_create():
    """
    Creates a new notification configuration.
    """
    user = current_user()
    try:
        name = request.form.get("name")
        event_type = request.form.get("event_type")
        message_template = request.form.get("message_template")
        recipient_type = request.form.get("recipient_type")
        
        target_entity_type = request.form.get("target_entity_type") or None
        target_permission = request.form.get("target_permission") or None
        
        selected_uids = request.form.getlist("recipient_user_ids")
        recipient_user_ids = ",".join(selected_uids) if selected_uids else None
        
        dynamic_role = request.form.get("dynamic_role") or None
        
        selected_channels = request.form.getlist("channels")
        channels = ",".join(selected_channels) if selected_channels else "in_app"
        
        is_active = request.form.get("is_active") == "on"
        
        config = NotificationConfig(
            name=name,
            event_type=event_type,
            message_template=message_template,
            recipient_type=recipient_type,
            target_entity_type=target_entity_type,
            target_permission=target_permission,
            recipient_user_ids=recipient_user_ids,
            dynamic_role=dynamic_role,
            channels=channels,
            is_active=is_active,
            created_by=user.id,
            updated_by=user.id
        )
        db.session.add(config)
        db.session.commit()
        flash("Notification configuration created.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating configuration: {e}", "error")
        
    return redirect(url_for("notify.manager"))


@bp.route("/manager/edit/<int:config_id>", methods=["POST"])
@require_permission("notification", "edit")
def manager_edit(config_id):
    """
    Updates an existing notification configuration.
    """
    user = current_user()
    config = NotificationConfig.query.filter_by(id=config_id, is_deleted=False).first()
    if not config:
        flash("Configuration not found.", "error")
        return redirect(url_for("notify.manager"))
        
    try:
        config.name = request.form.get("name")
        config.event_type = request.form.get("event_type")
        config.message_template = request.form.get("message_template")
        config.recipient_type = request.form.get("recipient_type")
        
        config.target_entity_type = request.form.get("target_entity_type") or None
        config.target_permission = request.form.get("target_permission") or None
        
        selected_uids = request.form.getlist("recipient_user_ids")
        config.recipient_user_ids = ",".join(selected_uids) if selected_uids else None
        
        config.dynamic_role = request.form.get("dynamic_role") or None
        
        selected_channels = request.form.getlist("channels")
        config.channels = ",".join(selected_channels) if selected_channels else "in_app"
        
        config.is_active = request.form.get("is_active") == "on"
        config.updated_by = user.id
        
        db.session.commit()
        flash("Notification configuration updated.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating configuration: {e}", "error")
        
    return redirect(url_for("notify.manager"))


@bp.route("/manager/delete/<int:config_id>", methods=["POST"])
@require_permission("notification", "delete")
def manager_delete(config_id):
    """
    Soft deletes a notification configuration.
    """
    user = current_user()
    config = NotificationConfig.query.filter_by(id=config_id, is_deleted=False).first()
    if not config:
        flash("Configuration not found.", "error")
        return redirect(url_for("notify.manager"))
        
    try:
        config.is_deleted = True
        config.deleted_at = datetime.now(timezone.utc)
        config.deleted_by = user.id
        db.session.commit()
        flash("Notification configuration deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting configuration: {e}", "error")
        
    return redirect(url_for("notify.manager"))
