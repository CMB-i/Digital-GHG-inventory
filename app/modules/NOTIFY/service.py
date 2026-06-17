import os
from datetime import datetime, timezone
from app.database import db
from app.modules.NOTIFY.model import Notification, UserNotificationPreference, NotificationConfig


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


def send_mock_email(to_email, subject, body):
    """
    Simulates sending an email by logging to the console and writing to uploads/mock_emails.log
    """
    log_dir = "/Users/shubhamindulkar/Digital-GHG-inventory/uploads"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "mock_emails.log")
    
    log_entry = (
        f"========================================\n"
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
        f"To: {to_email}\n"
        f"Subject: {subject}\n"
        f"Body:\n{body}\n"
        f"========================================\n\n"
    )
    
    with open(log_path, "a") as f:
        f.write(log_entry)
    print(f"[MOCK EMAIL SENT] To: {to_email} | Subject: {subject}")


def send_mock_whatsapp(to_phone, body):
    """
    Simulates sending a WhatsApp message by logging to the console and writing to uploads/mock_whatsapp.log
    """
    log_dir = "/Users/shubhamindulkar/Digital-GHG-inventory/uploads"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "mock_whatsapp.log")
    
    log_entry = (
        f"========================================\n"
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
        f"To Phone: {to_phone}\n"
        f"Message:\n{body}\n"
        f"========================================\n\n"
    )
    
    with open(log_path, "a") as f:
        f.write(log_entry)
    print(f"[MOCK WHATSAPP SENT] To: {to_phone} | Message: {body}")


def get_user_preferences(user_id):
    """
    Gets user notification preferences or returns a default instance.
    """
    pref = UserNotificationPreference.query.filter_by(user_id=user_id).first()
    if not pref:
        pref = UserNotificationPreference(
            user_id=user_id,
            pref_in_app=True,
            pref_desktop=False,
            pref_email=False,
            pref_whatsapp=False
        )
    return pref


def resolve_recipients(config, entity_type, entity_id, context):
    """
    Resolves the list of User objects who should receive the notification based on the config.
    """
    from app.modules.USRMGMT.model import User
    from app.modules.ACCESS.model import AccessMatrix
    
    recipients = []
    
    if config.recipient_type == "users":
        if config.recipient_user_ids:
            user_ids = [int(uid.strip()) for uid in config.recipient_user_ids.split(",") if uid.strip().isdigit()]
            if user_ids:
                recipients = User.query.filter(User.id.in_(user_ids), User.is_active == True, User.is_deleted == False).all()
                
    elif config.recipient_type == "role":
        site_id = context.get("site_id")
        perm_flag = f"can_{config.target_permission}"
        if not hasattr(AccessMatrix, perm_flag):
            return []
            
        query = AccessMatrix.query.filter(
            AccessMatrix.entity_type == config.target_entity_type,
            AccessMatrix.is_deleted == False,
            getattr(AccessMatrix, perm_flag) == True
        )
        
        if site_id:
            query = query.filter(
                (AccessMatrix.scope_type == "global") | 
                ((AccessMatrix.scope_type == "site") & (AccessMatrix.scope_site_id == site_id))
            )
        else:
            query = query.filter(AccessMatrix.scope_type == "global")
            
        rows = query.all()
        user_ids = {row.user_id for row in rows}
        if user_ids:
            recipients = User.query.filter(User.id.in_(list(user_ids)), User.is_active == True, User.is_deleted == False).all()
            
    elif config.recipient_type == "dynamic":
        site_id = context.get("site_id")
        
        if config.dynamic_role == "spoc":
            submitter_id = context.get("submitter_id")
            if submitter_id:
                u = User.query.filter_by(id=submitter_id, is_active=True, is_deleted=False).first()
                if u:
                    recipients = [u]
                    
        elif config.dynamic_role == "level_approvers":
            from app.modules.SUBMIT.model import Submission
            from app.modules.WFLWBLD.model import WorkflowLevel
            from app.modules.WFLWBLD.service import get_eligible_level_approvers
            from app.common.permissions import has_permission
            
            submission_id = entity_id if entity_type == "submission" else context.get("submission_id")
            if submission_id:
                submission = Submission.query.get(submission_id)
                if submission and not submission.is_deleted:
                    lvl = WorkflowLevel.query.filter_by(
                        workflow_version_id=submission.workflow_version_id,
                        level_number=submission.current_level,
                        is_deleted=False
                    ).first()
                    if lvl:
                        level_approvers = get_eligible_level_approvers(lvl, submission.site_id)
                        user_ids = []
                        for app in level_approvers:
                            if app.user_id == submission.submitted_by:
                                continue
                            if has_permission(app.user_id, "submission", "approve", scope_site_id=submission.site_id):
                                user_ids.append(app.user_id)
                        if user_ids:
                            recipients = User.query.filter(User.id.in_(user_ids), User.is_active == True, User.is_deleted == False).all()
                            
        elif config.dynamic_role == "site_admins":
            query = AccessMatrix.query.filter(
                AccessMatrix.entity_type == "site",
                AccessMatrix.is_deleted == False,
                AccessMatrix.can_edit == True
            )
            if site_id:
                query = query.filter(
                    (AccessMatrix.scope_type == "global") | 
                    ((AccessMatrix.scope_type == "site") & (AccessMatrix.scope_site_id == site_id))
                )
            else:
                query = query.filter(AccessMatrix.scope_type == "global")
            rows = query.all()
            user_ids = {row.user_id for row in rows}
            if user_ids:
                recipients = User.query.filter(User.id.in_(list(user_ids)), User.is_active == True, User.is_deleted == False).all()
                
    return recipients


def dispatch_notification_event(event_type, entity_type, entity_id, context):
    """
    Finds active configurations for event_type, formats template, resolves recipients,
    and dispatches via preferred channels.
    """
    configs = NotificationConfig.query.filter_by(
        event_type=event_type,
        is_active=True,
        is_deleted=False
    ).all()
    
    dispatched = []
    
    for config in configs:
        recipients = resolve_recipients(config, entity_type, entity_id, context)
        config_channels = [c.strip() for c in config.channels.split(",") if c.strip()]
        
        for user in recipients:
            pref = get_user_preferences(user.id)
            
            try:
                message = config.message_template.format(**context)
            except Exception as e:
                message = config.message_template
                print(f"[NOTIFICATION ERROR] Message formatting failed: {e}")
            
            # 1. In-App delivery
            if "in_app" in config_channels and pref.pref_in_app:
                n = create_notification(
                    user_id=user.id,
                    event_type=event_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    message=message,
                    channel="in_app"
                )
                dispatched.append(n)
                
            # 2. Desktop delivery
            if "desktop" in config_channels and pref.pref_desktop:
                n = create_notification(
                    user_id=user.id,
                    event_type=event_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    message=message,
                    channel="desktop"
                )
                dispatched.append(n)
                
            # 3. Email delivery
            if "email" in config_channels and pref.pref_email:
                subject = f"GHG Platform Notification: {config.name}"
                send_mock_email(user.email, subject, message)
                
            # 4. WhatsApp delivery
            if "whatsapp" in config_channels and pref.pref_whatsapp:
                phone = user.phone or "Unknown Phone"
                send_mock_whatsapp(phone, message)
                
    return dispatched


def notify_level_approvers(submission_id):
    """
    Finds the active workflow level for the submission and notifies its assigned approvers.
    Delegates to the configured trigger-event system.
    """
    from app.modules.SUBMIT.model import Submission
    from app.modules.SITEMST.model import Site
    from app.modules.FORMBLD.model import Form
    from app.modules.SUBMIT.service import human_sheet_label

    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        return []

    site = Site.query.get(submission.site_id)
    form = Form.query.get(submission.form_id)
    site_name = site.name if site else "Unknown Site"
    form_name = human_sheet_label(form)

    context = {
        "site_id": submission.site_id,
        "site_name": site_name,
        "form_name": form_name,
        "level_number": submission.current_level,
        "submission_id": submission_id,
        "submitter_id": submission.submitted_by
    }

    return dispatch_notification_event(
        event_type="SUBMISSION_SUBMITTED",
        entity_type="submission",
        entity_id=submission_id,
        context=context
    )


def notify_spoc(submission_id, event_type, message):
    """
    Sends a workflow status update notification to the SPOC who submitted the form.
    Delegates to the configured trigger-event system.
    """
    from app.modules.SUBMIT.model import Submission
    from app.modules.SITEMST.model import Site
    from app.modules.FORMBLD.model import Form
    from app.modules.SUBMIT.service import format_period_label, human_sheet_label
    from app.modules.PERIOD.model import ReportingPeriod

    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted or not submission.submitted_by:
        return None

    site = Site.query.get(submission.site_id)
    form = Form.query.get(submission.form_id)
    period = ReportingPeriod.query.get(submission.reporting_period_id)

    site_name = site.name if site else "Unknown Site"
    form_name = human_sheet_label(form)
    period_label = format_period_label(period.year, period.month) if period else ""

    from app.modules.APPROV.model import ApprovalAction
    last_action = ApprovalAction.query.filter_by(submission_id=submission_id).order_by(ApprovalAction.created_at.desc()).first()
    reason = last_action.comments if last_action else ""

    mapped_event_type = f"SUBMISSION_{event_type.upper()}"
    if event_type.upper() not in ("SUBMISSION_APPROVED", "SUBMISSION_REJECTED", "SUBMISSION_CHANGES_REQUESTED"):
        if event_type.upper() == "APPROVED":
            mapped_event_type = "SUBMISSION_APPROVED"
        elif event_type.upper() == "REJECTED":
            mapped_event_type = "SUBMISSION_REJECTED"
        elif event_type.upper() in ("CHANGES_REQUESTED", "CORRECTIONS_REQUESTED"):
            mapped_event_type = "SUBMISSION_CHANGES_REQUESTED"

    context = {
        "site_id": submission.site_id,
        "site_name": site_name,
        "form_name": form_name,
        "period_label": period_label,
        "level_number": submission.current_level,
        "reason": reason,
        "status": submission.status,
        "submission_id": submission_id,
        "submitter_id": submission.submitted_by
    }

    results = dispatch_notification_event(
        event_type=mapped_event_type,
        entity_type="submission",
        entity_id=submission_id,
        context=context
    )
    return results[0] if results else None


def notify_period_open_for_entry(period_id):
    """
    Notify users who can create/edit/submit submissions for this period's site.
    Delegates to the configured trigger-event system.
    """
    from app.modules.PERIOD.model import ReportingPeriod
    from app.modules.SITEMST.model import Site
    from app.modules.SUBMIT.service import format_period_label

    period = ReportingPeriod.query.filter_by(id=period_id, is_deleted=False).first()
    if not period or period.status not in ("OPEN", "REOPENED"):
        return []

    site = Site.query.get(period.site_id)
    site_name = site.name if site else "Unknown Site"
    period_label = format_period_label(period.year, period.month)

    context = {
        "site_id": period.site_id,
        "site_name": site_name,
        "period_label": period_label,
        "period_id": period_id
    }

    return dispatch_notification_event(
        event_type="PERIOD_OPEN",
        entity_type="reporting_period",
        entity_id=period_id,
        context=context
    )


def seed_default_notification_configs():
    """
    Creates the default notification configurations if they do not exist.
    """
    # Check if there are already configurations
    if NotificationConfig.query.filter_by(is_deleted=False).count() > 0:
        return
        
    defaults = [
        {
            "name": "Pending Submission Review",
            "event_type": "SUBMISSION_SUBMITTED",
            "message_template": "Submission from {site_name} for {form_name} is now pending your Level {level_number} review.",
            "recipient_type": "dynamic",
            "dynamic_role": "level_approvers",
            "channels": "in_app,desktop,email,whatsapp",
            "created_by": 1,
            "updated_by": 1
        },
        {
            "name": "Submission Approved Notification",
            "event_type": "SUBMISSION_APPROVED",
            "message_template": "{form_name} submission for {site_name} ({period_label}) has been approved.",
            "recipient_type": "dynamic",
            "dynamic_role": "spoc",
            "channels": "in_app,desktop,email,whatsapp",
            "created_by": 1,
            "updated_by": 1
        },
        {
            "name": "Submission Rejected Notification",
            "event_type": "SUBMISSION_REJECTED",
            "message_template": "{form_name} submission for {site_name} ({period_label}) was rejected. Reason: {reason}",
            "recipient_type": "dynamic",
            "dynamic_role": "spoc",
            "channels": "in_app,desktop,email,whatsapp",
            "created_by": 1,
            "updated_by": 1
        },
        {
            "name": "Submission Corrections Requested",
            "event_type": "SUBMISSION_CHANGES_REQUESTED",
            "message_template": "Corrections requested for {form_name} submission, {site_name} ({period_label}). Reason: {reason}",
            "recipient_type": "dynamic",
            "dynamic_role": "spoc",
            "channels": "in_app,desktop,email,whatsapp",
            "created_by": 1,
            "updated_by": 1
        },
        {
            "name": "Reporting Period Opened",
            "event_type": "PERIOD_OPEN",
            "message_template": "{period_label} reporting period is now open for {site_name}. You can start entering data.",
            "recipient_type": "role",
            "target_entity_type": "submission",
            "target_permission": "create",
            "channels": "in_app,desktop,email,whatsapp",
            "created_by": 1,
            "updated_by": 1
        }
    ]
    
    for item in defaults:
        config = NotificationConfig(**item)
        db.session.add(config)
    db.session.commit()


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
