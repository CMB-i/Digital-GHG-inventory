from datetime import datetime, timezone
from app.database import db
from app.common.permissions import has_permission
from app.common.submission_status import (
    STATUS_SUBMITTED,
    STATUS_RESUBMITTED,
    STATUS_UNDER_REVIEW,
    STATUS_CHANGES_REQUESTED,
    STATUS_APPROVED,
    STATUS_REJECTED,
    REVIEWABLE_STATUSES,
    SUBMISSION_STATUS_LABELS,
)
from app.modules.SUBMIT.model import (
    Submission,
    ProofDocument,
    SubmissionPackage,
    SubmissionValue,
    SubmissionValueIssue,
)
from app.modules.WFLWBLD.model import WorkflowLevel
from app.modules.WFLWBLD.service import (
    find_next_applicable_level,
    get_eligible_level_approvers,
    is_user_eligible_level_approver,
)
from app.modules.APPROV.model import ApprovalAction, Issue
from app.modules.USRMGMT.model import User
from app.modules.SUBMIT.service import (
    compose_readonly_workbook_context,
    format_period_label,
    human_sheet_label,
    sync_submission_values_for_status,
    serialize_submission_value_issue,
    fy_start_year_for,
)

SUPPORTED_APPROVAL_MODES = ("ANY_ONE", "SEQUENTIAL")


def _utc_now():
    return datetime.now(timezone.utc)


# (Removed local notification helper, now importing from NOTIFY service)


def _queue_submission_if_eligible(sub, user_id):
    # Check site-specific permission
    if not has_permission(user_id, "submission", "approve", scope_site_id=sub.site_id) and \
       not has_permission(user_id, "submission", "reject", scope_site_id=sub.site_id):
        return None

    # Self-approval guard: approver cannot approve their own submission
    if sub.submitted_by == user_id:
        return None

    # Get active level for the submission's workflow
    lvl = WorkflowLevel.query.filter_by(
        workflow_version_id=sub.workflow_version_id,
        level_number=sub.current_level,
        is_deleted=False
    ).first()
    if not lvl:
        return None

    if lvl.approval_mode not in SUPPORTED_APPROVAL_MODES:
        return None

    if not is_user_eligible_level_approver(lvl, user_id, sub.site_id):
        return None

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
        all_approvers = get_eligible_level_approvers(lvl, sub.site_id)

        next_approver = None
        for app in all_approvers:
            if app.user_id not in approved_user_ids:
                next_approver = app
                break

        if next_approver and next_approver.user_id != user_id:
            is_my_turn = False

    return {
        "level": lvl,
        "is_my_turn": is_my_turn,
    }


def _submission_queue_item(sub, eligibility):
    # Load form, site, and period for metadata
    from app.modules.FORMBLD.model import Form
    from app.modules.SITEMST.model import Site
    from app.modules.PERIOD.model import ReportingPeriod

    form = Form.query.get(sub.form_id)
    site = Site.query.get(sub.site_id)
    period = ReportingPeriod.query.get(sub.reporting_period_id)
    lvl = eligibility["level"]
    submitter = User.query.get(sub.submitted_by) if sub.submitted_by else None

    # Calculate days waiting
    start_time = sub.last_status_changed_at or sub.submitted_at or sub.created_at
    days_waiting = (_utc_now() - start_time).days if start_time else 0

    return {
        "item_type": "submission",
        "submission_id": sub.id,
        "form_name": human_sheet_label(form),
        "site_id": sub.site_id,
        "site_name": site.name if site else "Unknown Site",
        "period_id": sub.reporting_period_id,
        "period_label": format_period_label(period.year, period.month) if period else "Unknown Period",
        "month": period.month if period else None,
        "year": period.year if period else None,
        "current_level_name": lvl.level_name,
        "current_level_number": sub.current_level,
        "status": sub.status,
        "days_waiting": max(0, days_waiting),
        "is_my_turn": eligibility["is_my_turn"],
        "submitted_by": sub.submitted_by,
        "submitted_by_name": submitter.full_name if submitter else "System",
        "submitted_at": sub.submitted_at
    }


def _package_queue_item(package_id, grouped_items):
    from app.modules.FORMBLD.model import Form
    from app.modules.SITEMST.model import Site
    from app.modules.PERIOD.model import ReportingPeriod

    package = SubmissionPackage.query.get(package_id)
    representative = grouped_items[0]["submission"]
    eligibility = grouped_items[0]["eligibility"]
    site = Site.query.get(package.site_id if package else representative.site_id)
    period = ReportingPeriod.query.get(package.period_id if package else representative.reporting_period_id)

    form_ids = [item["submission"].form_id for item in grouped_items]
    forms = Form.query.filter(Form.id.in_(form_ids)).all() if form_ids else []
    forms_by_id = {form.id: form for form in forms}
    form_names = [human_sheet_label(form) for form in forms]

    start_times = [
        item["submission"].last_status_changed_at
        or item["submission"].submitted_at
        or item["submission"].created_at
        for item in grouped_items
    ]
    start_times = [item for item in start_times if item]
    oldest_start = min(start_times) if start_times else None
    days_waiting = (_utc_now() - oldest_start).days if oldest_start else 0
    submitted_users = {
        item["submission"].submitted_by
        for item in grouped_items
        if item["submission"].submitted_by
    }
    submitted_by_name = "Multiple submitters"
    if len(submitted_users) == 1:
        submitter = User.query.get(next(iter(submitted_users)))
        submitted_by_name = submitter.full_name if submitter else "System"
    elif not submitted_users:
        submitted_by_name = "System"

    current_levels = [
        item["submission"].current_level
        for item in grouped_items
        if item["submission"].current_level is not None
    ]
    statuses = {item["submission"].status for item in grouped_items}
    status = package.status if package else (", ".join(sorted(statuses)) if statuses else STATUS_SUBMITTED)

    return {
        "item_type": "package",
        "package_id": package_id,
        "package_type": package.package_type if package else "monthly_workbook",
        "label": (
            f"{format_period_label(period.year, period.month)} Monthly Workbook Package"
            if period else "Monthly Workbook Package"
        ),
        "site_id": site.id if site else representative.site_id,
        "site_name": site.name if site else "Unknown Site",
        "period_id": period.id if period else representative.reporting_period_id,
        "period_label": format_period_label(period.year, period.month) if period else "Unknown Period",
        "month": period.month if period else None,
        "year": period.year if period else None,
        "status": status,
        "submitted_by": list(submitted_users),
        "submitted_by_name": submitted_by_name,
        "submitted_at": package.submitted_at if package else representative.submitted_at,
        "included_submission_count": len(grouped_items),
        "included_submissions": [
            {
                "submission_id": item["submission"].id,
                "form_id": item["submission"].form_id,
                "form_name": human_sheet_label(forms_by_id[item["submission"].form_id]) if item["submission"].form_id in forms_by_id else "Untitled Sheet",
                "status": item["submission"].status,
            }
            for item in grouped_items
        ],
        "forms_included": form_names,
        "current_level_number": min(current_levels) if current_levels else representative.current_level,
        "current_level_name": eligibility["level"].level_name,
        "days_waiting": max(0, days_waiting),
        "is_my_turn": any(item["eligibility"]["is_my_turn"] for item in grouped_items),
    }


def get_package_summary_for_reviewer(package_id, user_id):
    package = SubmissionPackage.query.get(package_id)
    if not package or package.is_deleted:
        return None

    submissions = Submission.query.filter_by(package_id=package.id, is_deleted=False).all()
    eligible = []
    for submission in submissions:
        eligibility = _queue_submission_if_eligible(submission, user_id)
        if eligibility:
            eligible.append({
                "submission": submission,
                "eligibility": eligibility,
            })

    if not eligible:
        return None

    return _package_queue_item(package.id, eligible)


def compose_package_review_data(package_id, user_id):
    queue_summary = get_package_summary_for_reviewer(package_id, user_id)

    package = SubmissionPackage.query.get(package_id)
    if not package or package.is_deleted:
        return None

    from app.modules.FORMBLD.model import Form
    from app.modules.SITEMST.model import Site
    from app.modules.PERIOD.model import ReportingPeriod

    site = Site.query.get(package.site_id)
    period = ReportingPeriod.query.get(package.period_id)
    submitter = User.query.get(package.submitted_by) if package.submitted_by else None
    fy_start_year = fy_start_year_for(period.year, period.month) if period else None

    submissions = Submission.query.filter_by(package_id=package.id, is_deleted=False).all()
    can_view_package = any(
        has_permission(user_id, "submission", "view", scope_site_id=submission.site_id)
        for submission in submissions
    )
    if not queue_summary and not can_view_package:
        return None

    form_ids = [submission.form_id for submission in submissions]
    forms_by_id = {
        form.id: form
        for form in Form.query.filter(Form.id.in_(form_ids or [0])).all()
    }

    sheets = []
    for submission in submissions:
        form = forms_by_id.get(submission.form_id)
        sub_submitter = User.query.get(submission.submitted_by) if submission.submitted_by else None
        workbook_context = compose_readonly_workbook_context(
            submission.site_id,
            submission.form_id,
            fy_start_year,
            active_period_id=package.period_id,
            form_version_id=submission.form_version_id,
        )
        active_row = next(
            (
                row for row in workbook_context["rows"]
                if row.get("submission_id") == submission.id
            ),
            None,
        )
        sheets.append({
            "submission_id": submission.id,
            "form_id": submission.form_id,
            "form_name": human_sheet_label(form),
            "status": submission.status,
            "current_level": submission.current_level,
            "submitted_by": sub_submitter.full_name if sub_submitter else "System",
            "submitted_at": submission.submitted_at,
            "fields": workbook_context["fields"],
            "sections": workbook_context.get("sections", []),
            "workbook_values": workbook_context.get("workbook_values", {}),
            "rows": workbook_context["rows"],
            "active_row_key": workbook_context.get("active_row_key") or (
                active_row.get("row_key") if active_row else None
            ),
            "values": active_row.get("values", {}) if active_row else {},
            "proofs": active_row.get("proofs", {}) if active_row else {},
            "_sort_name": human_sheet_label(form),
        })

    sheets.sort(key=lambda sheet: sheet["_sort_name"].lower())
    for sheet in sheets:
        sheet.pop("_sort_name", None)

    can_reject = has_permission(user_id, "submission", "reject", scope_site_id=package.site_id)
    can_review = has_permission(user_id, "submission", "approve", scope_site_id=package.site_id) or can_reject
    is_my_turn = bool(queue_summary and queue_summary.get("is_my_turn"))

    return {
        "package": {
            "package_id": package.id,
            "package_type": package.package_type,
            "status": package.status,
            "site_id": package.site_id,
            "site_name": site.name if site else "Unknown Site",
            "period_id": package.period_id,
            "period_label": format_period_label(period.year, period.month) if period else "Unknown Period",
            "month": period.month if period else None,
            "year": period.year if period else None,
            "financial_year_start": fy_start_year,
            "current_level": package.current_level,
            "current_level_name": queue_summary.get("current_level_name") if queue_summary else None,
            "submitted_by": submitter.full_name if submitter else "System",
            "submitted_at": package.submitted_at,
            "included_submission_count": len(sheets),
            "is_my_turn": is_my_turn,
            "actions": {
                "can_approve": is_my_turn and can_review,
                "can_request_changes": can_review,
                "can_reject": can_reject,
                "can_add_issues": bool(queue_summary and can_review),
            },
        },
        "sheets": sheets,
    }


def _package_submission_value(package_id, value_id):
    package = SubmissionPackage.query.get(package_id)
    if not package or package.is_deleted:
        raise ValueError("Package not found.")

    value = SubmissionValue.query.get(value_id)
    if not value:
        raise ValueError("Cell value not found.")

    submission = Submission.query.get(value.submission_id)
    if not submission or submission.is_deleted or submission.package_id != package.id:
        raise ValueError("Cell value does not belong to this package.")

    return package, submission, value


def list_package_value_issues(package_id, value_id, user_id):
    package, _submission, _value = _package_submission_value(package_id, value_id)
    review_data = compose_package_review_data(package.id, user_id)
    if not review_data:
        raise ValueError("Permission denied.")

    issues = (
        SubmissionValueIssue.query.filter_by(
            submission_value_id=value_id,
            is_deleted=False,
        )
        .order_by(SubmissionValueIssue.created_at.asc(), SubmissionValueIssue.id.asc())
        .all()
    )
    return [serialize_submission_value_issue(issue) for issue in issues]


def add_package_value_issue(package_id, value_id, user_id, issue_text):
    if not issue_text or not issue_text.strip():
        raise ValueError("Issue comment is required.")
    if len(issue_text.strip()) > 2000:
        raise ValueError("Issue comment must be 2000 characters or fewer.")

    package, _submission, value = _package_submission_value(package_id, value_id)
    if not get_package_summary_for_reviewer(package.id, user_id):
        raise ValueError("Permission denied.")

    issue = SubmissionValueIssue(
        submission_value_id=value.id,
        raised_by=user_id,
        issue_text=issue_text.strip(),
        status="Open",
        blocks_approval=True,
        created_by=user_id,
        updated_by=user_id,
    )
    db.session.add(issue)
    db.session.flush()

    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission_value_issue",
        entity_id=issue.id,
        action="RAISE_CELL_ISSUE",
        old_values=None,
        new_values={
            "package_id": package.id,
            "submission_value_id": value.id,
            "status": issue.status,
        },
    )
    return issue


def resolve_package_value_issue(package_id, value_id, issue_id, user_id):
    package, _submission, value = _package_submission_value(package_id, value_id)

    issue = SubmissionValueIssue.query.filter_by(
        id=issue_id, submission_value_id=value.id, is_deleted=False
    ).first()
    if not issue:
        raise ValueError("Cell issue not found.")
    if issue.status == "Resolved":
        raise ValueError("Cell issue is already resolved.")

    if not get_package_summary_for_reviewer(package.id, user_id):
        raise ValueError("Permission denied.")

    issue.status = "Resolved"
    issue.resolved_by = user_id
    issue.resolved_at = _utc_now()
    issue.updated_by = user_id

    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission_value_issue",
        entity_id=issue.id,
        action="RESOLVE_CELL_ISSUE",
        old_values={"status": "Open"},
        new_values={"status": "Resolved"},
    )
    return issue


def _get_package_for_action(package_id, user_id):
    queue_summary = get_package_summary_for_reviewer(package_id, user_id)
    if not queue_summary:
        raise ValueError("Permission denied.")

    package = SubmissionPackage.query.get(package_id)
    if not package or package.is_deleted:
        raise ValueError("Package not found.")

    return package, queue_summary


def _all_package_submissions(package_id):
    # Ordered so that two concurrent batch calls touching overlapping
    # submissions always acquire their per-submission row locks in the same
    # relative order -- an arbitrary/unordered iteration order here would be a
    # real lock-order-inversion deadlock risk once each iteration locks a row.
    return (
        Submission.query.filter_by(package_id=package_id, is_deleted=False)
        .order_by(Submission.id)
        .all()
    )


def _attempt_in_savepoint(fn):
    """
    Runs fn() inside a SAVEPOINT so a failure only undoes fn's own partial
    changes, not whatever earlier submissions in the same batch already
    staged in the outer transaction (those still commit together at the view
    layer's single db.session.commit()). Returns (ok, error_message).
    """
    nested = db.session.begin_nested()
    try:
        fn()
        nested.commit()
        return True, None
    except Exception as exc:
        nested.rollback()
        return False, str(exc)


def _sync_package_status_from_submissions(package, user_id):
    submissions = Submission.query.filter_by(package_id=package.id, is_deleted=False).all()
    if not submissions:
        return package

    statuses = {submission.status for submission in submissions}
    if statuses == {STATUS_APPROVED}:
        package.status = STATUS_APPROVED
        package.final_approved_at = _utc_now()
        package.final_approved_by = user_id
    elif STATUS_REJECTED in statuses:
        package.status = STATUS_REJECTED
    elif STATUS_CHANGES_REQUESTED in statuses:
        package.status = STATUS_CHANGES_REQUESTED
    elif statuses & set(REVIEWABLE_STATUSES):
        package.status = STATUS_UNDER_REVIEW if STATUS_UNDER_REVIEW in statuses else STATUS_SUBMITTED
        levels = [
            submission.current_level
            for submission in submissions
            if submission.current_level is not None
        ]
        if levels:
            package.current_level = min(levels)
    package.updated_by = user_id
    return package


def approve_package(package_id, user_id, comment=None):
    """
    Approves every member submission this caller is currently eligible to
    approve. Purely additive: a submission that isn't reviewable right now, or
    that this caller isn't eligible for, is recorded as skipped/failed with a
    reason rather than aborting the whole batch -- members that do succeed are
    not rolled back just because a sibling submission couldn't be actioned.
    """
    package, queue_summary = _get_package_for_action(package_id, user_id)
    if not queue_summary.get("is_my_turn"):
        raise ValueError("It is not your turn to approve this package.")

    submissions = _all_package_submissions(package.id)
    if not submissions:
        raise ValueError("No submissions found in this package.")

    results = []
    for submission in submissions:
        if submission.status not in REVIEWABLE_STATUSES or submission.is_locked:
            results.append({
                "submission_id": submission.id,
                "ok": False,
                "skipped": True,
                "status": submission.status,
                "error": f"Not reviewable (status: {submission.status}).",
            })
            continue

        ok, error = _attempt_in_savepoint(lambda s=submission: approve_submission(s.id, user_id, comment))
        results.append({
            "submission_id": submission.id,
            "ok": ok,
            "skipped": False,
            "status": submission.status,
            "error": error,
        })

    _sync_package_status_from_submissions(package, user_id)

    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission_package",
        entity_id=package.id,
        action="APPROVE_PACKAGE",
        old_values=None,
        new_values={
            "status": package.status,
            "results": results,
        },
        metadata={"comment": comment},
    )

    return package, results


def request_changes_package(package_id, user_id, comment):
    """
    Requests changes on every member submission this caller is currently
    eligible to act on. See approve_package for the partial-eligibility
    handling this shares.
    """
    if not comment or not comment.strip():
        raise ValueError("A comment is required to request changes.")

    package, _queue_summary = _get_package_for_action(package_id, user_id)
    submissions = _all_package_submissions(package.id)
    if not submissions:
        raise ValueError("No submissions found in this package.")

    results = []
    for submission in submissions:
        if submission.status not in REVIEWABLE_STATUSES or submission.is_locked:
            results.append({
                "submission_id": submission.id,
                "ok": False,
                "skipped": True,
                "status": submission.status,
                "error": f"Not reviewable (status: {submission.status}).",
            })
            continue

        ok, error = _attempt_in_savepoint(lambda s=submission: request_changes_submission(s.id, user_id, comment))
        results.append({
            "submission_id": submission.id,
            "ok": ok,
            "skipped": False,
            "status": submission.status,
            "error": error,
        })

    _sync_package_status_from_submissions(package, user_id)

    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission_package",
        entity_id=package.id,
        action="REQUEST_CHANGES_PACKAGE",
        old_values=None,
        new_values={
            "status": package.status,
            "results": results,
        },
        metadata={"comment": comment.strip()},
    )

    return package, results


def reject_package(package_id, user_id, comment):
    """
    Rejects every member submission this caller is currently eligible to act
    on. See approve_package for the partial-eligibility handling this shares.
    """
    if not comment or not comment.strip():
        raise ValueError("A comment is required to reject a package.")

    package, _queue_summary = _get_package_for_action(package_id, user_id)
    if not has_permission(user_id, "submission", "reject", scope_site_id=package.site_id):
        raise ValueError("Permission denied: You do not have permission to reject submissions.")

    submissions = _all_package_submissions(package.id)
    if not submissions:
        raise ValueError("No submissions found in this package.")

    results = []
    for submission in submissions:
        if submission.status not in REVIEWABLE_STATUSES or submission.is_locked:
            results.append({
                "submission_id": submission.id,
                "ok": False,
                "skipped": True,
                "status": submission.status,
                "error": f"Not reviewable (status: {submission.status}).",
            })
            continue

        ok, error = _attempt_in_savepoint(lambda s=submission: reject_submission(s.id, user_id, comment))
        results.append({
            "submission_id": submission.id,
            "ok": ok,
            "skipped": False,
            "status": submission.status,
            "error": error,
        })

    _sync_package_status_from_submissions(package, user_id)

    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission_package",
        entity_id=package.id,
        action="REJECT_PACKAGE",
        old_values=None,
        new_values={
            "status": package.status,
            "results": results,
        },
        metadata={"comment": comment.strip()},
    )

    return package, results


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
    package_groups = {}
    for sub in subs:
        eligibility = _queue_submission_if_eligible(sub, user_id)
        if not eligibility:
            continue

        if sub.package_id:
            package_groups.setdefault(sub.package_id, []).append({
                "submission": sub,
                "eligibility": eligibility,
            })
            continue

        queue.append(_submission_queue_item(sub, eligibility))

    for package_id, grouped_items in package_groups.items():
        queue.append(_package_queue_item(package_id, grouped_items))

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

    def action_label(action):
        return {
            "Approve": "Approved",
            "Request Changes": "Returned for correction",
            "Reject": "Sent back",
        }.get(action, action or "Reviewed")

    def status_label(status):
        return SUBMISSION_STATUS_LABELS.get(status, status or "Unknown")

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
            "package_id": sub.package_id,
            "form_name": human_sheet_label(form),
            "site_name": site.name if site else "Unknown Site",
            "period_label": format_period_label(period.year, period.month) if period else "Unknown Period",
            "action": act.action,
            "action_text": action_label(act.action),
            "comment": act.comment,
            "acted_at": act.acted_at,
            "current_status": sub.status,
            "current_status_text": status_label(sub.status),
        })
    return history

def approve_submission(submission_id, user_id, comment=None):
    """
    Approves the submission at the current level.
    If the level is fully satisfied, advances to the next level or locks as Approved.
    """
    # Locks the row for the rest of this transaction so two concurrent approvals
    # of the same submission (e.g. two eligible ANY_ONE-mode approvers, or a
    # double-click) can't both observe is_level_completed=True and both try to
    # advance/finalize -- Query.get() is deliberately not used, see submit_submission.
    submission = (
        Submission.query.filter_by(id=submission_id)
        .with_for_update()
        .one_or_none()
    )
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

    if not is_user_eligible_level_approver(lvl, user_id, submission.site_id):
        raise ValueError("You are not an assigned reviewer for the current workflow level.")

    # If SEQUENTIAL, verify it is this user's turn
    if lvl.approval_mode == "SEQUENTIAL":
        approved_actions = ApprovalAction.query.filter_by(
            submission_id=submission_id,
            level_number=submission.current_level,
            action="Approve",
            is_deleted=False
        ).all()
        approved_user_ids = {a.actor_id for a in approved_actions}

        all_approvers = get_eligible_level_approvers(lvl, submission.site_id)

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

    if submission.status in (STATUS_SUBMITTED, STATUS_RESUBMITTED):
        submission.status = STATUS_UNDER_REVIEW
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

        all_approvers = get_eligible_level_approvers(lvl, submission.site_id)

        remaining = [app for app in all_approvers if app.user_id not in approved_user_ids]
        if len(remaining) == 0:
            is_level_completed = True

    if is_level_completed:
        next_lvl = find_next_applicable_level(
            submission.workflow_version_id,
            submission.site_id,
            submission.current_level,
        )

        if next_lvl:
            # Notify SPOC
            from app.modules.SITEMST.model import Site
            from app.modules.FORMBLD.model import Form
            from app.modules.NOTIFY.service import notify_spoc
            site = Site.query.get(submission.site_id)
            form = Form.query.get(submission.form_id)
            notify_spoc(
                submission_id=submission_id,
                event_type="LEVEL_APPROVED",
                message=f"Your submission for {human_sheet_label(form)} ({site.name}) has been approved at Level {submission.current_level}."
            )

            # Advance level
            submission.current_level = next_lvl.level_number
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

            open_cell_issues_count = (
                SubmissionValueIssue.query.join(
                    SubmissionValue, SubmissionValue.id == SubmissionValueIssue.submission_value_id
                )
                .filter(
                    SubmissionValue.submission_id == submission_id,
                    SubmissionValueIssue.status == "Open",
                    SubmissionValueIssue.blocks_approval == True,
                    SubmissionValueIssue.is_deleted == False,
                )
                .count()
            )
            if open_cell_issues_count > 0:
                raise ValueError("Cannot final approve: There are open cell-level issues blocking approval.")

            if submission.needs_recalc_review:
                raise ValueError(
                    "This submission has a calculated field that needs recalculation review before it can be given final approval."
                )

            old_status = submission.status
            submission.status = STATUS_APPROVED
            submission.approved_by = user_id
            submission.approved_at = _utc_now()
            submission.is_locked = True
            submission.last_status_changed_at = _utc_now()
            submission.updated_by = user_id
            sync_submission_values_for_status(submission, user_id)

            # Log final approval in audit trail
            log_audit(
                actor_user_id=user_id,
                entity_type="submission",
                entity_id=submission_id,
                action="FINAL_APPROVE",
                old_values={"status": old_status},
                new_values={"status": STATUS_APPROVED}
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
                message=f"Your submission for {human_sheet_label(form)} ({site.name}) has been approved."
            )

    return submission

def request_changes_submission(submission_id, user_id, comment):
    """
    Sends the submission back to the SPOC for edits.
    """
    if not comment or not comment.strip():
        raise ValueError("A comment is required to request changes.")

    # See approve_submission for why this locks the row instead of using Query.get().
    submission = (
        Submission.query.filter_by(id=submission_id)
        .with_for_update()
        .one_or_none()
    )
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
    submission.status = STATUS_CHANGES_REQUESTED
    submission.last_status_changed_at = _utc_now()
    submission.updated_by = user_id
    sync_submission_values_for_status(submission, user_id)

    # Audit log
    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission",
        entity_id=submission_id,
        action="REQUEST_CHANGES",
        old_values={"status": old_status},
        new_values={"status": STATUS_CHANGES_REQUESTED},
        metadata={"comment": comment}
    )

    # Notify SPOC
    from app.modules.FORMBLD.model import Form
    from app.modules.NOTIFY.service import notify_spoc
    form = Form.query.get(submission.form_id)
    notify_spoc(
        submission_id=submission_id,
        event_type="CHANGES_REQUESTED",
        message=f"Changes requested on your submission for {human_sheet_label(form)}. Reason: {comment}"
    )

    return submission

def reject_submission(submission_id, user_id, comment):
    """
    Terminally rejects the submission. Locks the record.
    """
    if not comment or not comment.strip():
        raise ValueError("A comment is required to reject a submission.")

    # See approve_submission for why this locks the row instead of using Query.get().
    submission = (
        Submission.query.filter_by(id=submission_id)
        .with_for_update()
        .one_or_none()
    )
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
    submission.status = STATUS_REJECTED
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
        new_values={"status": STATUS_REJECTED},
        metadata={"comment": comment}
    )

    # Notify SPOC
    from app.modules.FORMBLD.model import Form
    from app.modules.NOTIFY.service import notify_spoc
    form = Form.query.get(submission.form_id)
    notify_spoc(
        submission_id=submission_id,
        event_type="REJECTED",
        message=f"Your submission for {human_sheet_label(form)} has been rejected. Reason: {comment}"
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

def clear_recalc_review(submission_id, user_id, comment=None):
    """
    Clears a submission's needs_recalc_review flag once a reviewer has confirmed
    the flagged calculated value is acceptable. Resubmission after a fix already
    clears this flag automatically (it's recomputed from scratch on every submit);
    this is for the case where a reviewer accepts the existing value as-is,
    without the submitter having to resubmit anything.
    """
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        raise ValueError("Submission not found.")

    if not submission.needs_recalc_review:
        raise ValueError("This submission is not flagged for recalculation review.")

    # Permission check
    if not has_permission(user_id, "submission", "approve", scope_site_id=submission.site_id):
        raise ValueError("Permission denied: You do not have permission to clear review flags.")

    submission.needs_recalc_review = False
    submission.updated_by = user_id

    # Audit log
    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission",
        entity_id=submission.id,
        action="CLEAR_RECALC_REVIEW",
        old_values={"needs_recalc_review": True},
        new_values={"needs_recalc_review": False},
        metadata={"comment": comment}
    )

    return submission
