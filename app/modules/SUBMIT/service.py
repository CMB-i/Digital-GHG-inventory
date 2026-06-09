import json
import calendar
from datetime import datetime, timezone

from app.database import db
from app.common.permissions import has_permission
from app.modules.ACCESS.model import AccessMatrix
from app.modules.SITEMST.model import Site
from app.modules.FORMBLD.model import Form, FormVersion, Field, FieldVersion
from app.modules.FORMBLD.service import get_form_version_fields
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.SUBMIT.model import Submission, SubmissionValue, ProofDocument
from app.modules.FRMULA.model import FormulaVersion
from app.modules.FRMULA.service import evaluate_formula
from app.modules.WFLWBLD.model import Workflow

class DuplicateSubmissionError(Exception):
    def __init__(self, existing_id):
        self.existing_id = existing_id
        super().__init__(f"Submission already exists with ID: {existing_id}")

class SubmissionValidationError(ValueError):
    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = errors  # Dict of {field_code: error_message}

def format_period_label(year, month):
    if 1 <= month <= 12:
        return f"{calendar.month_name[month]} {year}"
    return f"Month {month} {year}"

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
            "form_name": form.name,
            "form_code": form.code,
            "site_name": site.name,
            "period_label": period_label,
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
        raise ValueError("No workflow assigned to this form.")
        
    workflow = Workflow.query.filter_by(id=wf_id, is_deleted=False).first()
    if not workflow or not workflow.current_version_id:
        raise ValueError("Assigned workflow does not have a published version.")
        
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
    
    submission.status = new_status
    submission.submitted_by = user_id
    submission.submitted_at = datetime.now(timezone.utc)
    submission.last_status_changed_at = datetime.now(timezone.utc)
    submission.updated_by = user_id
    
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
