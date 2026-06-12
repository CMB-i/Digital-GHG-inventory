from datetime import date, datetime, timezone

from app.common.validators import ValidationError
from app.database import db
from app.modules.AUDITL.service import log_audit
from app.modules.PERIOD.model import ReportingPeriod


VALID_STATUSES = ("OPEN", "SUBMISSION_CLOSED", "LOCKED", "REOPENED")

VALID_TRANSITIONS = {
    "OPEN": "SUBMISSION_CLOSED",
    "SUBMISSION_CLOSED": "LOCKED",
    "LOCKED": "REOPENED",
    "REOPENED": "OPEN",
}

TRANSITION_LABELS = {
    "OPEN": "Close Submission",
    "SUBMISSION_CLOSED": "Lock",
    "LOCKED": "Reopen",
    "REOPENED": "Mark Open",
}

# Maps the target status to the action required to reach it.
TRANSITION_ACTION = {
    "SUBMISSION_CLOSED": "edit",
    "LOCKED": "edit",
    "REOPENED": "reopen",
    "OPEN": "edit",
}

STATUS_LABELS = {
    "OPEN": "Open",
    "SUBMISSION_CLOSED": "Closed",
    "LOCKED": "Locked",
    "REOPENED": "Reopened",
}

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
    period = ReportingPeriod.query.filter_by(id=period_id, is_deleted=False).one_or_none()
    if not period:
        raise ValidationError("Reporting period not found.")

    expected_target = VALID_TRANSITIONS.get(period.status)
    if expected_target != target_status:
        raise ValidationError(
            f"Cannot transition from {period.status} to {target_status}."
        )

    old_status = period.status
    if target_status == "REOPENED":
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
