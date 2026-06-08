from datetime import datetime, timezone
from app.database import db
from app.common.permissions import has_permission
from app.modules.SUBMIT.model import Submission, ProofDocument
from app.modules.WFLWBLD.model import WorkflowLevel, WorkflowLevelApprover
from app.modules.APPROV.model import ApprovalAction, Issue
from app.modules.USRMGMT.model import User
from app.modules.SUBMIT.service import format_period_label

REVIEWABLE_STATUSES = ("Submitted", "Resubmitted", "Under Review")
SUPPORTED_APPROVAL_MODES = ("ANY_ONE", "SEQUENTIAL")


def _utc_now():
    return datetime.now(timezone.utc)


# (Removed local notification helper, now importing from NOTIFY service)


def get_approver_queue(user_id):
    """
    Returns a sorted list of submissions pending review by user_id.
    Matches against site-specific permissions and workflow levels.
    """
    subs = Submission.query.filter(
        Submission.status.in_(REVIEWABLE_STATUSES),
        Submission.is_deleted == False
    ).all()

    queue = []
    for sub in subs:
        # Check site-specific permission
        if not has_permission(user_id, "submission", "approve", scope_site_id=sub.site_id) and \
           not has_permission(user_id, "submission", "reject", scope_site_id=sub.site_id):
            continue

        # Self-approval guard: approver cannot approve their own submission
        if sub.submitted_by == user_id:
            continue

        # Get active level for the submission's workflow
        lvl = WorkflowLevel.query.filter_by(
            workflow_version_id=sub.workflow_version_id,
            level_number=sub.current_level,
            is_deleted=False
        ).first()
        if not lvl:
            continue

        if lvl.approval_mode not in SUPPORTED_APPROVAL_MODES:
            continue

        # Check if the user is an approver at this level
        approver_entry = WorkflowLevelApprover.query.filter_by(
            workflow_level_id=lvl.id,
            user_id=user_id,
            is_deleted=False
        ).first()
        if not approver_entry:
            continue

        # Evaluate if it is this user's turn (handles SEQUENTIAL logic)
        is_my_turn = True
        if lvl.approval_mode == "SEQUENTIAL":
            # Get approvals already completed at this level
            approved_actions = ApprovalAction.query.filter_by(
                submission_id=sub.id,
                level_number=sub.current_level,
                action="Approve",
                is_deleted=False
            ).all()
            approved_user_ids = {a.actor_id for a in approved_actions}

            # Fetch all approvers ordered by sequence number
            all_approvers = WorkflowLevelApprover.query.filter_by(
                workflow_level_id=lvl.id,
                is_deleted=False
            ).order_by(WorkflowLevelApprover.sequence_number.asc()).all()

            next_approver = None
            for app in all_approvers:
                if app.user_id not in approved_user_ids:
                    next_approver = app
                    break

            if next_approver and next_approver.user_id != user_id:
                is_my_turn = False

        # Load form, site, and period for metadata
        from app.modules.FORMBLD.model import Form
        from app.modules.SITEMST.model import Site
        from app.modules.PERIOD.model import ReportingPeriod

        form = Form.query.get(sub.form_id)
        site = Site.query.get(sub.site_id)
        period = ReportingPeriod.query.get(sub.reporting_period_id)

        # Calculate days waiting
        start_time = sub.last_status_changed_at or sub.submitted_at or sub.created_at
        days_waiting = (_utc_now() - start_time).days if start_time else 0

        queue.append({
            "submission_id": sub.id,
            "form_name": form.name if form else "Unknown Form",
            "site_name": site.name if site else "Unknown Site",
            "period_label": format_period_label(period.year, period.month) if period else "Unknown Period",
            "current_level_name": lvl.level_name,
            "current_level_number": sub.current_level,
            "status": sub.status,
            "days_waiting": max(0, days_waiting),
            "is_my_turn": is_my_turn,
            "submitted_by_name": User.query.get(sub.submitted_by).full_name if sub.submitted_by else "System",
            "submitted_at": sub.submitted_at
        })

    # Sort by days waiting descending
    queue.sort(key=lambda x: x["days_waiting"], reverse=True)
    return queue

def get_actioned_history(user_id):
    """
    Returns list of submissions the user recently actioned.
    """
    actions = (
        ApprovalAction.query.filter_by(actor_id=user_id, is_deleted=False)
        .order_by(ApprovalAction.acted_at.desc())
        .limit(50)
        .all()
    )

    from app.modules.FORMBLD.model import Form
    from app.modules.SITEMST.model import Site
    from app.modules.PERIOD.model import ReportingPeriod

    history = []
    seen_submissions = set()
    for act in actions:
        if act.submission_id in seen_submissions:
            continue
        seen_submissions.add(act.submission_id)

        sub = Submission.query.get(act.submission_id)
        if not sub or sub.is_deleted:
            continue

        form = Form.query.get(sub.form_id)
        site = Site.query.get(sub.site_id)
        period = ReportingPeriod.query.get(sub.reporting_period_id)

        history.append({
            "submission_id": sub.id,
            "form_name": form.name if form else "Unknown Form",
            "site_name": site.name if site else "Unknown Site",
            "period_label": format_period_label(period.year, period.month) if period else "Unknown Period",
            "action": act.action,
            "comment": act.comment,
            "acted_at": act.acted_at,
            "current_status": sub.status
        })
    return history

def approve_submission(submission_id, user_id, comment=None):
    """
    Approves the submission at the current level.
    If the level is fully satisfied, advances to the next level or locks as Approved.
    """
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        raise ValueError("Submission not found.")

    if submission.status not in REVIEWABLE_STATUSES:
        raise ValueError(f"Cannot approve submission in status: {submission.status}")

    # Permission check
    if not has_permission(user_id, "submission", "approve", scope_site_id=submission.site_id):
        raise ValueError("Permission denied: You do not have permission to approve submissions for this site.")

    # Self-approval prevention
    if submission.submitted_by == user_id:
        raise ValueError("Self-approval is blocked. You cannot approve a sheet you submitted.")

    # Load workflow level and approvers
    lvl = WorkflowLevel.query.filter_by(
        workflow_version_id=submission.workflow_version_id,
        level_number=submission.current_level,
        is_deleted=False
    ).first()
    if not lvl:
        raise ValueError("Workflow level config not found.")

    if lvl.approval_mode not in SUPPORTED_APPROVAL_MODES:
        raise ValueError(f"Approval mode {lvl.approval_mode} is not supported in MVP.")

    approver_entry = WorkflowLevelApprover.query.filter_by(
        workflow_level_id=lvl.id,
        user_id=user_id,
        is_deleted=False
    ).first()
    if not approver_entry:
        raise ValueError("You are not an assigned approver for the current workflow level.")

    # If SEQUENTIAL, verify it is this user's turn
    if lvl.approval_mode == "SEQUENTIAL":
        approved_actions = ApprovalAction.query.filter_by(
            submission_id=submission_id,
            level_number=submission.current_level,
            action="Approve",
            is_deleted=False
        ).all()
        approved_user_ids = {a.actor_id for a in approved_actions}

        all_approvers = WorkflowLevelApprover.query.filter_by(
            workflow_level_id=lvl.id,
            is_deleted=False
        ).order_by(WorkflowLevelApprover.sequence_number.asc()).all()

        next_approver = None
        for app in all_approvers:
            if app.user_id not in approved_user_ids:
                next_approver = app
                break

        if next_approver and next_approver.user_id != user_id:
            raise ValueError("It is not your turn to approve in the sequence.")

    # Record approval action
    action = ApprovalAction(
        submission_id=submission_id,
        actor_id=user_id,
        level_number=submission.current_level,
        action="Approve",
        comment=comment,
        created_by=user_id,
        updated_by=user_id
    )
    db.session.add(action)
    db.session.flush()

    if submission.status in ("Submitted", "Resubmitted"):
        submission.status = "Under Review"
        submission.last_status_changed_at = _utc_now()
        submission.updated_by = user_id

    # Audit log approve action
    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission",
        entity_id=submission_id,
        action="APPROVE_LEVEL",
        old_values={"current_level": submission.current_level},
        new_values={"current_level": submission.current_level},
        metadata={"comment": comment}
    )

    # Evaluate level completion
    is_level_completed = False
    if lvl.approval_mode == "ANY_ONE":
        is_level_completed = True
    elif lvl.approval_mode == "SEQUENTIAL":
        # Check if any sequential approvers remain
        approved_actions = ApprovalAction.query.filter_by(
            submission_id=submission_id,
            level_number=submission.current_level,
            action="Approve",
            is_deleted=False
        ).all()
        approved_user_ids = {a.actor_id for a in approved_actions}

        all_approvers = WorkflowLevelApprover.query.filter_by(
            workflow_level_id=lvl.id,
            is_deleted=False
        ).all()

        remaining = [app for app in all_approvers if app.user_id not in approved_user_ids]
        if len(remaining) == 0:
            is_level_completed = True

    if is_level_completed:
        # Check for next level
        next_lvl = WorkflowLevel.query.filter_by(
            workflow_version_id=submission.workflow_version_id,
            level_number=submission.current_level + 1,
            is_deleted=False
        ).first()

        if next_lvl:
            # Advance level
            submission.current_level += 1
            submission.last_status_changed_at = _utc_now()
            submission.updated_by = user_id

            # Notify next level approvers
            from app.modules.NOTIFY.service import notify_level_approvers
            notify_level_approvers(submission_id)
        else:
            # Final Approval
            # Verify no open issues
            open_issues_count = Issue.query.filter_by(
                submission_id=submission_id,
                status="Open",
                blocks_approval=True,
                is_deleted=False
            ).count()
            if open_issues_count > 0:
                raise ValueError("Cannot final approve: There are open issues blocking approval.")

            old_status = submission.status
            submission.status = "Approved"
            submission.approved_by = user_id
            submission.approved_at = _utc_now()
            submission.is_locked = True
            submission.last_status_changed_at = _utc_now()
            submission.updated_by = user_id

            # Log final approval in audit trail
            log_audit(
                actor_user_id=user_id,
                entity_type="submission",
                entity_id=submission_id,
                action="FINAL_APPROVE",
                old_values={"status": old_status},
                new_values={"status": "Approved"}
            )

            # Notify SPOC
            from app.modules.SITEMST.model import Site
            from app.modules.FORMBLD.model import Form
            from app.modules.NOTIFY.service import notify_spoc
            site = Site.query.get(submission.site_id)
            form = Form.query.get(submission.form_id)
            notify_spoc(
                submission_id=submission_id,
                event_type="APPROVED",
                message=f"Your submission for {form.name} ({site.name}) has been approved."
            )

    return submission

def request_changes_submission(submission_id, user_id, comment):
    """
    Sends the submission back to the SPOC for edits.
    """
    if not comment or not comment.strip():
        raise ValueError("A comment is required to request changes.")

    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        raise ValueError("Submission not found.")

    if submission.status not in REVIEWABLE_STATUSES:
        raise ValueError(f"Cannot request changes on submission in status: {submission.status}")

    if not has_permission(user_id, "submission", "approve", scope_site_id=submission.site_id) and \
       not has_permission(user_id, "submission", "reject", scope_site_id=submission.site_id):
        raise ValueError("Permission denied: You do not have permission to review submissions.")

    # Self-approval guard applies to returns too
    if submission.submitted_by == user_id:
        raise ValueError("Self-review action is blocked.")

    # Record request changes action
    action = ApprovalAction(
        submission_id=submission_id,
        actor_id=user_id,
        level_number=submission.current_level,
        action="Request Changes",
        comment=comment.strip(),
        created_by=user_id,
        updated_by=user_id
    )
    db.session.add(action)

    # Soft delete approvals at the current level so they reset when SPOC resubmits
    current_approvals = ApprovalAction.query.filter_by(
        submission_id=submission_id,
        level_number=submission.current_level,
        action="Approve",
        is_deleted=False
    ).all()
    for app_act in current_approvals:
        app_act.is_deleted = True
        app_act.deleted_by = user_id
        app_act.deleted_at = _utc_now()

    old_status = submission.status
    submission.status = "Changes Requested"
    submission.last_status_changed_at = _utc_now()
    submission.updated_by = user_id

    # Audit log
    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission",
        entity_id=submission_id,
        action="REQUEST_CHANGES",
        old_values={"status": old_status},
        new_values={"status": "Changes Requested"},
        metadata={"comment": comment}
    )

    # Notify SPOC
    from app.modules.FORMBLD.model import Form
    from app.modules.NOTIFY.service import notify_spoc
    form = Form.query.get(submission.form_id)
    notify_spoc(
        submission_id=submission_id,
        event_type="CHANGES_REQUESTED",
        message=f"Changes requested on your submission for {form.name if form else 'sheet'}. Reason: {comment}"
    )

    return submission

def reject_submission(submission_id, user_id, comment):
    """
    Terminally rejects the submission. Locks the record.
    """
    if not comment or not comment.strip():
        raise ValueError("A comment is required to reject a submission.")

    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        raise ValueError("Submission not found.")

    if submission.status not in REVIEWABLE_STATUSES:
        raise ValueError(f"Cannot reject submission in status: {submission.status}")

    if not has_permission(user_id, "submission", "reject", scope_site_id=submission.site_id):
        raise ValueError("Permission denied: You do not have permission to reject submissions.")

    # Self-approval guard applies
    if submission.submitted_by == user_id:
        raise ValueError("Self-review action is blocked.")

    # Record rejection action
    action = ApprovalAction(
        submission_id=submission_id,
        actor_id=user_id,
        level_number=submission.current_level,
        action="Reject",
        comment=comment.strip(),
        created_by=user_id,
        updated_by=user_id
    )
    db.session.add(action)

    old_status = submission.status
    submission.status = "Rejected"
    submission.is_locked = True
    submission.last_status_changed_at = _utc_now()
    submission.updated_by = user_id

    # Audit log
    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission",
        entity_id=submission_id,
        action="REJECT",
        old_values={"status": old_status},
        new_values={"status": "Rejected"},
        metadata={"comment": comment}
    )

    # Notify SPOC
    from app.modules.FORMBLD.model import Form
    from app.modules.NOTIFY.service import notify_spoc
    form = Form.query.get(submission.form_id)
    notify_spoc(
        submission_id=submission_id,
        event_type="REJECTED",
        message=f"Your submission for {form.name if form else 'sheet'} has been rejected. Reason: {comment}"
    )

    return submission

def raise_issue(submission_id, field_id, title, description, user_id):
    """
    Raises a review issue blocking final approval.
    """
    if not title or not title.strip():
        raise ValueError("Issue title is required.")
    if not description or not description.strip():
        raise ValueError("Issue description is required.")

    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        raise ValueError("Submission not found.")

    # Permission check
    if not has_permission(user_id, "submission", "approve", scope_site_id=submission.site_id):
        raise ValueError("Permission denied: You do not have permission to raise review issues.")

    issue = Issue(
        submission_id=submission_id,
        field_id=field_id,
        raised_by=user_id,
        title=title.strip(),
        description=description.strip(),
        status="Open",
        blocks_approval=True,
        created_by=user_id,
        updated_by=user_id
    )
    db.session.add(issue)
    db.session.flush()

    # Audit log
    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="issue",
        entity_id=issue.id,
        action="RAISE_ISSUE",
        old_values=None,
        new_values={"status": "Open", "submission_id": submission_id, "title": title},
        metadata={"description": description}
    )

    # Notify SPOC
    from app.modules.NOTIFY.service import notify_spoc
    notify_spoc(
        submission_id=submission_id,
        event_type="ISSUE_RAISED",
        message=f"An issue has been raised on your submission: '{title}'"
    )

    return issue

def resolve_issue(issue_id, user_id):
    """
    Resolves an open issue.
    """
    issue = Issue.query.get(issue_id)
    if not issue or issue.is_deleted:
        raise ValueError("Issue not found.")

    if issue.status == "Resolved":
        raise ValueError("Issue is already resolved.")

    submission = Submission.query.get(issue.submission_id)
    # Permission check
    if not has_permission(user_id, "submission", "approve", scope_site_id=submission.site_id):
        raise ValueError("Permission denied: You do not have permission to resolve review issues.")

    issue.status = "Resolved"
    issue.resolved_by = user_id
    issue.resolved_at = _utc_now()
    issue.updated_by = user_id

    # Audit log
    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="issue",
        entity_id=issue.id,
        action="RESOLVE_ISSUE",
        old_values={"status": "Open"},
        new_values={"status": "Resolved"}
    )

    # Notify SPOC
    from app.modules.NOTIFY.service import notify_spoc
    notify_spoc(
        submission_id=issue.submission_id,
        event_type="ISSUE_RESOLVED",
        message=f"The review issue '{issue.title}' on your submission has been resolved."
    )

    return issue
