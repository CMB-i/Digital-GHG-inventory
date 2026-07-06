import json
import calendar
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

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
    WorkbookFieldValue,
    ProofDocument,
    SubmissionPackage,
)
from app.modules.FRMULA.model import FormulaVersion
from app.modules.FRMULA.service import aggregate_operand_names, evaluate_formula
from app.modules.WFLWBLD.model import Workflow
from app.modules.WFLWBLD.service import (
    find_next_applicable_level,
    validate_workflow_path_for_site,
)
from app.modules.WKBK.model import (
    Workbook, WorkbookForm, WorkbookSite, WorkbookSiteSubmitter
)


LIVE_WORKBOOK_STATUSES = {"published", "live"}


def _get_workflow_id_for_form(form_id):
    """
    Returns the workflow_id assigned to the active workbook that contains
    this form, or None if no active workbook or no workflow is assigned.

    workbook.workflow_id is now the authoritative approval path assignment.
    """
    wf_rows = (
        db.session.query(Workbook.id, Workbook.workflow_id)
        .join(WorkbookForm, WorkbookForm.workbook_id == Workbook.id)
        .filter(
            WorkbookForm.form_id == form_id,
            Workbook.is_active == True,
        )
        .all()
    )

    assigned = [row.workflow_id for row in wf_rows if row.workflow_id]

    if len(assigned) == 1:
        return assigned[0]

    if len(assigned) > 1:
        raise ValueError(
            "This sheet belongs to multiple workbooks with approval paths. "
            "Please submit from a specific workbook context."
        )

    return None


def _get_workflow_for_workbook(workbook):
    if not workbook.workflow_id:
        return None
    return Workflow.query.filter_by(id=workbook.workflow_id, is_deleted=False).first()


def _require_active_workbook(workbook_id):
    try:
        workbook_id = int(workbook_id)
    except (TypeError, ValueError):
        raise ValueError("A valid workbook is required.")

    workbook = Workbook.query.filter_by(id=workbook_id, is_active=True).first()
    if not workbook:
        raise ValueError("Workbook not found.")
    if str(workbook.status or "").strip().lower() not in LIVE_WORKBOOK_STATUSES:
        raise ValueError("This workbook is not published for data entry.")
    return workbook


def _require_workbook_site_submitter(user_id, workbook_id, site_id):
    if not (
        has_permission(user_id, "submission", "view", scope_site_id=site_id)
        or has_permission(user_id, "submission", "submit", scope_site_id=site_id)
    ):
        raise ValueError("Permission denied: You cannot view submissions for this site.")

    site_link = WorkbookSite.query.filter_by(
        workbook_id=workbook_id,
        site_id=site_id,
    ).first()
    if not site_link:
        raise ValueError("This workbook is not assigned to the selected site.")

    submitter = WorkbookSiteSubmitter.query.filter_by(
        workbook_id=workbook_id,
        site_id=site_id,
        user_id=user_id,
    ).first()
    if not submitter:
        raise ValueError(
            "Permission denied: You are not assigned to submit this workbook for this site."
        )


def _require_workbook_runtime_access(user_id, workbook_id, site_id):
    try:
        site_id = int(site_id)
    except (TypeError, ValueError):
        raise ValueError("A valid site is required.")

    workbook = _require_active_workbook(workbook_id)
    site = Site.query.filter_by(id=site_id, is_deleted=False).first()
    if not site:
        raise ValueError("Site not found.")
    _require_workbook_site_submitter(user_id, workbook.id, site_id)
    return workbook, site


def _workbook_sheet_rows(workbook_id):
    return (
        db.session.query(WorkbookForm, Form)
        .join(Form, Form.id == WorkbookForm.form_id)
        .filter(
            WorkbookForm.workbook_id == workbook_id,
            Form.is_deleted == False,
            Form.current_version_id.is_not(None),
        )
        .order_by(WorkbookForm.display_order.asc(), WorkbookForm.id.asc())
        .all()
    )


def _workbook_sheet_payload(workbook_form, form):
    return {
        "id": form.id,
        "form_id": form.id,
        "name": workbook_form.sheet_label or human_sheet_label(form),
        "code": form.code,
        "display_order": workbook_form.display_order,
    }


def _published_forms_for_workbook(workbook_id):
    return [
        (
            form,
            {
                "sheet_label": workbook_form.sheet_label or human_sheet_label(form),
                "display_order": workbook_form.display_order,
                "workbook_id": workbook_id,
            },
        )
        for workbook_form, form in _workbook_sheet_rows(workbook_id)
    ]


def _require_form_in_workbook(workbook_id, form_id):
    try:
        form_id = int(form_id)
    except (TypeError, ValueError):
        raise ValueError("A valid sheet is required.")

    row = (
        db.session.query(WorkbookForm, Form)
        .join(Form, Form.id == WorkbookForm.form_id)
        .filter(
            WorkbookForm.workbook_id == workbook_id,
            WorkbookForm.form_id == form_id,
            Form.is_deleted == False,
            Form.current_version_id.is_not(None),
        )
        .first()
    )
    if not row:
        raise ValueError("Selected sheet is not attached to this workbook.")
    return row


def _user_workbook_for_site_form(user_id, site_id, form_id):
    return (
        db.session.query(Workbook)
        .join(WorkbookForm, WorkbookForm.workbook_id == Workbook.id)
        .join(WorkbookSite, WorkbookSite.workbook_id == Workbook.id)
        .join(
            WorkbookSiteSubmitter,
            (WorkbookSiteSubmitter.workbook_id == Workbook.id)
            & (WorkbookSiteSubmitter.site_id == WorkbookSite.site_id),
        )
        .filter(
            WorkbookForm.form_id == form_id,
            WorkbookSite.site_id == site_id,
            WorkbookSiteSubmitter.user_id == user_id,
            Workbook.is_active == True,
            db.func.lower(Workbook.status).in_(LIVE_WORKBOOK_STATUSES),
        )
        .order_by(Workbook.name.asc(), Workbook.id.asc())
        .first()
    )


def _is_form_assigned_to_site(form_id, site_id):
    """
    Returns True if this form belongs to an active workbook
    that is assigned to the given site via WorkbookSite.
    WorkbookSite is the authoritative source for site eligibility.
    """
    row = (
        db.session.query(WorkbookForm.id)
        .join(Workbook, Workbook.id == WorkbookForm.workbook_id)
        .join(WorkbookSite, WorkbookSite.workbook_id == Workbook.id)
        .filter(
            WorkbookForm.form_id == form_id,
            WorkbookSite.site_id == site_id,
            Workbook.is_active == True,
        )
        .first()
    )
    return row is not None


def _get_user_workbook_site_ids(user_id):
    rows = (
        db.session.query(WorkbookSiteSubmitter.site_id)
        .join(Workbook, Workbook.id == WorkbookSiteSubmitter.workbook_id)
        .filter(
            WorkbookSiteSubmitter.user_id == user_id,
            Workbook.is_active == True,
        )
        .distinct()
        .all()
    )
    return {row.site_id for row in rows}


def _user_has_workbook_submitter_assignments(user_id):
    return (
        db.session.query(WorkbookSiteSubmitter.id)
        .join(Workbook, Workbook.id == WorkbookSiteSubmitter.workbook_id)
        .filter(
            WorkbookSiteSubmitter.user_id == user_id,
            Workbook.is_active == True,
        )
        .first()
    ) is not None


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
# Status of a calculated field's most recent evaluation, independent of cell_state.
CALC_STATUS_OK = "ok"
CALC_STATUS_ERROR = "error"
CALC_STATUS_PENDING = "pending"
NON_MONTHLY_LAYOUT_TYPES = {"annual_table", "reference_table"}
EDITABLE_WORKBOOK_VALUE_FREQUENCIES = {"annual"}


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


def _looks_like_internal_code(value):
    text = (value or "").strip()
    if not text:
        return True
    normalized = re.sub(r"[\s_-]+", "", text).lower()
    if not normalized:
        return True
    if re.fullmatch(r"[a-z]{1,4}\d+[a-z]*(test)?", normalized):
        return True
    if re.fullmatch(r"[a-z]*\d+[a-z]*", normalized) and len(normalized) <= 12:
        return True
    if re.fullmatch(r"[a-z]{1,4}", normalized) and text == text.lower():
        return True
    words = re.findall(r"[A-Za-z]+", text)
    meaningful_words = [word for word in words if len(word) > 2 and word.lower() != "test"]
    return bool(re.search(r"\d", text)) and not meaningful_words


def human_sheet_label(form):
    if not form:
        return "Untitled Sheet"

    metadata = _parse_form_metadata(form)
    candidates = [
        metadata.get("display_name"),
        metadata.get("title"),
        metadata.get("sheet_name"),
        metadata.get("sheet_label"),
        metadata.get("label"),
        form.name,
    ]
    form_code = (form.code or "").strip().lower()

    for candidate in candidates:
        label = (candidate or "").strip()
        if not label:
            continue
        if form_code and label.lower() == form_code:
            continue
        if not _looks_like_internal_code(label):
            return label

    for section in sorted(
        [section for section in getattr(form, "sections", []) if not section.is_deleted],
        key=lambda section: (section.display_order, section.id),
    ):
        label = (section.name or "").strip()
        if label and not _looks_like_internal_code(label):
            return label

    if form.code:
        return form.code.strip()
    if form.name:
        return form.name.strip()
    return "Untitled Sheet"


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


def _published_forms_for_site_via_workbook(site_id):
    """
    Returns published forms assigned to this site via WorkbookSite.
    This is the new authoritative lookup replacing form.description["sites"].
    Returns list of (form, metadata) tuples for compatibility.
    """
    rows = (
        db.session.query(Form)
        .join(WorkbookForm, WorkbookForm.form_id == Form.id)
        .join(Workbook, Workbook.id == WorkbookForm.workbook_id)
        .join(WorkbookSite, WorkbookSite.workbook_id == Workbook.id)
        .filter(
            WorkbookSite.site_id == site_id,
            Workbook.is_active == True,
            Form.is_deleted == False,
            Form.current_version_id.is_not(None),
        )
        .order_by(Form.name.asc(), Form.id.asc())
        .all()
    )
    result = []
    for form in rows:
        metadata = _parse_form_metadata(form)
        result.append((form, metadata))
    return result


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
            "section_id": field_version.section_id,
            "frequency": field_version.frequency or "monthly",
        })
    return fields


def _sections_payload(form):
    from app.modules.FORMBLD.model import FormSection

    sections_query = (
        FormSection.query.filter_by(form_id=form.id, is_deleted=False)
        .order_by(FormSection.display_order.asc(), FormSection.id.asc())
        .all()
    )
    return [{
        "id": section.id,
        "name": section.name,
        "code": section.code,
        "layout_type": section.layout_type,
        "display_order": section.display_order,
        "description": section.description,
    } for section in sections_query]


def _section_by_id(sections):
    return {section["id"]: section for section in sections or []}


def _normalized_frequency(value):
    return (value or "monthly").strip().lower()


def _normalized_layout_type(value):
    return (value or "monthly_table").strip().lower()


def _normalized_field_type(value):
    return (value or "").strip().lower()


def is_sheet_result_field(field):
    config = field.get("field_config") or {}
    return (
        _normalized_field_type(field.get("field_type")) == "calculated"
        and (
            config.get("field_scope") == "annual_result"
            or config.get("result_role") in ("aggregate_result", "formula_result")
            or config.get("display_region") in ("below_monthly_table", "under_input_column")
        )
    )


def is_non_monthly_field(field, sections):
    if is_sheet_result_field(field):
        return True
    if _normalized_frequency(field.get("frequency")) in ("annual", "static"):
        return True
    section = _section_by_id(sections).get(field.get("section_id"))
    return bool(section and _normalized_layout_type(section.get("layout_type")) in NON_MONTHLY_LAYOUT_TYPES)


def monthly_table_fields(fields, sections):
    """Fields that belong in the monthly grid and SUM_MONTHS operand series."""
    return [field for field in fields if not is_non_monthly_field(field, sections)]


def is_editable_workbook_field(field, sections):
    section = _section_by_id(sections).get(field.get("section_id"))
    if section and _normalized_layout_type(section.get("layout_type")) == "reference_table":
        return False
    if _normalized_frequency(field.get("frequency")) not in EDITABLE_WORKBOOK_VALUE_FREQUENCIES:
        return False
    if _normalized_field_type(field.get("field_type")) in ("calculated", "file"):
        return False
    return True


def _value_has_content(raw_value):
    if isinstance(raw_value, dict):
        return any(item not in (None, "") for item in raw_value.values())
    if isinstance(raw_value, list):
        return len(raw_value) > 0
    return raw_value not in (None, "")


def _coerce_numeric_value(raw_value):
    if raw_value in (None, ""):
        return None
    try:
        return Decimal(str(raw_value))
    except (InvalidOperation, ValueError):
        return None


def _workbook_value_payload(value):
    if not value:
        return {
            "workbook_value_id": None,
            "raw_value": None,
            "calculated_value": None,
            "cell_state": CELL_STATE_BLANK_EDITABLE,
            "is_locked": False,
            "remark": None,
        }
    raw_value = value.value_json if value.value_json is not None else value.value_text
    return {
        "workbook_value_id": value.id,
        "raw_value": raw_value,
        "calculated_value": float(value.numeric_value) if value.numeric_value is not None else None,
        "cell_state": value.cell_state,
        "is_locked": value.is_locked,
        "remark": value.remark,
    }


def workbook_values_payload(site_id, form_id, fy_start_year, fields):
    field_version_ids = [
        field["field_version_id"]
        for field in fields
        if field.get("field_version_id")
    ]
    if not field_version_ids:
        return {}

    values = (
        WorkbookFieldValue.query.filter(
            WorkbookFieldValue.site_id == site_id,
            WorkbookFieldValue.form_id == form_id,
            WorkbookFieldValue.fy_start_year == fy_start_year,
            WorkbookFieldValue.field_version_id.in_(field_version_ids),
            WorkbookFieldValue.is_deleted == False,
        )
        .all()
    )
    values_by_version = {value.field_version_id: value for value in values}
    return {
        field["field_code"]: _workbook_value_payload(values_by_version.get(field["field_version_id"]))
        for field in fields
        if field.get("field_version_id")
    }


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


def _row_editability(period, submission, can_edit_monthly):
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
    if not can_edit_monthly:
        return {
            "state": "disabled",
            "editable": False,
            "reason": "You do not have permission to edit submissions for this site.",
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
        return {"sites": [], "forms_by_site": {}, "workbooks_by_site": {}}

    workbook_site_ids = _get_user_workbook_site_ids(user_id)
    site_ids = site_ids & workbook_site_ids

    if not site_ids:
        return {"sites": [], "forms_by_site": {}, "workbooks_by_site": {}}

    sites = Site.query.filter(
        Site.id.in_(site_ids),
        Site.is_deleted == False,
    ).order_by(Site.name.asc(), Site.id.asc()).all()

    forms_by_site = {}
    workbooks_by_site = {}
    for site in sites:
        workbook_rows = (
            db.session.query(Workbook)
            .join(WorkbookSite, WorkbookSite.workbook_id == Workbook.id)
            .join(
                WorkbookSiteSubmitter,
                (WorkbookSiteSubmitter.workbook_id == Workbook.id)
                & (WorkbookSiteSubmitter.site_id == WorkbookSite.site_id),
            )
            .filter(
                WorkbookSite.site_id == site.id,
                WorkbookSiteSubmitter.user_id == user_id,
                Workbook.is_active == True,
                db.func.lower(Workbook.status).in_(LIVE_WORKBOOK_STATUSES),
            )
            .order_by(Workbook.name.asc(), Workbook.id.asc())
            .all()
        )
        site_workbooks = []
        legacy_forms = []
        for workbook in workbook_rows:
            sheets = [
                _workbook_sheet_payload(workbook_form, form)
                for workbook_form, form in _workbook_sheet_rows(workbook.id)
            ]
            if not sheets:
                continue
            site_workbooks.append({
                "id": workbook.id,
                "workbook_id": workbook.id,
                "name": workbook.name,
                "code": workbook.code,
                "sheet_count": len(sheets),
                "sheets": sheets,
            })
            legacy_forms.extend(sheets)

        workbooks_by_site[str(site.id)] = site_workbooks
        forms_by_site[str(site.id)] = legacy_forms

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
        "workbooks_by_site": workbooks_by_site,
    }


def _compute_preview_calculated_values(submissions, fields):
    """
    For a list of submissions (all for the same form), compute preview values
    for calculated fields using currently saved raw input values. Runs the same
    3-pass formula evaluation as autosave but read-only — does not persist anything.
    Returns {submission_id: {field_code: float_value}} only for fields that could
    be evaluated; fields with missing inputs are absent from the inner dict.
    """
    calc_fields = [
        f for f in fields
        if f.get("field_type") == "calculated"
        and (f.get("field_config") or {}).get("formula_version_id")
    ]
    if not calc_fields:
        return {}

    sub_ids = [s.id for s in submissions if s]
    if not sub_ids:
        return {}

    fv_ids = list({f["field_config"]["formula_version_id"] for f in calc_fields})
    formula_versions = {
        fv.id: fv
        for fv in FormulaVersion.query.filter(FormulaVersion.id.in_(fv_ids)).all()
    }

    value_set_snapshot = get_approved_valsets_snapshot()

    all_svs = SubmissionValue.query.filter(
        SubmissionValue.submission_id.in_(sub_ids)
    ).all()
    id_to_code = {f["field_id"]: f["field_code"] for f in fields}
    svs_by_sub = {}
    for sv in all_svs:
        svs_by_sub.setdefault(sv.submission_id, []).append(sv)

    result = {}
    for sub in submissions:
        if not sub:
            continue
        field_values = {}
        for sv in svs_by_sub.get(sub.id, []):
            code = id_to_code.get(sv.field_id)
            if code:
                if sv.calculated_value is not None:
                    field_values[code] = float(sv.calculated_value)
                elif sv.raw_value is not None:
                    field_values[code] = sv.raw_value

        computed = {}
        for _pass in range(3):
            for f in calc_fields:
                code = f["field_code"]
                fv = formula_versions.get(f["field_config"]["formula_version_id"])
                if not fv:
                    continue
                try:
                    computed_val = evaluate_formula(fv.expression, field_values, value_set_snapshot)
                    decimals = f.get("field_config", {}).get("round_off_decimals", 3)
                    try:
                        decimals = int(decimals)
                        if not (1 <= decimals <= 9):
                            decimals = 3
                    except (ValueError, TypeError):
                        decimals = 3
                    if computed_val is not None:
                        try:
                            computed_val = round(float(computed_val), decimals)
                        except (ValueError, TypeError):
                            pass
                    computed[code] = computed_val
                    field_values[code] = computed_val
                except Exception:
                    pass

        result[sub.id] = computed

    return result


def _coerce_sheet_result_number(value):
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        if value.get("calculated_value") not in (None, ""):
            value = value.get("calculated_value")
        elif value.get("raw_value") not in (None, ""):
            value = value.get("raw_value")
        else:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _monthly_series_for_results(rows, monthly_fields):
    series = {}
    labels = {}
    for field in monthly_fields:
        code = field.get("field_code")
        if not code or _normalized_field_type(field.get("field_type")) == "file":
            continue
        if _normalized_frequency(field.get("frequency")) in ("annual", "static"):
            continue
        values = []
        missing_labels = []
        for row in rows:
            raw_value = (row.get("values") or {}).get(code)
            coerced = _coerce_sheet_result_number(raw_value)
            values.append(coerced)
            if coerced is None:
                missing_labels.append(row.get("label") or row.get("period_label") or "a month")
        series[code] = values
        labels[code] = missing_labels
    return series, labels


def _compose_sheet_results(result_fields, monthly_fields, rows):
    if not result_fields:
        return []

    value_set_snapshot = get_approved_valsets_snapshot()
    monthly_series, missing_by_code = _monthly_series_for_results(rows, monthly_fields)
    result_values = {}
    results_by_code = {}

    formula_version_ids = [
        (field.get("field_config") or {}).get("formula_version_id")
        for field in result_fields
        if (field.get("field_config") or {}).get("formula_version_id")
    ]
    formula_versions = {
        fv.id: fv
        for fv in FormulaVersion.query.filter(FormulaVersion.id.in_(formula_version_ids or [0])).all()
    }

    for _pass in range(3):
        for field in result_fields:
            code = field["field_code"]
            config = field.get("field_config") or {}
            formula_version_id = config.get("formula_version_id")
            previous = results_by_code.get(code)
            if previous and previous.get("status") == "calculated":
                continue

            if not formula_version_id:
                results_by_code[code] = {
                    "status": "not_configured",
                    "message": "Formula is not configured.",
                    "source_field_codes": [],
                }
                continue

            formula_version = formula_versions.get(formula_version_id)
            if not formula_version:
                results_by_code[code] = {
                    "status": "not_configured",
                    "message": "Formula version not found.",
                    "source_field_codes": [],
                }
                continue

            aggregate_names = aggregate_operand_names(formula_version.expression)
            missing_messages = []
            context_values = dict(result_values)

            for name in aggregate_names:
                if name not in monthly_series:
                    missing_messages.append(f"Monthly field '{name}' is not available in this sheet.")
                    continue
                missing_months = missing_by_code.get(name) or []
                if config.get("blank_policy", "strict") == "strict" and missing_months:
                    preview = ", ".join(missing_months[:3])
                    suffix = "..." if len(missing_months) > 3 else ""
                    missing_messages.append(f"{name} is missing for {preview}{suffix}.")
                context_values[name] = monthly_series[name]

            if missing_messages:
                results_by_code[code] = {
                    "status": "needs_input",
                    "message": "Cannot calculate: " + " ".join(missing_messages),
                    "source_field_codes": sorted(aggregate_names),
                }
                continue

            try:
                result = evaluate_formula(formula_version.expression, context_values, value_set_snapshot)
                decimals = config.get("round_off_decimals", 3)
                try:
                    decimals = int(decimals)
                    if not (1 <= decimals <= 9):
                        decimals = 3
                except (ValueError, TypeError):
                    decimals = 3
                if result is not None:
                    try:
                        result = round(float(result), decimals)
                    except (ValueError, TypeError):
                        pass
                result_values[code] = result
                results_by_code[code] = {
                    "status": "calculated",
                    "value": result,
                    "message": "",
                    "source_field_codes": sorted(aggregate_names),
                }
            except Exception as exc:
                results_by_code[code] = {
                    "status": "error",
                    "message": str(exc),
                    "source_field_codes": sorted(aggregate_names),
                }

    sheet_results = []
    for field in result_fields:
        config = field.get("field_config") or {}
        result = results_by_code.get(field["field_code"], {})
        value = result.get("value")
        source_field_codes = result.get("source_field_codes")
        if source_field_codes is None:
            formula_version_id = config.get("formula_version_id")
            formula_version = formula_versions.get(formula_version_id) if formula_version_id else None
            source_field_codes = (
                sorted(aggregate_operand_names(formula_version.expression))
                if formula_version
                else []
            )
        sheet_results.append({
            "field_id": field["field_id"],
            "field_code": field["field_code"],
            "label": field["field_name"],
            "value": value,
            "unit": config.get("unit") or field.get("unit") or "",
            "status": result.get("status") or "error",
            "message": result.get("message") or "",
            "source_field_codes": source_field_codes,
            "display_region": config.get("display_region") or "under_input_column",
        })
    return sheet_results


def compose_annual_workbook_data(user_id, site_id, workbook_id, fy_start_year, selected_form_id=None):
    try:
        site_id = int(site_id)
        workbook_id = int(workbook_id)
        fy_start_year = int(fy_start_year)
    except (TypeError, ValueError):
        raise ValueError("A valid site, workbook, and financial year are required.")

    workbook, site = _require_workbook_runtime_access(user_id, workbook_id, site_id)
    sheet_rows = _workbook_sheet_rows(workbook.id)
    if not sheet_rows:
        raise ValueError("This workbook has no published sheets.")

    sheet_payloads = [
        _workbook_sheet_payload(workbook_form, sheet_form)
        for workbook_form, sheet_form in sheet_rows
    ]
    selected_id = int(selected_form_id) if selected_form_id else sheet_payloads[0]["id"]
    workbook_form, form = _require_form_in_workbook(workbook.id, selected_id)

    fields = _field_payload(form.current_version_id)
    sheet_result_fields = [field for field in fields if is_sheet_result_field(field)]
    sections = _sections_payload(form)
    monthly_fields = monthly_table_fields(fields, sections)
    months = _fy_months(fy_start_year)
    can_edit_monthly = (
        has_permission(user_id, "submission", "edit", scope_site_id=site_id)
        or has_permission(user_id, "submission", "create", scope_site_id=site_id)
        or has_permission(user_id, "submission", "submit", scope_site_id=site_id)
    )

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
        Submission.form_id == form.id,
        Submission.is_deleted == False,
        Submission.reporting_period_id.in_([period.id for period in periods] or [0]),
    ).all()
    submission_by_period = {
        submission.reporting_period_id: submission
        for submission in submissions
    }

    calc_preview = _compute_preview_calculated_values(list(submissions), monthly_fields)

    rows = []
    for item in months:
        period = period_by_key.get((item["year"], item["month"]))
        submission = submission_by_period.get(period.id) if period else None
        editability = _row_editability(period, submission, can_edit_monthly)
        values = _submission_values_payload(submission, monthly_fields)
        if submission and submission.id in calc_preview:
            for code, preview_val in calc_preview[submission.id].items():
                if preview_val is not None and values.get(code) in (None, ""):
                    values[code] = preview_val
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
            "values": values,
            "issues": submission_value_issues_by_field(submission, monthly_fields),
            "is_active_period": bool(period and period.status in ("OPEN", "REOPENED")),
        })

    sheet_results = _compose_sheet_results(sheet_result_fields, monthly_fields, rows)

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
        "workbook": {
            "id": workbook.id,
            "name": workbook.name,
            "code": workbook.code,
            "workflow_id": workbook.workflow_id,
        },
        "forms": sheet_payloads,
        "selected_form": {
            "id": form.id,
            "name": workbook_form.sheet_label or human_sheet_label(form),
            "code": form.code,
            "workflow_id": workbook.workflow_id,
        },
        "fields": monthly_fields,
        "sections": sections,
        "workbook_values": workbook_values_payload(site.id, form.id, fy_start_year, fields),
        "sheet_results": sheet_results,
        "rows": rows,
    }


def save_annual_workbook_values(user_id, site_id, workbook_id, form_id, fy_start_year, values):
    try:
        site_id = int(site_id)
        workbook_id = int(workbook_id)
        form_id = int(form_id)
        fy_start_year = int(fy_start_year)
    except (TypeError, ValueError):
        raise ValueError("A valid site, workbook, sheet, and financial year are required.")

    if not isinstance(values, dict):
        raise ValueError("Values must be submitted as an object.")

    if not (
        has_permission(user_id, "submission", "edit", scope_site_id=site_id)
        or has_permission(user_id, "submission", "create", scope_site_id=site_id)
        or has_permission(user_id, "submission", "submit", scope_site_id=site_id)
    ):
        raise ValueError("Permission denied: You cannot edit annual workbook values for this site.")

    workbook, _site = _require_workbook_runtime_access(user_id, workbook_id, site_id)
    _workbook_form, form = _require_form_in_workbook(workbook.id, form_id)

    months = _fy_months(fy_start_year)
    open_period_exists = ReportingPeriod.query.filter(
        ReportingPeriod.site_id == site_id,
        ReportingPeriod.is_deleted == False,
        tuple_(ReportingPeriod.year, ReportingPeriod.month).in_(
            [(item["year"], item["month"]) for item in months]
        ),
        ReportingPeriod.status.in_(EDITABLE_PERIOD_STATUSES),
    ).first() is not None
    if not open_period_exists:
        raise ValueError("At least one reporting period in this financial year must be open for annual value entry.")

    fields = _field_payload(form.current_version_id)
    sections = _sections_payload(form)
    editable_fields = {
        field["field_code"]: field
        for field in fields
        if is_editable_workbook_field(field, sections)
    }

    saved = {}
    for field_code, raw_value in values.items():
        field = editable_fields.get(field_code)
        if not field:
            continue

        value_row = WorkbookFieldValue.query.filter_by(
            site_id=site_id,
            form_id=form_id,
            field_version_id=field["field_version_id"],
            fy_start_year=fy_start_year,
            is_deleted=False,
        ).first()
        if not value_row:
            value_row = WorkbookFieldValue(
                site_id=site_id,
                form_id=form_id,
                field_id=field["field_id"],
                field_version_id=field["field_version_id"],
                fy_start_year=fy_start_year,
                created_by=user_id,
            )
            db.session.add(value_row)

        value_row.value_text = None
        value_row.numeric_value = None
        value_row.value_json = None
        if isinstance(raw_value, (dict, list)):
            value_row.value_json = raw_value
        elif raw_value not in (None, ""):
            value_row.value_text = str(raw_value)
            if _normalized_field_type(field.get("field_type")) in ("integer", "number", "decimal", "float", "numeric"):
                value_row.numeric_value = _coerce_numeric_value(raw_value)

        set_state = CELL_STATE_DRAFT_FILLED if _value_has_content(raw_value) else CELL_STATE_BLANK_EDITABLE
        value_row.cell_state = set_state
        value_row.is_locked = False
        value_row.updated_by = user_id
        saved[field_code] = value_row

    db.session.flush()
    payload = workbook_values_payload(site_id, form_id, fy_start_year, fields)
    return {
        "workbook_values": payload,
        "saved_fields": list(saved.keys()),
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
    sections = _sections_payload(form)
    monthly_fields = monthly_table_fields(fields, sections)
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
            "values": submission_values_review_payload(submission, monthly_fields),
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
            "name": human_sheet_label(form),
            "code": form.code,
        },
        "fields": monthly_fields,
        "sections": sections,
        "workbook_values": workbook_values_payload(site.id, form.id, fy_start_year, fields),
        "rows": rows,
    }


def compose_calculation_results(site_id, workbook_id, fy_start_year, user_id):
    """
    Computes read-only calculated field results across all forms for a site and FY.
    Provides preview vs reportable calculation separation, handling missing values safely.
    """
    try:
        site_id = int(site_id)
        workbook_id = int(workbook_id)
        fy_start_year = int(fy_start_year)
    except (TypeError, ValueError):
        raise ValueError("A valid site, workbook, and financial year are required.")

    workbook, site = _require_workbook_runtime_access(user_id, workbook_id, site_id)
    assigned = _published_forms_for_workbook(workbook.id)
    sheet_payloads = [
        _workbook_sheet_payload(workbook_form, sheet_form)
        for workbook_form, sheet_form in _workbook_sheet_rows(workbook.id)
    ]
    if not assigned:
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
            "workbook": {
                "id": workbook.id,
                "name": workbook.name,
                "code": workbook.code,
                "workflow_id": workbook.workflow_id,
            },
            "forms": sheet_payloads,
            "selected_form": {
                "id": "calc_results",
                "name": "Calculation Results",
                "code": "calc_results",
                "workflow_id": None,
            },
            "fields": [],
            "sections": [],
            "rows": []
        }

    from app.modules.FORMBLD.service import get_form_version_fields
    from app.modules.FORMBLD.model import Field
    from app.modules.FRMULA.model import FormulaVersion

    calculated_fields = []
    field_code_to_name = {}
    form_ids = [form.id for form, _ in assigned]

    # Map all fields in assigned forms to translate dependency codes to names
    all_fields = Field.query.filter(Field.form_id.in_(form_ids or [0]), Field.is_deleted == False).all()
    field_id_to_code = {f.id: f.field_code for f in all_fields}
    form_map = {form.id: human_sheet_label(form) for form, _ in assigned}
    field_code_to_form_name = {f.field_code: form_map.get(f.form_id, "Unknown Sheet") for f in all_fields}

    for form, metadata in assigned:
        fields = get_form_version_fields(form.current_version_id)
        for fv, f in fields:
            field_code_to_name[f.field_code] = fv.field_name
            if fv.field_type == "calculated" and not is_sheet_result_field({
                "field_type": fv.field_type,
                "field_config": fv.field_config or {},
            }):
                calculated_fields.append({
                    "field": f,
                    "version": fv,
                    "form": form
                })

    # Sort calculated fields by form name and field display order to keep order deterministic
    calculated_fields.sort(key=lambda item: (human_sheet_label(item["form"]).lower(), item["field"].display_order))

    # Serialize fields for workbook sheet columns
    serialized_fields = []
    for item in calculated_fields:
        serialized_fields.append({
            "id": item["field"].id,
            "field_id": item["field"].id,
            "field_version_id": item["version"].id,
            "field_code": item["field"].field_code,
            "field_name": item["version"].field_name,
            "form_name": human_sheet_label(item["form"]),
            "field_type": "calculated",
            "field_config": item["version"].field_config or {},
            "unit": item["version"].field_config.get("unit") or "" if item["version"].field_config else "",
            "display_order": item["field"].display_order,
            "form_id": item["form"].id,
        })

    value_set_snapshot = get_approved_valsets_snapshot()

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
        Submission.form_id.in_(form_ids or [0]),
        Submission.is_deleted == False,
        Submission.reporting_period_id.in_([p.id for p in periods] or [0])
    ).all()

    submission_by_period_and_form = {}
    for sub in submissions:
        submission_by_period_and_form[(sub.reporting_period_id, sub.form_id)] = sub

    sub_ids = [s.id for s in submissions]
    sub_values = SubmissionValue.query.filter(
        SubmissionValue.submission_id.in_(sub_ids or [0])
    ).all() if sub_ids else []

    values_by_sub_and_code = {}
    for val in sub_values:
        code = field_id_to_code.get(val.field_id)
        if code:
            values_by_sub_and_code.setdefault(val.submission_id, {})[code] = val

    rows = []
    for item in months:
        period = period_by_key.get((item["year"], item["month"]))
        row_values = {}

        if not period:
            for field_info in calculated_fields:
                code = field_info["field"].field_code
                row_values[code] = {
                    "calculated_value": None,
                    "preview_value": None,
                    "reportable_value": None,
                    "status": "missing_input",
                    "warnings": ["Reporting period not created for this month."]
                }
        else:
            preview_field_values = {}
            reportable_field_values = {}
            cell_states = {}

            # Gather all available field values for preview vs reportable
            for form, metadata in assigned:
                sub = submission_by_period_and_form.get((period.id, form.id))
                if sub:
                    sub_vals = values_by_sub_and_code.get(sub.id, {})
                    for code, val in sub_vals.items():
                        val_str = ""
                        if val.calculated_value is not None:
                            val_str = val.calculated_value
                        elif val.raw_value is not None:
                            val_str = val.raw_value

                        is_approved = (val.cell_state == "approved_locked" or sub.status == "Approved")
                        cell_states[code] = "approved_locked" if is_approved else val.cell_state

                        if val_str is not None and val_str != "":
                            preview_field_values[code] = val_str
                            if is_approved:
                                reportable_field_values[code] = val_str

            # Perform 3 calculation passes to resolve inter-calculated field dependencies
            for pass_num in range(3):
                for field_info in calculated_fields:
                    f = field_info["field"]
                    fv = field_info["version"]
                    code = f.field_code

                    formula_ver_id = fv.field_config.get("formula_version_id")
                    if not formula_ver_id:
                        row_values[code] = {
                            "calculated_value": None,
                            "preview_value": None,
                            "reportable_value": None,
                            "status": "not_configured",
                            "warnings": ["Formula not configured."]
                        }
                        continue

                    formula_version = FormulaVersion.query.get(formula_ver_id)
                    if not formula_version:
                        row_values[code] = {
                            "calculated_value": None,
                            "preview_value": None,
                            "reportable_value": None,
                            "status": "not_configured",
                            "warnings": ["Formula version not found."]
                        }
                        continue

                    tokens = list((formula_version.tokens or {}).keys())

                    # Check missing preview inputs
                    missing_preview_deps = []
                    for t in tokens:
                        if t not in value_set_snapshot and t not in preview_field_values:
                            missing_preview_deps.append(t)

                    # Check missing/unapproved reportable inputs
                    missing_reportable_deps = []
                    unapproved_reportable_deps = []
                    for t in tokens:
                        if t not in value_set_snapshot:
                            if t not in preview_field_values:
                                missing_reportable_deps.append(t)
                            elif t not in reportable_field_values:
                                unapproved_reportable_deps.append(t)

                    preview_val = None
                    preview_status = "preview_only"
                    preview_warnings = []

                    if missing_preview_deps:
                        preview_status = "missing_input"
                        for dep in missing_preview_deps:
                            form_name = field_code_to_form_name.get(dep)
                            if form_name and form_name != human_sheet_label(field_info["form"]):
                                preview_warnings.append(f"Cannot calculate yet — [{form_name}] value is missing")
                            else:
                                dep_name = field_code_to_name.get(dep, dep)
                                preview_warnings.append(f"Cannot calculate — waiting for {dep_name}.")
                    else:
                        try:
                            preview_val = evaluate_formula(formula_version.expression, preview_field_values, value_set_snapshot)

                            # Check if preview relies on unapproved values
                            unapproved_inputs = [t for t in tokens if t not in value_set_snapshot and cell_states.get(t) != "approved_locked"]
                            if unapproved_inputs:
                                preview_status = "preview_only"
                                for dep in unapproved_inputs:
                                    dep_name = field_code_to_name.get(dep, dep)
                                    preview_warnings.append(f"Input {dep_name} is submitted but not approved, preview only.")
                            else:
                                preview_status = "calculable"
                        except Exception as exc:
                            preview_status = "evaluation_error"
                            preview_warnings.append(f"Evaluation error: {str(exc)}")

                    reportable_val = None
                    reportable_status = "calculable"
                    reportable_warnings = []

                    if missing_reportable_deps:
                        reportable_status = "missing_input"
                        for dep in missing_reportable_deps:
                            form_name = field_code_to_form_name.get(dep)
                            if form_name and form_name != human_sheet_label(field_info["form"]):
                                reportable_warnings.append(f"Cannot calculate yet — [{form_name}] value is missing")
                            else:
                                dep_name = field_code_to_name.get(dep, dep)
                                reportable_warnings.append(f"Cannot calculate — waiting for {dep_name}.")
                    elif unapproved_reportable_deps:
                        reportable_status = "pending_approval"
                        for dep in unapproved_reportable_deps:
                            dep_name = field_code_to_name.get(dep, dep)
                            reportable_warnings.append(f"Input {dep_name} is not approved, preview only.")
                    else:
                        try:
                            reportable_val = evaluate_formula(formula_version.expression, reportable_field_values, value_set_snapshot)
                        except Exception as exc:
                            reportable_status = "evaluation_error"
                            reportable_warnings.append(f"Evaluation error: {str(exc)}")

                    final_status = "calculable" if reportable_status == "calculable" else preview_status
                    if final_status == "preview_only" and reportable_status == "pending_approval":
                        final_status = "preview_only"
                    elif final_status == "missing_input":
                        final_status = "missing_input"

                    final_warnings = list(set(preview_warnings + reportable_warnings))

                    row_values[code] = {
                        "calculated_value": reportable_val if reportable_status == "calculable" else preview_val,
                        "preview_value": preview_val,
                        "reportable_value": reportable_val,
                        "status": final_status,
                        "warnings": final_warnings
                    }

                    if preview_val is not None:
                        preview_field_values[code] = preview_val
                    if reportable_val is not None:
                        reportable_field_values[code] = reportable_val

            # Round final display values in row_values
            for code, r_info in row_values.items():
                f_info = next((fi for fi in calculated_fields if fi["field"].field_code == code), None)
                if f_info:
                    fv = f_info["version"]
                    decimals = fv.field_config.get("round_off_decimals", 3)
                    try:
                        decimals = int(decimals)
                        if not (1 <= decimals <= 9):
                            decimals = 3
                    except (ValueError, TypeError):
                        decimals = 3
                    for key in ["calculated_value", "preview_value", "reportable_value"]:
                        val = r_info.get(key)
                        if val is not None:
                            try:
                                r_info[key] = round(float(val), decimals)
                            except (ValueError, TypeError):
                                pass

        rows.append({
            **item,
            "period_id": period.id if period else None,
            "period_status": period.status if period else None,
            "submission_id": None,
            "submission_status": None,
            "is_locked": True,
            "last_saved": None,
            "editability": {
                "state": "read_only",
                "editable": False,
                "reason": "Calculation Results are read-only output."
            },
            "values": row_values,
            "issues": {},
            "is_active_period": bool(period and period.status in ("OPEN", "REOPENED")),
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
        "workbook": {
            "id": workbook.id,
            "name": workbook.name,
            "code": workbook.code,
            "workflow_id": workbook.workflow_id,
        },
        "forms": sheet_payloads,
        "selected_form": {
            "id": "calc_results",
            "name": "Calculation Results",
            "code": "calc_results",
            "workflow_id": None,
        },
        "fields": serialized_fields,
        "sections": [],
        "rows": rows,
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
    else:
        active_sites = Site.query.filter(Site.id.in_(allowed_site_ids), Site.is_deleted == False).all()

    workbook_site_ids = _get_user_workbook_site_ids(user_id)
    allowed_site_ids = allowed_site_ids & workbook_site_ids
    active_sites = [s for s in active_sites if s.id in allowed_site_ids]

    sites_map = {site.id: site for site in active_sites}

    # 2. Get all published forms
    published_forms = Form.query.filter_by(is_deleted=False).filter(Form.current_version_id.is_not(None)).all()

    # Check form applicability per site using WorkbookSite as authoritative source
    applicable_forms_by_site = {site_id: [] for site_id in allowed_site_ids}
    form_map = {}

    for f in published_forms:
        form_map[f.id] = f
    for site_id in allowed_site_ids:
        workbook_rows = (
            db.session.query(Workbook)
            .join(WorkbookSite, WorkbookSite.workbook_id == Workbook.id)
            .join(
                WorkbookSiteSubmitter,
                (WorkbookSiteSubmitter.workbook_id == Workbook.id)
                & (WorkbookSiteSubmitter.site_id == WorkbookSite.site_id),
            )
            .filter(
                WorkbookSite.site_id == site_id,
                WorkbookSiteSubmitter.user_id == user_id,
                Workbook.is_active == True,
                db.func.lower(Workbook.status).in_(LIVE_WORKBOOK_STATUSES),
            )
            .all()
        )
        seen_forms = set()
        for workbook in workbook_rows:
            for _workbook_form, form in _workbook_sheet_rows(workbook.id):
                form_map[form.id] = form
                if form.id not in seen_forms:
                    applicable_forms_by_site[site_id].append(form)
                    seen_forms.add(form.id)

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

    def plain_submission_status(status):
        return {
            "Approved": "Approved and locked",
            "Draft": "Draft saved",
            "Changes Requested": "Needs correction",
            "Rejected": "Sent back",
            "Resubmitted": "Sent again for review",
            "Under Review": "Under review",
            "Submitted": "Submitted",
        }.get(status, status or "Unknown")

    # Track submission combos (site_id, form_id, reporting_period_id)
    submitted_combos = set()
    
    for sub in submissions:
        site = sites_map.get(sub.site_id)
        form = form_map.get(sub.form_id)
        period = ReportingPeriod.query.get(sub.reporting_period_id)
        
        if not site or not form or not period:
            continue
        workbook = _user_workbook_for_site_form(user_id, sub.site_id, sub.form_id)
        if not workbook:
            continue
            
        submitted_combos.add((sub.site_id, sub.form_id, sub.reporting_period_id))
        
        period_label = format_period_label(period.year, period.month)
        
        item = {
            "submission_id": sub.id,
            "package_id": sub.package_id,
            "site_id": sub.site_id,
            "workbook_id": workbook.id,
            "workbook_name": workbook.name,
            "form_name": human_sheet_label(form),
            "form_id": sub.form_id,
            "form_code": form.code,
            "site_name": site.name,
            "reporting_period_id": sub.reporting_period_id,
            "period_label": period_label,
            "year": period.year,
            "month": period.month,
            "status": sub.status,
            "status_text": plain_submission_status(sub.status),
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
                workbook = _user_workbook_for_site_form(user_id, site_id, form.id)
                if not workbook:
                    continue
                combo = (site_id, form.id, period.id)
                if combo not in submitted_combos:
                    not_started.append({
                        "workbook_id": workbook.id,
                        "workbook_name": workbook.name,
                        "form_id": form.id,
                        "form_name": human_sheet_label(form),
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

def create_draft_submission(site_id, form_id, reporting_period_id, user_id, workbook_id=None):
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
        
    workbook = None

    # 3. Form check
    form = Form.query.filter_by(id=form_id, is_deleted=False).first()
    if not form or not form.current_version_id:
        raise ValueError("Published form version not found.")

    if workbook_id:
        workbook, _site = _require_workbook_runtime_access(user_id, workbook_id, site_id)
        _require_form_in_workbook(workbook.id, form_id)
    elif not _is_form_assigned_to_site(form_id, site_id):
        raise ValueError(
            "This form is not assigned to the selected site. "
            "Check the workbook's Sites tab."
        )

    # 4. Workflow assignment
    wf_id = workbook.workflow_id if workbook else _get_workflow_id_for_form(form_id)
    if not wf_id:
        raise ValueError(
            "This form is not ready for submission: no approval path has been assigned to its workbook."
        )

    workflow = Workflow.query.filter_by(id=wf_id, is_deleted=False).first()
    if not workflow or not workflow.current_version_id:
        raise ValueError(
            "This form is not ready for submission: the assigned approval path has no published version."
        )
        
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


def assign_submission_workflow_from_workbook(submission_id, workbook_id, user_id):
    """
    Ensures a submission uses the approval workflow configured on its workbook.
    Annual workbook section submission remains per-sheet; the workbook only
    supplies the shared approval chain.
    """
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        raise ValueError("Submission not found.")

    workbook, _site = _require_workbook_runtime_access(user_id, workbook_id, submission.site_id)
    _require_form_in_workbook(workbook.id, submission.form_id)
    workflow = _get_workflow_for_workbook(workbook)
    if not workflow or not workflow.current_version_id:
        raise ValueError(
            "This workbook is not ready for submission: no published approval path has been assigned."
        )

    submission.workflow_version_id = workflow.current_version_id
    submission.updated_by = user_id
    db.session.flush()
    return submission

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

def submit_monthly_workbook_package(site_id, workbook_id=None, period_id=None, year=None, month=None, user_id=None, selected_form_id=None, values=None):
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

    workbook, _site = _require_workbook_runtime_access(user_id, workbook_id, site_id)
    workflow = _get_workflow_for_workbook(workbook)
    if not workflow or not workflow.current_version_id:
        raise ValueError(
            "This workbook is not ready for submission: no published approval path has been assigned."
        )

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

    assigned_forms = [
        form for form, _metadata
        in _published_forms_for_workbook(workbook.id)
    ]
    if not assigned_forms:
        raise ValueError("No published sheets are assigned to this workbook.")

    assigned_form_ids = {form.id for form in assigned_forms}
    selected_form_id = int(selected_form_id) if selected_form_id else None
    if selected_form_id and selected_form_id not in assigned_form_ids:
        raise ValueError("Selected sheet is not assigned to this workbook.")

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
                submission = create_draft_submission(site_id, form.id, period.id, user_id, workbook_id=workbook.id)
                created_from_payload = True
            except DuplicateSubmissionError as exc:
                submission = Submission.query.get(exc.existing_id)

        if not submission:
            skipped.append({
                "form_id": form.id,
                "form_name": human_sheet_label(form),
                "reason": "No draft or filled values to submit.",
            })
            continue

        if submission.is_locked or submission.status == "Approved":
            skipped.append({
                "form_id": form.id,
                "form_name": human_sheet_label(form),
                "submission_id": submission.id,
                "reason": "Already approved or locked.",
            })
            continue

        if selected_form_id == form.id and values is not None and submission.status in EDITABLE_SUBMISSION_STATUSES:
            autosave_submission_values(submission.id, values or {}, user_id)
        elif submission.status in EDITABLE_SUBMISSION_STATUSES:
            autosave_submission_values(submission.id, {}, user_id)

        submission.package_id = package.id
        if submission.status in EDITABLE_SUBMISSION_STATUSES:
            submission.workflow_version_id = workflow.current_version_id
        submission.updated_by = user_id

        needs_recalc_review = False
        if submission.status in EDITABLE_SUBMISSION_STATUSES:
            try:
                submit_result = submit_submission(submission.id, user_id)
                needs_recalc_review = submit_result["needs_recalc_review"]
                submitted_count += 1
            except SubmissionValidationError as exc:
                errors.append({
                    "form_id": form.id,
                    "form_name": human_sheet_label(form),
                    "submission_id": submission.id,
                    "error": str(exc),
                    "validation_errors": exc.errors,
                })
                continue
            except ValueError as exc:
                errors.append({
                    "form_id": form.id,
                    "form_name": human_sheet_label(form),
                    "submission_id": submission.id,
                    "error": str(exc),
                })
                continue

        included.append({
            "form_id": form.id,
            "form_name": human_sheet_label(form),
            "submission_id": submission.id,
            "status": submission.status,
            "created": created_from_payload,
            "needs_recalc_review": needs_recalc_review,
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

def _build_fields_map(fields):
    fields_map = {}
    for fv, f in fields:
        fields_map[f.field_code] = {
            "field_id": f.id,
            "field_version_id": fv.id,
            "field_type": fv.field_type,
            "field_config": fv.field_config or {},
            "frequency": fv.frequency or "monthly",
            "section_id": fv.section_id,
        }
    return fields_map


def recalculate_submission_formulas(submission, fields_map, user_id):
    """
    Recomputes every calculated field for a submission from currently persisted
    raw values, and records an explicit calc_status ("ok" | "error" | "pending")
    per field rather than collapsing every non-result into a bare None.

    Shared by autosave (client-triggered, after raw values are saved) and
    submit_submission (server-authoritative recheck at submit time), so the
    persisted calculated_value is never stale relative to the raw inputs on
    record, regardless of client/autosave timing.

    Returns (calculation_errors, values_by_field_id):
      - calculation_errors: {field_code: message} only for fields whose formula
        actually failed to evaluate (status "error") -- fields merely waiting on
        upstream inputs (status "pending") are not included, since that's an
        expected, non-blocking state.
      - values_by_field_id: {field_id: SubmissionValue} for every value row on
        this submission (raw and calculated), so callers that need the
        post-recalculation state don't have to re-query it.
    """
    submission_id = submission.id

    # Load all saved values to pass as inputs
    db_values = SubmissionValue.query.filter_by(submission_id=submission_id).all()
    id_to_code = {info["field_id"]: code for code, info in fields_map.items()}
    values_by_field_id = {val.field_id: val for val in db_values}

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

    period = ReportingPeriod.query.get(submission.reporting_period_id)
    if period:
        fy_start_year = period.year if period.month >= 4 else period.year - 1
        version_to_code = {
            info["field_version_id"]: code
            for code, info in fields_map.items()
            if info.get("field_version_id")
        }
        workbook_values = WorkbookFieldValue.query.filter(
            WorkbookFieldValue.site_id == submission.site_id,
            WorkbookFieldValue.form_id == submission.form_id,
            WorkbookFieldValue.fy_start_year == fy_start_year,
            WorkbookFieldValue.field_version_id.in_(list(version_to_code.keys()) or [0]),
            WorkbookFieldValue.is_deleted == False,
        ).all()
        for workbook_value in workbook_values:
            code = version_to_code.get(workbook_value.field_version_id)
            if not code or code in field_values:
                continue
            if workbook_value.numeric_value is not None:
                field_values[code] = float(workbook_value.numeric_value)
            elif workbook_value.value_text not in (None, ""):
                field_values[code] = workbook_value.value_text
            elif workbook_value.value_json is not None:
                field_values[code] = workbook_value.value_json

    # Prepare value set snapshot
    value_set_snapshot = get_approved_valsets_snapshot()

    calculation_errors = {}

    def _get_or_create_calc_row(f_id, fv_id):
        calc_row = values_by_field_id.get(f_id)
        if not calc_row:
            calc_row = SubmissionValue(
                submission_id=submission_id,
                field_id=f_id,
                field_version_id=fv_id,
                created_by=user_id,
            )
            db.session.add(calc_row)
            values_by_field_id[f_id] = calc_row
        return calc_row

    # Calculate each formula with 3 passes to resolve inter-calculated field dependencies
    for pass_num in range(3):
        for code, info in fields_map.items():
            if info["field_type"] == "calculated" and not is_sheet_result_field(info):
                f_id = info["field_id"]
                fv_id = info["field_version_id"]
                formula_ver_id = info["field_config"].get("formula_version_id")

                calc_row = _get_or_create_calc_row(f_id, fv_id)
                calc_row.raw_value = None
                calc_row.formula_eval_at = datetime.now(timezone.utc)
                calc_row.updated_by = user_id

                if not formula_ver_id:
                    calc_row.calculated_value = None
                    calc_row.calc_status = CALC_STATUS_ERROR
                    calc_row.calc_error_message = "Formula is not configured."
                    set_submission_value_state(calc_row, CELL_STATE_DRAFT_FILLED)
                    calculation_errors[code] = calc_row.calc_error_message
                    field_values[code] = None
                    continue

                formula_version = FormulaVersion.query.get(formula_ver_id)
                if not formula_version:
                    calc_row.calculated_value = None
                    calc_row.calc_status = CALC_STATUS_ERROR
                    calc_row.calc_error_message = "Formula version not found."
                    set_submission_value_state(calc_row, CELL_STATE_DRAFT_FILLED)
                    calculation_errors[code] = calc_row.calc_error_message
                    field_values[code] = None
                    continue

                calc_row.formula_version_id = formula_version.id
                token_keys = list((formula_version.tokens or {}).keys())

                # A token that isn't a known field code or value-set constant is a
                # broken formula reference (stale/renamed/deleted field), not data
                # entry in progress -- it can never resolve, so it must surface as
                # an error rather than being mistaken for "pending" forever.
                unknown_tokens = [
                    name for name in token_keys
                    if name not in fields_map and name not in value_set_snapshot
                ]
                if unknown_tokens:
                    calc_row.calculated_value = None
                    calc_row.calc_status = CALC_STATUS_ERROR
                    calc_row.calc_error_message = (
                        f"Unknown formula variable: {', '.join(sorted(unknown_tokens))}."
                    )
                    set_submission_value_state(calc_row, CELL_STATE_DRAFT_FILLED)
                    calculation_errors[code] = calc_row.calc_error_message
                    field_values[code] = None
                    continue

                missing_inputs = [
                    name for name in token_keys
                    if name not in value_set_snapshot
                    and (name not in field_values or field_values.get(name) in (None, ""))
                ]

                if missing_inputs:
                    # Referenced fields simply haven't been filled in yet -- this is
                    # expected while data entry is in progress, not a formula error.
                    calc_row.calculated_value = None
                    calc_row.calc_status = CALC_STATUS_PENDING
                    calc_row.calc_error_message = None
                    set_submission_value_state(calc_row, CELL_STATE_DRAFT_FILLED)
                    calculation_errors.pop(code, None)
                    field_values[code] = None
                    continue

                try:
                    result = evaluate_formula(formula_version.expression, field_values, value_set_snapshot)

                    calc_row.calculated_value = result
                    calc_row.calc_status = CALC_STATUS_OK
                    calc_row.calc_error_message = None
                    set_submission_value_state(calc_row, CELL_STATE_DRAFT_FILLED)

                    # Snapshot tokens and values
                    inputs_snapshot = {}
                    for key in token_keys:
                        if key in field_values:
                            inputs_snapshot[key] = field_values[key]
                        elif key in value_set_snapshot:
                            inputs_snapshot[key] = value_set_snapshot[key]
                    calc_row.formula_inputs_snapshot = inputs_snapshot

                    # Add calculated value to field_values so subsequent calculations can read it
                    field_values[code] = result

                    # Clear from errors on success
                    calculation_errors.pop(code, None)

                except Exception as e:
                    # Log evaluation error and clear previous calculation
                    calc_row.calculated_value = None
                    calc_row.calc_status = CALC_STATUS_ERROR
                    calc_row.calc_error_message = str(e)
                    calculation_errors[code] = str(e)
                    field_values[code] = None

    db.session.flush()
    return calculation_errors, values_by_field_id


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
    form = Form.query.get(submission.form_id)
    if not form:
        raise ValueError("Submission form not found.")

    form_version_id = (form.current_version_id if form.current_version_id else None) or submission.form_version_id
    fields = get_form_version_fields(form_version_id)
    fields_map = _build_fields_map(fields)

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

    calculation_errors, _ = recalculate_submission_formulas(submission, fields_map, user_id)
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

    form = Form.query.get(submission.form_id)
    if not submission.workflow_version_id:
        raise ValueError(
            "This submission cannot proceed: no approval path has been assigned to its workbook."
        )
    validate_workflow_path_for_site(submission.workflow_version_id, submission.site_id)
    first_applicable_level = find_next_applicable_level(
        submission.workflow_version_id,
        submission.site_id,
        0,
    )
    if not first_applicable_level:
        raise ValueError(
            "This workflow has no eligible reviewer path for this submission site. "
            "Please contact setup support."
        )
        
    # Get form version fields
    fields = get_form_version_fields(submission.form_version_id)
    sections = _sections_payload(form)

    # Server-side authoritative recalculation: recompute every calculated field from
    # currently persisted raw values right now, rather than trusting whatever the last
    # client autosave happened to persist. This is what actually gets validated/stored.
    fields_map = _build_fields_map(fields)
    _, values_map = recalculate_submission_formulas(submission, fields_map, user_id)

    validation_errors = {}
    calc_review_flags = {}

    for fv, f in fields:
        if is_non_monthly_field(
            {"frequency": fv.frequency, "section_id": fv.section_id},
            sections,
        ):
            continue

        config = fv.field_config or {}
        val_obj = values_map.get(f.id)
        is_calculated = fv.field_type == "calculated"

        # 1. Required field check -- only raw input fields block submission.
        # Calculated fields are derived, not entered, so their completeness is
        # tracked separately (see check 3) and never blocks the raw data submit.
        is_required = config.get("is_required") is True
        has_val = val_obj is not None and (
            (val_obj.raw_value is not None and val_obj.raw_value != "") or
            (val_obj.calculated_value is not None)
        )

        if is_required and not has_val and not is_calculated:
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

        # 3. Calculation completeness -- informational only, never blocks submission.
        # A formula error or an upstream input still being blank must not hold up
        # the raw data; instead, an "error" status is flagged for reviewer follow-up.
        if is_calculated and not is_sheet_result_field(
            {"field_type": fv.field_type, "field_config": config}
        ):
            if val_obj and val_obj.calc_status == CALC_STATUS_ERROR:
                calc_review_flags[f.field_code] = (
                    val_obj.calc_error_message or "Formula evaluation failed."
                )
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

    # A calculated field with a formula error doesn't block the raw data from being
    # submitted, but it does mean a stored number may be wrong -- flag the record so
    # it surfaces for reviewer follow-up instead of silently passing through.
    submission.needs_recalc_review = bool(calc_review_flags)
    submission.recalc_review_notes = (
        "; ".join(f"{code}: {msg}" for code, msg in calc_review_flags.items())
        if calc_review_flags else None
    )

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

    return {
        "submission": submission,
        "needs_recalc_review": submission.needs_recalc_review,
        "calc_review_fields": calc_review_flags,
    }
