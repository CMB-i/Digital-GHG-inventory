from datetime import date, datetime, timezone

from app.common.permissions import has_permission
from app.common.validators import ValidationError
from app.database import db
from app.modules.AUDITL.service import log_audit
from app.modules.PERIOD.model import ReportingPeriod


VALID_STATUSES = ("OPEN", "SUBMISSION_CLOSED", "LOCKED")

VALID_TRANSITIONS = {
    "OPEN": "SUBMISSION_CLOSED",
    "SUBMISSION_CLOSED": "LOCKED",
    "LOCKED": "OPEN",
}

TRANSITION_LABELS = {
    "OPEN": "Close Submission",
    "SUBMISSION_CLOSED": "Lock",
    "LOCKED": "Reopen",
}

STATUS_LABELS = {
    "OPEN": "Open",
    "SUBMISSION_CLOSED": "Closed",
    "LOCKED": "Locked",
}


def required_transition_action(current_status, target_status):
    """
    Maps a (current_status, target_status) transition to the permission
    action it requires. Keyed by target status alone, this used to conflate
    two different things once LOCKED -> OPEN became a single step: "close
    submission was reversed" (cheap, only needs "edit") and "a locked period
    was reopened" (must require "reopen"). LOCKED -> OPEN is the one-step
    replacement for the old two-step Lock -> Reopen -> Mark-Open cycle and is
    the only transition that needs "reopen"; every other valid transition
    only needs "edit". Returns None if (current_status, target_status) isn't
    a valid direct transition at all.
    """
    if VALID_TRANSITIONS.get(current_status) != target_status:
        return None
    if current_status == "LOCKED" and target_status == "OPEN":
        return "reopen"
    return "edit"


MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def _utc_now():
    return datetime.now(timezone.utc)


def list_periods(site_id=None, status=None):
    query = ReportingPeriod.query.filter_by(is_deleted=False)
    if site_id:
        query = query.filter_by(site_id=site_id)
    if status and status in VALID_STATUSES:
        query = query.filter_by(status=status)
    return query.order_by(
        ReportingPeriod.year.desc(),
        ReportingPeriod.month.desc(),
        ReportingPeriod.site_id.asc(),
    ).all()


def get_period(period_id):
    return ReportingPeriod.query.filter_by(id=period_id, is_deleted=False).one_or_none()


def sort_period_group(periods, site_map, sort_by=None, sort_dir="desc"):
    """
    Sorts periods belonging to a single (year, month) group in place. This is
    scoped to one month's periods only -- the month grouping/ordering itself
    is a separate, unrelated concern handled by the index view.

    sort_by="updated_at" sorts by last-updated timestamp (direction per
    sort_dir); anything else falls back to the default site-name ordering.
    """
    if sort_by == "updated_at":
        periods.sort(key=lambda p: p.updated_at, reverse=(sort_dir == "desc"))
    else:
        periods.sort(key=lambda p: site_map[p.site_id].name if p.site_id in site_map else "")
    return periods


def create_period(site_id, year, month, deadline, actor_id):
    if not site_id:
        raise ValidationError("Site is required.")
    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError):
        raise ValidationError("Invalid year or month.")

    if not (2000 <= year <= 2100):
        raise ValidationError("Year must be between 2000 and 2100.")
    if not (1 <= month <= 12):
        raise ValidationError("Month must be between 1 and 12.")

    parsed_deadline = None
    if deadline and isinstance(deadline, str) and deadline.strip():
        try:
            parsed_deadline = date.fromisoformat(deadline.strip())
        except ValueError:
            raise ValidationError("Invalid deadline date.")
    elif isinstance(deadline, date):
        parsed_deadline = deadline

    existing = ReportingPeriod.query.filter_by(
        site_id=site_id,
        year=year,
        month=month,
        is_deleted=False,
    ).first()
    if existing:
        raise ValidationError(
            "A reporting period for this site, year, and month already exists."
        )

    period = ReportingPeriod(
        site_id=site_id,
        year=year,
        month=month,
        status="OPEN",
        deadline=parsed_deadline,
        created_by=actor_id,
    )
    db.session.add(period)
    return period


def bulk_open_month(year, month, actor_id, site_ids):
    """Create OPEN periods for sites that do not yet have one for year/month."""
    created = []
    for site_id in site_ids:
        existing = ReportingPeriod.query.filter_by(
            site_id=site_id, year=year, month=month, is_deleted=False
        ).first()
        if existing:
            continue
        period = ReportingPeriod(
            site_id=site_id,
            year=year,
            month=month,
            status="OPEN",
            deadline=None,
            created_by=actor_id,
        )
        db.session.add(period)
        created.append(period)
    return created


def transition_period(period_id, target_status, actor_id, reopen_reason=None):
    # Locks the row so a submission mid-commit (see submit_submission's own
    # ReportingPeriod re-check) can't land in the same window as a concurrent
    # period-status change without one of the two waiting for the other.
    period = (
        ReportingPeriod.query.filter_by(id=period_id, is_deleted=False)
        .with_for_update()
        .one_or_none()
    )
    if not period:
        raise ValidationError("Reporting period not found.")

    expected_target = VALID_TRANSITIONS.get(period.status)
    if expected_target != target_status:
        raise ValidationError(
            f"Cannot transition from {period.status} to {target_status}."
        )

    old_status = period.status
    if old_status == "LOCKED" and target_status == "OPEN":
        reason = (reopen_reason or "").strip()
        if not reason:
            raise ValidationError("A reopen reason is required.")
        period.reopen_reason = reason
        period.reopened_at = _utc_now()
        period.reopened_by = actor_id

    period.status = target_status
    period.updated_by = actor_id
    log_audit(
        actor_id,
        "period",
        period.id,
        "PERIOD_STATUS_CHANGED",
        old_values={"status": old_status},
        new_values={"status": target_status},
    )
    return period


def _run_in_savepoint(fn):
    """
    Runs fn() inside a SAVEPOINT so a failure for one period doesn't undo
    periods already transitioned earlier in the same batch -- those still
    commit together at the view layer's single db.session.commit(). Mirrors
    APPROV.service._attempt_in_savepoint.
    """
    nested = db.session.begin_nested()
    try:
        fn()
        nested.commit()
        return True, None
    except Exception as exc:
        nested.rollback()
        return False, str(exc)


def bulk_transition_periods(period_ids, target_status, actor_id, reopen_reason=None):
    """
    Transitions every given period to target_status where the caller is
    permitted and the period is currently eligible. Purely additive: a period
    the caller lacks permission for, one whose current status doesn't lead to
    target_status (or that no longer exists), is recorded as skipped rather
    than aborting the batch; one that raises during transition_period itself
    is recorded as failed. Neither skip nor fail rolls back periods that
    already succeeded earlier in the same call -- see approve_package in
    APPROV/service.py for the same partial-eligibility handling.
    """
    results = {"succeeded": [], "skipped": [], "failed": []}

    seen_ids = set()
    for period_id in period_ids:
        if period_id in seen_ids:
            continue
        seen_ids.add(period_id)

        period = get_period(period_id)
        if not period:
            results["skipped"].append({
                "period_id": period_id,
                "reason": "Reporting period not found.",
            })
            continue

        # Permission depends on the (current_status, target_status) pair, not
        # target_status alone -- a batch can mix current statuses (e.g. some
        # LOCKED, some SUBMISSION_CLOSED) even though today's transition graph
        # happens to make LOCKED the only source that reaches OPEN.
        required_action = required_transition_action(period.status, target_status)
        if not required_action:
            results["skipped"].append({
                "period_id": period_id,
                "reason": f"Not eligible for this transition (current status: {period.status}).",
            })
            continue

        if not has_permission(actor_id, "period", required_action):
            results["skipped"].append({
                "period_id": period_id,
                "reason": "You do not have permission for this transition.",
            })
            continue

        outcome = {}

        def _do(pid=period_id):
            outcome["period"] = transition_period(
                period_id=pid,
                target_status=target_status,
                actor_id=actor_id,
                reopen_reason=reopen_reason,
            )

        ok, error = _run_in_savepoint(_do)
        if ok:
            results["succeeded"].append(outcome["period"])
        else:
            results["failed"].append({"period_id": period_id, "reason": error})

    return results
