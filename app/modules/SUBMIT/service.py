import json
import calendar
from datetime import datetime, timezone

from sqlalchemy import tuple_

from app.database import db
from app.common.permissions import has_permission
from app.modules.ACCESS.model import AccessMatrix
from app.modules.SITEMST.model import Site
from app.modules.FORMBLD.model import Form, FormVersion, Field, FieldVersion
from app.modules.FORMBLD.service import get_form_version_fields
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.SUBMIT.model import (
    Submission,
    SubmissionValue,
    SubmissionValueIssue,
    ProofDocument,
    SubmissionPackage,
)
from app.modules.FRMULA.model import FormulaVersion
from app.modules.FRMULA.service import evaluate_formula
from app.modules.WFLWBLD.model import Workflow
from app.modules.WFLWBLD.service import (
    find_next_applicable_level,
    validate_workflow_path_for_site,
)

class DuplicateSubmissionError(Exception):
    def __init__(self, existing_id):
        self.existing_id = existing_id
        super().__init__(f"Submission already exists with ID: {existing_id}")

class SubmissionValidationError(ValueError):
    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = errors  # Dict of {field_code: error_message}

class PackageSubmissionError(ValueError):
    def __init__(self, message, errors=None, warnings=None):
        super().__init__(message)
        self.errors = errors or []
        self.warnings = warnings or []

FY_MONTH_ORDER = (4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3)
EDITABLE_PERIOD_STATUSES = ("OPEN", "REOPENED")
EDITABLE_SUBMISSION_STATUSES = ("Draft", "Changes Requested")
CELL_STATE_BLANK_EDITABLE = "blank_editable"
CELL_STATE_DRAFT_FILLED = "draft_filled"
CELL_STATE_SUBMITTED = "submitted"
CELL_STATE_APPROVED_LOCKED = "approved_locked"
CELL_STATE_CHANGES_REQUESTED = "changes_requested"
CELL_STATE_LATE_ENTRY = "late_entry"
ALLOWED_CELL_STATES = {
    CELL_STATE_BLANK_EDITABLE,
    CELL_STATE_DRAFT_FILLED,
    CELL_STATE_SUBMITTED,
    CELL_STATE_APPROVED_LOCKED,
    CELL_STATE_CHANGES_REQUESTED,
    CELL_STATE_LATE_ENTRY,
}


def submission_value_has_content(value):
    return bool(
        value
        and (
            (value.raw_value is not None and value.raw_value != "")
            or value.calculated_value is not None
        )
    )


def set_submission_value_state(value, state):
    if state not in ALLOWED_CELL_STATES:
        raise ValueError(f"Unsupported cell state: {state}")
    value.cell_state = state
    value.is_locked = state == CELL_STATE_APPROVED_LOCKED


def sync_submission_values_for_status(submission, user_id=None):
    values = SubmissionValue.query.filter_by(submission_id=submission.id).all()
    for value in values:
        has_content = submission_value_has_content(value)
        if submission.status == "Approved" and has_content:
            set_submission_value_state(value, CELL_STATE_APPROVED_LOCKED)
        elif submission.status in ("Submitted", "Resubmitted", "Under Review") and has_content:
            set_submission_value_state(value, CELL_STATE_SUBMITTED)
        elif submission.status == "Changes Requested" and has_content:
            set_submission_value_state(value, CELL_STATE_CHANGES_REQUESTED)
        elif has_content:
            set_submission_value_state(value, CELL_STATE_DRAFT_FILLED)
        else:
            set_submission_value_state(value, CELL_STATE_BLANK_EDITABLE)
        if user_id:
            value.updated_by = user_id


def format_period_label(year, month):
    if 1 <= month <= 12:
        return f"{calendar.month_name[month]} {year}"
    return f"Month {month} {year}"


def financial_year_label(start_year):
    return f"FY {start_year}-{str(start_year + 1)[-2:]}"


def _parse_form_metadata(form):
    metadata = {
        "sites": [],
        "workflow_id": None,
        "description_text": form.description or "",
    }
    if form.description and form.description.startswith("{"):
        try:
            parsed = json.loads(form.description)
            if isinstance(parsed, dict):
                metadata.update(parsed)
        except Exception:
            pass
    return metadata


def _fy_months(start_year):
    months = []
    for month in FY_MONTH_ORDER:
        year = start_year if month >= 4 else start_year + 1
        months.append({
            "month": month,
            "year": year,
            "label": calendar.month_abbr[month],
            "period_label": format_period_label(year, month),
        })
    return months


def _is_future_month(year, month):
    today = datetime.now(timezone.utc).date()
    return (year, month) > (today.year, today.month)


def _user_submission_site_ids(user_id):
    rows = AccessMatrix.query.filter_by(
        user_id=user_id,
        entity_type="submission",
        is_deleted=False,
    ).all()

    is_global = False
    allowed_site_ids = set()
    for row in rows:
        if not (row.can_view or row.can_submit or row.can_create or row.can_edit):
            continue
        if row.scope_type == "global":
            is_global = True
            break
        if row.scope_type == "site" and row.scope_site_id:
            allowed_site_ids.add(row.scope_site_id)

    if is_global:
        return {
            site.id
            for site in Site.query.filter_by(is_deleted=False).all()
        }
    return allowed_site_ids


def _published_forms_for_site(site_id):
    forms = Form.query.filter(
        Form.is_deleted == False,
        Form.current_version_id.is_not(None),
    ).order_by(Form.name.asc(), Form.id.asc()).all()

    assigned = []
    for form in forms:
        metadata = _parse_form_metadata(form)
        site_ids = metadata.get("sites") or []
        if site_id in site_ids:
            assigned.append((form, metadata))
    return assigned


def _field_payload(form_version_id):
    fields = []
    for field_version, field in get_form_version_fields(form_version_id):
        fields.append({
            "id": field.id,
            "field_id": field.id,
            "field_version_id": field_version.id,
            "field_code": field.field_code,
            "field_name": field_version.field_name,
            "field_type": field_version.field_type,
            "field_config": field_version.field_config or {},
            "display_order": field.display_order,
        })
    return fields


def _submission_values_payload(submission, fields):
    if not submission:
        return {}

    field_id_to_code = {field["field_id"]: field["field_code"] for field in fields}
    field_id_to_type = {field["field_id"]: field["field_type"] for field in fields}
    values = {}
    db_values = SubmissionValue.query.filter_by(submission_id=submission.id).all()

    proofs = {
        proof.field_id: proof
        for proof in ProofDocument.query.filter_by(
            submission_id=submission.id,
            is_deleted=False,
        ).all()
    }

    for value in db_values:
        code = field_id_to_code.get(value.field_id)
        if not code:
            continue
        if field_id_to_type.get(value.field_id) == "file":
            proof = proofs.get(value.field_id)
            values[code] = {
                "storage_key": proof.storage_key,
                "original_name": proof.original_name,
            } if proof else ""
        elif value.calculated_value is not None:
            values[code] = float(value.calculated_value)
        else:
            values[code] = value.raw_value or ""
    return values


def submission_proofs_payload(submission):
    if not submission:
        return {}
    proofs = ProofDocument.query.filter_by(
        submission_id=submission.id,
        is_deleted=False,
    ).all()
    return {
        proof.field_id: {
            "original_name": proof.original_name,
            "storage_key": proof.storage_key,
        }
        for proof in proofs
        if proof.field_id is not None
    }


def serialize_submission_value_issue(issue):
    from app.modules.USRMGMT.model import User

    raiser = User.query.get(issue.raised_by) if issue.raised_by else None
    return {
        "id": issue.id,
        "submission_value_id": issue.submission_value_id,
        "issue_text": issue.issue_text,
        "status": issue.status,
        "raised_by": issue.raised_by,
        "raised_by_name": raiser.full_name if raiser else "System",
        "created_at": issue.created_at,
    }


def submission_value_issues_map(value_ids):
    if not value_ids:
        return {}

    issues = (
        SubmissionValueIssue.query.filter(
            SubmissionValueIssue.submission_value_id.in_(value_ids),
            SubmissionValueIssue.is_deleted == False,
        )
        .order_by(SubmissionValueIssue.created_at.asc(), SubmissionValueIssue.id.asc())
        .all()
    )
    issue_map = {}
    for issue in issues:
        issue_map.setdefault(issue.submission_value_id, []).append(
            serialize_submission_value_issue(issue)
        )
    return issue_map


def submission_value_issues_by_field(submission, fields):
    if not submission:
        return {}

    db_values = SubmissionValue.query.filter_by(submission_id=submission.id).all()
    value_by_field_id = {value.field_id: value for value in db_values}
    issue_map = submission_value_issues_map([value.id for value in db_values])
    issues_by_field = {}
    for field in fields:
        value = value_by_field_id.get(field["field_id"])
        if not value:
            continue
        issues = issue_map.get(value.id, [])
        if issues:
            issues_by_field[field["field_code"]] = issues
            issues_by_field[str(field["field_id"])] = issues
    return issues_by_field


def submission_values_review_payload(submission, fields):
    if not submission:
        return {}

    db_values = SubmissionValue.query.filter_by(submission_id=submission.id).all()
    db_values_by_field = {value.field_id: value for value in db_values}
    issue_map = submission_value_issues_map([value.id for value in db_values])
    values = {}
    for field in fields:
        code = field["field_code"]
        db_value = db_values_by_field.get(field["field_id"])
        if db_value:
            values[code] = {
                "submission_value_id": db_value.id,
                "raw_value": db_value.raw_value,
                "calculated_value": (
                    float(db_value.calculated_value)
                    if db_value.calculated_value is not None
                    else None
                ),
                "cell_state": db_value.cell_state,
                "is_locked": db_value.is_locked,
                "remark": db_value.remark,
                "issues": issue_map.get(db_value.id, []),
            }
        else:
            values[code] = {
                "submission_value_id": None,
                "raw_value": None,
                "calculated_value": None,
                "cell_state": CELL_STATE_BLANK_EDITABLE,
                "is_locked": False,
                "remark": None,
                "issues": [],
            }
    return values


def _row_editability(period, submission):
    if not period:
        return {
            "state": "disabled",
            "editable": False,
            "reason": "Reporting period is not open for this month.",
        }
    if submission and (submission.is_locked or submission.status == "Approved"):
        return {
            "state": "read_only",
            "editable": False,
            "reason": "Approved or locked monthly sheet.",
        }
    if submission and submission.status in ("Submitted", "Resubmitted", "Under Review"):
        return {
            "state": "read_only",
            "editable": False,
            "reason": f"Monthly sheet is {submission.status}.",
        }
    if submission and submission.status == "Changes Requested":
        return {
            "state": "editable",
            "editable": True,
            "reason": "Monthly sheet was sent back for changes.",
        }
    if period.status in EDITABLE_PERIOD_STATUSES and (
        not submission or submission.status == "Draft"
    ):
        return {
            "state": "editable",
            "editable": True,
            "reason": "Reporting period is open for entry.",
        }
    return {
        "state": "disabled",
        "editable": False,
        "reason": f"Reporting period is {period.status}.",
    }


def get_annual_workbook_options(user_id):
    site_ids = _user_submission_site_ids(user_id)
    if not site_ids:
        return {"sites": [], "forms_by_site": {}}

    sites = Site.query.filter(
        Site.id.in_(site_ids),
        Site.is_deleted == False,
    ).order_by(Site.name.asc(), Site.id.asc()).all()

    forms_by_site = {}
    for site in sites:
        forms_by_site[str(site.id)] = [
            {
                "id": form.id,
                "name": form.name,
                "code": form.code,
                "workflow_id": metadata.get("workflow_id"),
            }
            for form, metadata in _published_forms_for_site(site.id)
        ]

    return {
        "sites": [
            {
                "id": site.id,
                "name": site.name,
                "code": site.code,
            }
            for site in sites
        ],
        "forms_by_site": forms_by_site,
    }


def compose_annual_workbook_data(user_id, site_id, form_id, fy_start_year):
    try:
        site_id = int(site_id)
        form_id = int(form_id)
        fy_start_year = int(fy_start_year)
    except (TypeError, ValueError):
        raise ValueError("A valid site, form, and financial year are required.")

    if site_id not in _user_submission_site_ids(user_id):
        raise ValueError("Permission denied: You cannot view submissions for this site.")

    if not (
        has_permission(user_id, "submission", "view", scope_site_id=site_id)
        or has_permission(user_id, "submission", "submit", scope_site_id=site_id)
    ):
        raise ValueError("Permission denied: You cannot view submissions for this site.")

    site = Site.query.filter_by(id=site_id, is_deleted=False).first()
    if not site:
        raise ValueError("Site not found.")

    form = Form.query.filter_by(id=form_id, is_deleted=False).first()
    if not form or not form.current_version_id:
        raise ValueError("Published form not found.")

    metadata = _parse_form_metadata(form)
    if site_id not in (metadata.get("sites") or []):
        raise ValueError("This form is not assigned to the selected site.")

    fields = _field_payload(form.current_version_id)
    months = _fy_months(fy_start_year)

    periods = ReportingPeriod.query.filter(
        ReportingPeriod.site_id == site_id,
        ReportingPeriod.is_deleted == False,
        tuple_(ReportingPeriod.year, ReportingPeriod.month).in_(
            [(item["year"], item["month"]) for item in months]
        ),
    ).all()
    period_by_key = {(period.year, period.month): period for period in periods}

    submissions = Submission.query.filter(
        Submission.site_id == site_id,
        Submission.form_id == form_id,
        Submission.is_deleted == False,
        Submission.reporting_period_id.in_([period.id for period in periods] or [0]),
    ).all()
    submission_by_period = {
        submission.reporting_period_id: submission
        for submission in submissions
    }

    rows = []
    for item in months:
        period = period_by_key.get((item["year"], item["month"]))
        submission = submission_by_period.get(period.id) if period else None
        editability = _row_editability(period, submission)
        rows.append({
            **item,
            "period_id": period.id if period else None,
            "period_status": period.status if period else None,
            "deadline": period.deadline.isoformat() if period and period.deadline else None,
            "submission_id": submission.id if submission else None,
            "submission_status": submission.status if submission else "Not Started",
            "is_locked": bool(submission.is_locked) if submission else False,
            "last_saved": (
                (submission.updated_at or submission.created_at).isoformat()
                if submission and (submission.updated_at or submission.created_at)
                else None
            ),
            "editability": editability,
            "values": _submission_values_payload(submission, fields),
            "issues": submission_value_issues_by_field(submission, fields),
        })

    return {
        "financial_year": {
            "start_year": fy_start_year,
            "label": financial_year_label(fy_start_year),
            "months": months,
        },
        "site": {
            "id": site.id,
            "name": site.name,
            "code": site.code,
        },
        "selected_form": {
            "id": form.id,
            "name": form.name,
            "code": form.code,
            "workflow_id": metadata.get("workflow_id"),
        },
        "fields": fields,
        "rows": rows,
    }


def compose_readonly_workbook_context(site_id, form_id, fy_start_year, active_period_id=None, form_version_id=None):
    """
    Builds a read-only annual workbook context without creating submissions.
    Intended for review/view modes where surrounding months are comparison context.
    """
    try:
        site_id = int(site_id)
        form_id = int(form_id)
        fy_start_year = int(fy_start_year)
    except (TypeError, ValueError):
        raise ValueError("A valid site, form, and financial year are required.")

    site = Site.query.filter_by(id=site_id, is_deleted=False).first()
    if not site:
        raise ValueError("Site not found.")

    form = Form.query.filter_by(id=form_id, is_deleted=False).first()
    if not form or not form.current_version_id:
        raise ValueError("Published form not found.")

    fields = _field_payload(form_version_id or form.current_version_id)
    months = _fy_months(fy_start_year)
    month_keys = [(item["year"], item["month"]) for item in months]

    periods = ReportingPeriod.query.filter(
        ReportingPeriod.site_id == site_id,
        ReportingPeriod.is_deleted == False,
        tuple_(ReportingPeriod.year, ReportingPeriod.month).in_(month_keys),
    ).all()
    period_by_key = {(period.year, period.month): period for period in periods}

    submissions = Submission.query.filter(
        Submission.site_id == site_id,
        Submission.form_id == form_id,
        Submission.is_deleted == False,
        Submission.reporting_period_id.in_([period.id for period in periods] or [0]),
    ).all()
    submission_by_period = {
        submission.reporting_period_id: submission
        for submission in submissions
    }

    rows = []
    for item in months:
        period = period_by_key.get((item["year"], item["month"]))
        submission = submission_by_period.get(period.id) if period else None
        rows.append({
            **item,
            "row_key": f"{item['year']}-{item['month']}",
            "period_id": period.id if period else None,
            "period_status": period.status if period else None,
            "submission_id": submission.id if submission else None,
            "submission_status": submission.status if submission else "Not Started",
            "status": submission.status if submission else (period.status if period else "Not Started"),
            "is_locked": bool(submission.is_locked) if submission else False,
            "last_saved": (
                (submission.updated_at or submission.created_at).isoformat()
                if submission and (submission.updated_at or submission.created_at)
                else None
            ),
            "values": submission_values_review_payload(submission, fields),
            "proofs": submission_proofs_payload(submission),
            "editable": False,
            "is_active_period": bool(period and active_period_id and period.id == active_period_id),
        })

    return {
        "financial_year": {
            "start_year": fy_start_year,
            "label": financial_year_label(fy_start_year),
        },
        "site": {
            "id": site.id,
            "name": site.name,
            "code": site.code,
        },
        "form": {
            "id": form.id,
            "name": form.name,
            "code": form.code,
        },
        "fields": fields,
        "rows": rows,
        "active_row_key": next(
            (row["row_key"] for row in rows if row["is_active_period"]),
            None,
        ),
    }

def get_approved_valsets_snapshot():
    """
    Returns a dictionary of all active approved value set entries mapping entry_code -> entry_label.
    """
    from app.modules.VALSET.model import ValueSet, ValueSetVersion, ValueSetEntry
    snapshot = {}
    approved_entries = (
        db.session.query(ValueSetEntry)
        .join(ValueSetVersion, ValueSetVersion.id == ValueSetEntry.value_set_version_id)
        .join(ValueSet, ValueSet.id == ValueSetVersion.value_set_id)
        .filter(
            ValueSet.is_deleted == False,
            ValueSetVersion.status == "Approved",
            ValueSetEntry.is_deleted == False,
            ValueSetEntry.is_active == True
        )
        .all()
    )
    for entry in approved_entries:
        snapshot[entry.entry_code] = entry.entry_label
    return snapshot

def get_spoc_sheets_buckets(user_id):
    """
    Filters reporting periods, published forms, and submissions by the access matrix.
    Returns: { "action_needed": [...], "not_started": [...], "submitted": [...] }
    """
    # 1. Get user's allowed sites
    matrix_rows = AccessMatrix.query.filter_by(user_id=user_id, entity_type="submission", is_deleted=False).all()
    
    is_global = False
    allowed_site_ids = set()
    
    for row in matrix_rows:
        if row.can_view or row.can_submit or row.can_create:
            if row.scope_type == "global":
                is_global = True
                break
            elif row.scope_type == "site" and row.scope_site_id is not None:
                allowed_site_ids.add(row.scope_site_id)
                
    if is_global:
        active_sites = Site.query.filter_by(is_deleted=False).all()
        allowed_site_ids = {site.id for site in active_sites}
        sites_map = {site.id: site for site in active_sites}
    else:
        active_sites = Site.query.filter(Site.id.in_(allowed_site_ids), Site.is_deleted == False).all()
        sites_map = {site.id: site for site in active_sites}
        
    # 2. Get all published forms
    published_forms = Form.query.filter_by(is_deleted=False).filter(Form.current_version_id.is_not(None)).all()
    
    # Check form applicability per site
    applicable_forms_by_site = {site_id: [] for site_id in allowed_site_ids}
    form_map = {}
    
    for f in published_forms:
        form_map[f.id] = f
        try:
            parsed_desc = json.loads(f.description or "{}")
        except Exception:
            parsed_desc = {}
        applicable_site_ids = parsed_desc.get("sites", [])
        
        for site_id in allowed_site_ids:
            if site_id in applicable_site_ids:
                applicable_forms_by_site[site_id].append(f)

    # 3. Get all active submissions for allowed sites
    submissions = (
        Submission.query.filter(Submission.site_id.in_(allowed_site_ids), Submission.is_deleted == False)
        .order_by(Submission.updated_at.desc())
        .all()
    )
    
    action_needed = []
    submitted = []
    
    # Helper to load username
    from app.modules.USRMGMT.model import User
    users_cache = {}
    def get_username(uid):
        if not uid:
            return "System"
        if uid not in users_cache:
            u = User.query.get(uid)
            users_cache[uid] = u.full_name if u else f"User {uid}"
        return users_cache[uid]

    # Track submission combos (site_id, form_id, reporting_period_id)
    submitted_combos = set()
    
    for sub in submissions:
        site = sites_map.get(sub.site_id)
        form = form_map.get(sub.form_id)
        period = ReportingPeriod.query.get(sub.reporting_period_id)
        
        if not site or not form or not period:
            continue
            
        submitted_combos.add((sub.site_id, sub.form_id, sub.reporting_period_id))
        
        period_label = format_period_label(period.year, period.month)
        
        status_text = sub.status
        if sub.status in ("Submitted", "Resubmitted", "Under Review") and sub.current_level is not None:
            status_text = f"{sub.status} (Level {sub.current_level})"

        item = {
            "submission_id": sub.id,
            "package_id": sub.package_id,
            "site_id": sub.site_id,
            "form_name": form.name,
            "form_id": sub.form_id,
            "form_code": form.code,
            "site_name": site.name,
            "reporting_period_id": sub.reporting_period_id,
            "period_label": period_label,
            "year": period.year,
            "month": period.month,
            "status": sub.status,
            "status_text": status_text,
            "last_saved": sub.updated_at or sub.created_at,
            "submitted_at": sub.submitted_at,
            "submitted_by": get_username(sub.submitted_by)
        }
        
        if sub.status in ("Draft", "Changes Requested"):
            action_needed.append(item)
        else:
            submitted.append(item)
            
    # 4. Generate Not Started bucket
    not_started = []
    
    for site_id in allowed_site_ids:
        site = sites_map.get(site_id)
        # Fetch open periods for this site
        open_periods = ReportingPeriod.query.filter_by(
            site_id=site_id,
            is_deleted=False
        ).filter(ReportingPeriod.status.in_(("OPEN", "REOPENED"))).all()
        
        for period in open_periods:
            period_label = format_period_label(period.year, period.month)
            for form in applicable_forms_by_site[site_id]:
                combo = (site_id, form.id, period.id)
                if combo not in submitted_combos:
                    not_started.append({
                        "form_id": form.id,
                        "form_name": form.name,
                        "form_code": form.code,
                        "site_id": site.id,
                        "site_name": site.name,
                        "reporting_period_id": period.id,
                        "period_label": period_label,
                        "year": period.year,
                        "month": period.month,
                        "deadline": period.deadline.isoformat() if period.deadline else None
                    })
                    
    return {
        "action_needed": action_needed,
        "not_started": not_started,
        "submitted": submitted
    }

def create_draft_submission(site_id, form_id, reporting_period_id, user_id):
    """
    Creates a new draft submission for the given site, form, and period.
    """
    # 1. Authorization check
    if not has_permission(user_id, "submission", "create", scope_site_id=site_id) and \
       not has_permission(user_id, "submission", "submit", scope_site_id=site_id):
        raise ValueError("Permission denied: You cannot create submissions for this site.")
        
    # 2. Period check
    period = ReportingPeriod.query.get(reporting_period_id)
    if not period or period.is_deleted:
        raise ValueError("Reporting period not found.")
    if period.status not in ("OPEN", "REOPENED"):
        raise ValueError(f"Cannot create a submission for a reporting period that is {period.status}.")
        
    # 3. Form check
    form = Form.query.filter_by(id=form_id, is_deleted=False).first()
    if not form or not form.current_version_id:
        raise ValueError("Published form version not found.")
        
    try:
        parsed_desc = json.loads(form.description or "{}")
    except Exception:
        parsed_desc = {}
        
    if site_id not in parsed_desc.get("sites", []):
        raise ValueError("This form is not applicable to the selected site.")
        
    # 4. Workflow assignment
    wf_id = parsed_desc.get("workflow_id")
    if not wf_id:
        raise ValueError("This form is not ready for submission because no approval workflow has been assigned.")
        
    workflow = Workflow.query.filter_by(id=wf_id, is_deleted=False).first()
    if not workflow or not workflow.current_version_id:
        raise ValueError("This form is not ready for submission because no approval workflow has been assigned.")
        
    # 5. Duplicate check
    existing = Submission.query.filter_by(
        site_id=site_id,
        form_id=form_id,
        reporting_period_id=reporting_period_id,
        is_deleted=False
    ).first()
    
    if existing:
        raise DuplicateSubmissionError(existing.id)
        
    # 6. Create Submission
    sub = Submission(
        site_id=site_id,
        form_id=form_id,
        form_version_id=form.current_version_id,
        reporting_period_id=reporting_period_id,
        workflow_version_id=workflow.current_version_id,
        status="Draft",
        created_by=user_id,
        updated_by=user_id,
        current_level=1
    )
    db.session.add(sub)
    db.session.flush()

    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission",
        entity_id=sub.id,
        action="CREATE_DRAFT",
        old_values=None,
        new_values={
            "status": "Draft",
            "site_id": site_id,
            "form_id": form_id,
            "reporting_period_id": reporting_period_id
        }
    )

    return sub

def _values_have_content(values):
    if not isinstance(values, dict):
        return False
    for value in values.values():
        if value is None or value == "":
            continue
        if isinstance(value, dict):
            if any(v not in (None, "") for v in value.values()):
                return True
            continue
        return True
    return False

def get_or_create_submission_package(site_id, period_id, user_id, package_type="monthly_workbook"):
    package = SubmissionPackage.query.filter_by(
        site_id=site_id,
        period_id=period_id,
        package_type=package_type,
        is_deleted=False,
    ).first()
    if package:
        package.updated_by = user_id
        return package

    package = SubmissionPackage(
        site_id=site_id,
        period_id=period_id,
        package_type=package_type,
        status="Draft",
        created_by=user_id,
        updated_by=user_id,
    )
    db.session.add(package)
    db.session.flush()
    return package

def submit_monthly_workbook_package(site_id, period_id=None, year=None, month=None, user_id=None, selected_form_id=None, values=None):
    """
    Foundation package submit: groups assigned monthly form submissions for one site and period.
    Existing monthly submit logic remains the source of validation/routing/notifications.
    """
    try:
        site_id = int(site_id)
    except (TypeError, ValueError):
        raise ValueError("A valid site is required.")

    if not user_id:
        raise ValueError("A valid user is required.")

    if not has_permission(user_id, "submission", "submit", scope_site_id=site_id):
        raise ValueError("Permission denied: You do not have permission to submit this workbook package.")

    period = None
    if period_id:
        period = ReportingPeriod.query.filter_by(id=period_id, site_id=site_id, is_deleted=False).first()
    elif year and month:
        period = ReportingPeriod.query.filter_by(
            site_id=site_id,
            year=int(year),
            month=int(month),
            is_deleted=False,
        ).first()
    if not period:
        raise ValueError("Reporting period not found for this site and month.")
    if period.status not in EDITABLE_PERIOD_STATUSES:
        raise ValueError(f"Cannot submit a workbook package for a reporting period that is {period.status}.")

    assigned_forms = [form for form, _metadata in _published_forms_for_site(site_id)]
    if not assigned_forms:
        raise ValueError("No published forms are assigned to this site.")

    assigned_form_ids = {form.id for form in assigned_forms}
    selected_form_id = int(selected_form_id) if selected_form_id else None
    if selected_form_id and selected_form_id not in assigned_form_ids:
        raise ValueError("Selected form is not assigned to this site.")

    package = get_or_create_submission_package(site_id, period.id, user_id)
    included = []
    skipped = []
    errors = []
    submitted_count = 0

    existing_submissions = {
        submission.form_id: submission
        for submission in Submission.query.filter(
            Submission.site_id == site_id,
            Submission.reporting_period_id == period.id,
            Submission.form_id.in_(assigned_form_ids),
            Submission.is_deleted == False,
        ).all()
    }

    for form in assigned_forms:
        submission = existing_submissions.get(form.id)
        created_from_payload = False

        if not submission and selected_form_id == form.id and _values_have_content(values):
            try:
                submission = create_draft_submission(site_id, form.id, period.id, user_id)
                created_from_payload = True
            except DuplicateSubmissionError as exc:
                submission = Submission.query.get(exc.existing_id)

        if not submission:
            skipped.append({
                "form_id": form.id,
                "form_name": form.name,
                "reason": "No draft or filled values to submit.",
            })
            continue

        if submission.is_locked or submission.status == "Approved":
            skipped.append({
                "form_id": form.id,
                "form_name": form.name,
                "submission_id": submission.id,
                "reason": "Already approved or locked.",
            })
            continue

        if selected_form_id == form.id and values is not None and submission.status in EDITABLE_SUBMISSION_STATUSES:
            autosave_submission_values(submission.id, values or {}, user_id)

        submission.package_id = package.id
        submission.updated_by = user_id

        if submission.status in EDITABLE_SUBMISSION_STATUSES:
            try:
                submit_submission(submission.id, user_id)
                submitted_count += 1
            except SubmissionValidationError as exc:
                errors.append({
                    "form_id": form.id,
                    "form_name": form.name,
                    "submission_id": submission.id,
                    "error": str(exc),
                    "validation_errors": exc.errors,
                })
                continue
            except ValueError as exc:
                errors.append({
                    "form_id": form.id,
                    "form_name": form.name,
                    "submission_id": submission.id,
                    "error": str(exc),
                })
                continue

        included.append({
            "form_id": form.id,
            "form_name": form.name,
            "submission_id": submission.id,
            "status": submission.status,
            "created": created_from_payload,
        })

    if errors:
        raise PackageSubmissionError("Workbook package submission failed validation.", errors=errors, warnings=skipped)
    if submitted_count == 0:
        raise PackageSubmissionError(
            "No editable or submit-ready forms were found for this workbook package.",
            warnings=skipped,
        )

    package.status = "Submitted"
    package.submitted_by = user_id
    package.submitted_at = datetime.now(timezone.utc)
    included_levels = [
        submission.current_level
        for submission in Submission.query.filter(
            Submission.id.in_([item["submission_id"] for item in included])
        ).all()
        if submission.current_level is not None
    ]
    package.current_level = min(included_levels) if included_levels else None
    package.updated_by = user_id

    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission_package",
        entity_id=package.id,
        action="SUBMIT_PACKAGE",
        old_values=None,
        new_values={
            "status": package.status,
            "site_id": site_id,
            "period_id": period.id,
            "submission_ids": [item["submission_id"] for item in included],
        },
    )

    return {
        "package_id": package.id,
        "status": package.status,
        "site_id": site_id,
        "period_id": period.id,
        "period_label": format_period_label(period.year, period.month),
        "included_submissions": included,
        "skipped_forms": skipped,
    }

def autosave_submission_values(submission_id, values_dict, user_id):
    """
    Saves raw values and recalculates all formula fields.
    """
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        raise ValueError("Submission not found.")
        
    if submission.status not in ("Draft", "Changes Requested"):
        raise ValueError(f"Cannot edit submission in status: {submission.status}")
        
    if not has_permission(user_id, "submission", "edit", scope_site_id=submission.site_id):
        raise ValueError("Permission denied: You do not have permission to edit submissions for this site.")

    submission.updated_by = user_id
        
    # Get form version fields
    fields = get_form_version_fields(submission.form_version_id)
    fields_map = {}
    for fv, f in fields:
        fields_map[f.field_code] = {
            "field_id": f.id,
            "field_version_id": fv.id,
            "field_type": fv.field_type,
            "field_config": fv.field_config or {}
        }
        
    # Save input values
    for field_code, raw_value in values_dict.items():
        if field_code not in fields_map:
            continue
            
        field_info = fields_map[field_code]
        if field_info["field_type"] in ("calculated", "file"):
            # Skip file fields (handled by dedicated upload endpoint) and calculated fields
            continue
            
        f_id = field_info["field_id"]
        fv_id = field_info["field_version_id"]
        
        val_row = SubmissionValue.query.filter_by(
            submission_id=submission_id,
            field_id=f_id
        ).first()
        
        if not val_row:
            val_row = SubmissionValue(
                submission_id=submission_id,
                field_id=f_id,
                field_version_id=fv_id,
                created_by=user_id
            )
            db.session.add(val_row)
            
        val_row.raw_value = str(raw_value) if raw_value is not None and raw_value != "" else None
        val_row.calculated_value = None
        set_submission_value_state(
            val_row,
            CELL_STATE_DRAFT_FILLED if val_row.raw_value is not None else CELL_STATE_BLANK_EDITABLE,
        )
        val_row.updated_by = user_id
        
    db.session.flush()
    
    # Backend calculations
    # Load all saved values to pass as inputs
    db_values = SubmissionValue.query.filter_by(submission_id=submission_id).all()
    id_to_code = {info["field_id"]: code for code, info in fields_map.items()}
    
    field_values = {}
    for val in db_values:
        code = id_to_code.get(val.field_id)
        if code:
            if val.calculated_value is not None:
                field_values[code] = float(val.calculated_value)
            elif val.raw_value is not None:
                field_values[code] = val.raw_value
            else:
                field_values[code] = ""
                
    # Prepare value set snapshot
    value_set_snapshot = get_approved_valsets_snapshot()
    
    calculation_errors = {}
    
    # Calculate each formula
    for code, info in fields_map.items():
        if info["field_type"] == "calculated":
            f_id = info["field_id"]
            fv_id = info["field_version_id"]
            formula_ver_id = info["field_config"].get("formula_version_id")
            
            if not formula_ver_id:
                calculation_errors[code] = "Formula is not configured."
                continue
                
            formula_version = FormulaVersion.query.get(formula_ver_id)
            if not formula_version:
                calculation_errors[code] = "Formula version not found."
                continue
                
            try:
                # Run evaluation
                result = evaluate_formula(formula_version.expression, field_values, value_set_snapshot)
                
                # Save calculation row
                calc_row = SubmissionValue.query.filter_by(
                    submission_id=submission_id,
                    field_id=f_id
                ).first()
                
                if not calc_row:
                    calc_row = SubmissionValue(
                        submission_id=submission_id,
                        field_id=f_id,
                        field_version_id=fv_id,
                        created_by=user_id
                    )
                    db.session.add(calc_row)
                    
                calc_row.raw_value = None
                calc_row.calculated_value = result
                set_submission_value_state(calc_row, CELL_STATE_DRAFT_FILLED)
                calc_row.formula_version_id = formula_version.id
                calc_row.formula_eval_at = datetime.now(timezone.utc)
                
                # Snapshot tokens and values
                inputs_snapshot = {}
                for key in (formula_version.tokens or {}).keys():
                    if key in field_values:
                        inputs_snapshot[key] = field_values[key]
                    elif key in value_set_snapshot:
                        inputs_snapshot[key] = value_set_snapshot[key]
                calc_row.formula_inputs_snapshot = inputs_snapshot
                calc_row.updated_by = user_id
                
                # Add calculated value to field_values so subsequent calculations can read it
                field_values[code] = result
                
            except Exception as e:
                # Log evaluation error and clear previous calculation
                calc_row = SubmissionValue.query.filter_by(
                    submission_id=submission_id,
                    field_id=f_id
                ).first()
                if calc_row:
                    calc_row.calculated_value = None
                    calc_row.formula_eval_at = datetime.now(timezone.utc)
                    calc_row.updated_by = user_id
                calculation_errors[code] = str(e)
                field_values[code] = None
                
    db.session.flush()
    return calculation_errors

def submit_submission(submission_id, user_id):
    """
    Validates the submission and transitions its status to Submitted.
    """
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        raise ValueError("Submission not found.")
        
    if submission.status not in ("Draft", "Changes Requested"):
        raise ValueError(f"Cannot submit submission in status: {submission.status}")
        
    if not has_permission(user_id, "submission", "submit", scope_site_id=submission.site_id):
        raise ValueError("Permission denied: You do not have permission to submit this sheet.")

    # Confirm form has workflow assigned
    form = Form.query.get(submission.form_id)
    try:
        parsed_desc = json.loads(form.description or "{}")
    except Exception:
        parsed_desc = {}
    if not parsed_desc.get("workflow_id"):
        raise ValueError("This form is not ready for submission because no approval workflow has been assigned.")
    validate_workflow_path_for_site(submission.workflow_version_id, submission.site_id)
    first_applicable_level = find_next_applicable_level(
        submission.workflow_version_id,
        submission.site_id,
        0,
    )
    if not first_applicable_level:
        raise ValueError(
            "This workflow has no eligible approver path for this submission site. "
            "Please contact your administrator."
        )
        
    # Get form version fields
    fields = get_form_version_fields(submission.form_version_id)
    
    # Load saved values
    db_values = SubmissionValue.query.filter_by(submission_id=submission_id).all()
    values_map = {val.field_id: val for val in db_values}
    
    validation_errors = {}
    
    for fv, f in fields:
        config = fv.field_config or {}
        val_obj = values_map.get(f.id)
        
        # 1. Required field check
        is_required = config.get("is_required") is True
        has_val = val_obj is not None and (
            (val_obj.raw_value is not None and val_obj.raw_value != "") or
            (val_obj.calculated_value is not None)
        )
        
        if is_required and not has_val:
            validation_errors[f.field_code] = f"{fv.field_name} is required."
            continue
            
        # 2. Proof required check
        if config.get("proof_required") is True and fv.field_type == "file":
            proof = ProofDocument.query.filter_by(
                submission_id=submission_id,
                field_id=f.id,
                is_deleted=False
            ).first()
            if not proof:
                validation_errors[f.field_code] = f"Proof document is required for {fv.field_name}."
                continue
                
        # 3. Calculation errors check
        if fv.field_type == "calculated":
            if not val_obj or val_obj.calculated_value is None:
                validation_errors[f.field_code] = f"Calculated value is missing or has formula errors."
                continue

        # 4. Numeric type validation
        from app.modules.FORMBLD.service import NUMERIC_FIELD_TYPES
        is_num_type = (fv.field_type in NUMERIC_FIELD_TYPES or 
                       config.get("is_numeric") is True or 
                       str(config.get("result_type") or config.get("value_type") or "").lower() in NUMERIC_FIELD_TYPES)
        if is_num_type and val_obj and val_obj.raw_value is not None and val_obj.raw_value != "":
            try:
                float(val_obj.raw_value)
            except ValueError:
                validation_errors[f.field_code] = f"{fv.field_name} must be a valid number."
                continue

        # 5. Dropdown validation
        if fv.field_type == "dropdown" and val_obj and val_obj.raw_value is not None and val_obj.raw_value != "":
            vsv_id = config.get("value_set_version_id")
            if vsv_id:
                from app.modules.VALSET.model import ValueSetEntry
                entry = ValueSetEntry.query.filter_by(
                    value_set_version_id=vsv_id,
                    entry_code=val_obj.raw_value,
                    is_active=True,
                    is_deleted=False
                ).first()
                if not entry:
                    validation_errors[f.field_code] = f"Invalid option selected for {fv.field_name}."
                    continue
                
    if validation_errors:
        raise SubmissionValidationError("Validation failed. Please correct the fields.", validation_errors)
        
    # Verify duplicate on final submit
    existing = Submission.query.filter(
        Submission.id != submission_id,
        Submission.site_id == submission.site_id,
        Submission.form_id == submission.form_id,
        Submission.reporting_period_id == submission.reporting_period_id,
        Submission.is_deleted == False
    ).first()
    if existing:
        raise DuplicateSubmissionError(existing.id)
        
    # Transition status
    old_status = submission.status
    new_status = "Resubmitted" if old_status == "Changes Requested" else "Submitted"

    if old_status == "Changes Requested":
        # Soft-delete all existing ApprovalAction records for this submission
        from app.modules.APPROV.model import ApprovalAction
        prior_approvals = ApprovalAction.query.filter_by(
            submission_id=submission.id,
            action="Approve",
            is_deleted=False
        ).all()
        for app_act in prior_approvals:
            app_act.is_deleted = True
            app_act.deleted_by = user_id
            app_act.deleted_at = datetime.now(timezone.utc)
            app_act.delete_reason = "Workflow reset to Level 1 due to SPOC resubmission after Changes Requested"

    submission.status = new_status
    submission.current_level = first_applicable_level.level_number
    submission.submitted_by = user_id
    submission.submitted_at = datetime.now(timezone.utc)
    submission.last_status_changed_at = datetime.now(timezone.utc)
    submission.updated_by = user_id
    sync_submission_values_for_status(submission, user_id)
    
    # Audit log
    from app.modules.AUDITL.service import log_audit
    log_audit(
        actor_user_id=user_id,
        entity_type="submission",
        entity_id=submission.id,
        action="SUBMIT",
        old_values={"status": old_status},
        new_values={"status": new_status}
    )
    
    # Trigger NOTIFY event
    from app.modules.NOTIFY.service import notify_level_approvers
    notify_level_approvers(submission.id)
        
    return submission
