from datetime import datetime, timezone
from app.database import db
from app.modules.NOTIFY.model import Notification


def create_notification(user_id, event_type, entity_type, entity_id, message, channel="in_app"):
    """
    Creates and saves a single notification record for a user.
    """
    notification = Notification(
        user_id=user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        channel=channel
    )
    db.session.add(notification)
    db.session.flush()
    return notification


def create_notifications_for_users(user_ids, event_type, entity_type, entity_id, message, channel="in_app"):
    """
    Creates notifications for multiple users in bulk.
    """
    notifications = []
    for u_id in user_ids:
        n = Notification(
            user_id=u_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            message=message,
            channel=channel
        )
        db.session.add(n)
        notifications.append(n)
    db.session.flush()
    return notifications


def notify_level_approvers(submission_id):
    """
    Finds the active workflow level for the submission and notifies its assigned approvers
    who have the site-level can_approve permission. Prevents self-approval notifications.
    """
    from app.modules.SUBMIT.model import Submission
    from app.modules.WFLWBLD.model import WorkflowLevel, WorkflowLevelApprover
    from app.modules.SITEMST.model import Site
    from app.modules.FORMBLD.model import Form
    from app.common.permissions import has_permission

    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        return []

    lvl = WorkflowLevel.query.filter_by(
        workflow_version_id=submission.workflow_version_id,
        level_number=submission.current_level,
        is_deleted=False
    ).first()
    if not lvl:
        return []

    level_approvers = WorkflowLevelApprover.query.filter_by(
        workflow_level_id=lvl.id,
        is_deleted=False
    ).all()

    site = Site.query.get(submission.site_id)
    form = Form.query.get(submission.form_id)
    site_name = site.name if site else "Unknown Site"
    form_name = form.name if form else "Unknown Form"

    msg = f"Submission from {site_name} for {form_name} is now pending your Level {submission.current_level} review."

    notified = []
    for app in level_approvers:
        # Self-approval guard: do not notify the submitter
        if app.user_id == submission.submitted_by:
            continue
        # Check permissions (approvers must have can_approve on submission for that site)
        if has_permission(app.user_id, "submission", "approve", scope_site_id=submission.site_id):
            n = create_notification(
                user_id=app.user_id,
                event_type="SUBMITTED",
                entity_type="submission",
                entity_id=submission_id,
                message=msg
            )
            notified.append(n)
    return notified


def notify_spoc(submission_id, event_type, message):
    """
    Sends a workflow status update notification to the SPOC who submitted the form.
    """
    from app.modules.SUBMIT.model import Submission
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted or not submission.submitted_by:
        return None

    return create_notification(
        user_id=submission.submitted_by,
        event_type=event_type,
        entity_type="submission",
        entity_id=submission_id,
        message=message
    )


def mark_as_read(notification_id, user_id):
    """
    Marks a single notification as read by the recipient.
    """
    notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if not notification:
        raise ValueError("Notification not found or access denied.")
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.session.commit()
    return notification


def mark_all_as_read(user_id):
    """
    Marks all unread notifications of the user as read.
    """
    unread = Notification.query.filter_by(user_id=user_id, is_read=False).all()
    now = datetime.now(timezone.utc)
    for n in unread:
        n.is_read = True
        n.read_at = now
    db.session.commit()
    return len(unread)


def get_unread_count(user_id):
    """
    Gets the count of unread notifications for a user.
    """
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def get_recent_notifications(user_id, limit=10):
    """
    Retrieves the most recent notifications for a user.
    """
    return Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(limit).all()
