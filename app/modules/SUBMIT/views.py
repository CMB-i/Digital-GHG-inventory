import json

from flask import Blueprint, current_app, redirect, render_template, request, jsonify, send_file
from app.common.decorators import require_permission
from app.common.auth import current_user, require_login
from app.common.responses import success_response, error_response
from app.database import db
from app.common.file_storage import save_file, get_file_path
from app.modules.SUBMIT.model import Submission, SubmissionValue, ProofDocument
from app.modules.FORMBLD.model import Form, Field, FieldVersion
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.FORMBLD.service import get_form_version_fields
from app.modules.SUBMIT.service import (
    get_spoc_sheets_buckets,
    get_annual_workbook_options,
    compose_annual_workbook_data,
    save_annual_workbook_values,
    compose_calculation_results,
    create_draft_submission,
    autosave_submission_values,
    assign_submission_workflow_from_workbook,
    submit_submission,
    submit_monthly_workbook_package,
    human_sheet_label,
    set_submission_value_state,
    CELL_STATE_DRAFT_FILLED,
    DuplicateSubmissionError,
    SubmissionValidationError,
    PackageSubmissionError
)

MODULE_CODE = "SUBMIT"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("submission", ("submit", "view"))
def index():
    """
    My Workbooks dashboard page.
    """
    return render_template("modules/SUBMIT/my_sheets.html", module_code=MODULE_CODE)


@bp.route("/annual")
@require_login
def annual_workbook():
    """
    Annual workbook shell for SPOC entry. Underlying data remains monthly.
    """
    return render_template("modules/SUBMIT/annual_workbook.html", module_code=MODULE_CODE)


@bp.route("/submissions/<int:submission_id>")
@require_permission("submission", "view")
def edit_submission(submission_id):
    """
    Form Data Entry page.
    """
    sub = Submission.query.get_or_404(submission_id)
    if sub.status not in ("Draft", "Changes Requested"):
        if sub.package_id:
            return redirect(f"/module/APPROV/packages/{sub.package_id}")
        period = ReportingPeriod.query.get(sub.reporting_period_id)
        if period:
            fy_start = period.year if period.month >= 4 else period.year - 1
            return redirect(
                f"/module/SUBMIT/annual?site_id={sub.site_id}"
                f"&form_id={sub.form_id}&fy={fy_start}&month={period.month}"
            )
    return render_template(
        "modules/SUBMIT/data_entry.html",
        module_code=MODULE_CODE,
        submission_id=submission_id
    )


@bp.route("/submissions/download/<path:storage_key>")
@require_permission("submission", "view")
def download_proof(storage_key):
    """
    Serves uploaded proof documents.
    """
    try:
        file_path = get_file_path(storage_key)
        original_name = storage_key.split('/')[-1]
        return send_file(file_path, as_attachment=True, download_name=original_name)
    except Exception as e:
        return error_response(str(e), 400)


# --- REST API Endpoints ---

@bp.route("/api/sheets", methods=["GET"])
@require_permission("submission", ("submit", "view"))
def get_sheets():
    """
    Get SPOC submission sheets grouped into buckets.
    """
    user = current_user()
    buckets = get_spoc_sheets_buckets(user.id)
    return jsonify(buckets)


@bp.route("/api/annual-workbook/options", methods=["GET"])
@require_login
def annual_workbook_options():
    """
    Return sites and site-assigned forms available to the current SPOC.
    """
    user = current_user()
    return jsonify(get_annual_workbook_options(user.id))


@bp.route("/api/annual-workbook", methods=["GET"])
@require_login
def annual_workbook_data():
    """
    Compose a read-only annual workbook view over monthly submissions.
    """
    user = current_user()
    try:
        data = compose_annual_workbook_data(
            user_id=user.id,
            site_id=request.args.get("site_id"),
            workbook_id=request.args.get("workbook_id"),
            fy_start_year=request.args.get("fy"),
            selected_form_id=request.args.get("form_id"),
        )
        return jsonify(data)
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/annual-workbook/calculation-results", methods=["GET"])
@require_login
def annual_workbook_calculation_results():
    """
    Returns read-only calculated results across forms for the site and FY.
    """
    user = current_user()
    try:
        data = compose_calculation_results(
            site_id=request.args.get("site_id"),
            workbook_id=request.args.get("workbook_id"),
            fy_start_year=request.args.get("fy"),
            user_id=user.id,
        )
        return jsonify(data)
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/annual-workbook/package/submit", methods=["POST"])
@require_login
def submit_annual_workbook_package():
    """
    Submit the selected month as a workbook package foundation.
    Existing monthly submission validation/routing remains authoritative.
    """
    data = request.get_json() or {}
    user = current_user()
    try:
        result = submit_monthly_workbook_package(
            site_id=data.get("site_id"),
            workbook_id=data.get("workbook_id"),
            period_id=data.get("period_id"),
            year=data.get("year"),
            month=data.get("month"),
            user_id=user.id,
            selected_form_id=data.get("selected_form_id"),
            values=data.get("values") or {},
        )
        db.session.commit()
        return success_response(
            data=result,
            message="Workbook package submitted successfully."
        )
    except PackageSubmissionError as e:
        db.session.rollback()
        return jsonify({
            "error": str(e),
            "errors": e.errors,
            "warnings": e.warnings,
        }), 422 if e.errors else 400
    except (ValueError, DuplicateSubmissionError) as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Annual workbook package submit failed")
        return error_response("Could not submit workbook package.", 500)


@bp.route("/api/annual-workbook/values", methods=["PUT"])
@require_login
def save_annual_workbook_values_endpoint():
    data = request.get_json() or {}
    user = current_user()
    try:
        result = save_annual_workbook_values(
            user_id=user.id,
            site_id=data.get("site_id"),
            workbook_id=data.get("workbook_id"),
            form_id=data.get("form_id"),
            fy_start_year=data.get("fy"),
            values=data.get("values") or {},
        )
        db.session.commit()
        return success_response(data=result, message="Annual workbook values saved successfully.")
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Annual workbook value save failed")
        return error_response("Could not save annual workbook values.", 500)


@bp.route("/api/submissions", methods=["POST"])
@require_login
def create_submission_endpoint():
    """
    Creates a new Draft submission.
    """
    data = request.get_json() or {}
    site_id = data.get("site_id")
    form_id = data.get("form_id")
    reporting_period_id = data.get("reporting_period_id")
    
    user = current_user()
    try:
        sub = create_draft_submission(
            site_id,
            form_id,
            reporting_period_id,
            user.id,
            workbook_id=data.get("workbook_id"),
        )
        db.session.commit()
        return success_response(
            data={"submission_id": sub.id},
            message="Draft sheet created successfully."
        )
    except DuplicateSubmissionError as e:
        db.session.rollback()
        return jsonify({
            "error": "A submission already exists for this site, form, and period.",
            "existing_id": e.existing_id
        }), 409
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Draft submission creation failed")
        return error_response("Could not create draft for this month.", 500)


@bp.route("/api/submissions/<int:submission_id>", methods=["GET"])
@require_permission("submission", "view")
def get_submission_details(submission_id):
    """
    Load form fields and values for a submission.
    """
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        return error_response("Submission not found.", 404)
        
    # Get form fields
    fields = get_form_version_fields(submission.form_version_id)
    
    # Load values
    db_values = SubmissionValue.query.filter_by(submission_id=submission_id).all()
    id_to_code = {}
    fields_data = []
    
    for fv, f in fields:
        id_to_code[f.id] = f.field_code
        fields_data.append({
            "id": f.id,
            "field_id": f.id,
            "field_code": f.field_code,
            "field_name": fv.field_name,
            "field_type": fv.field_type,
            "field_config": fv.field_config or {},
            "display_order": f.display_order
        })
        
    values_dict = {}
    for val in db_values:
        code = id_to_code.get(val.field_id)
        if not code:
            continue
            
        f_info = next((fd for fd in fields_data if fd["field_id"] == val.field_id), None)
        if f_info and f_info["field_type"] == "file":
            proof = ProofDocument.query.filter_by(
                submission_id=submission_id,
                field_id=val.field_id,
                is_deleted=False
            ).first()
            if proof:
                values_dict[code] = {
                    "storage_key": proof.storage_key,
                    "original_name": proof.original_name
                }
            else:
                values_dict[code] = ""
        else:
            if val.calculated_value is not None:
                values_dict[code] = float(val.calculated_value)
            else:
                values_dict[code] = val.raw_value or ""
                
    # Check for anomalies
    from app.common.anomaly import check_anomalies
    anomalies = check_anomalies(submission_id)
    
    # Load site/form metadata
    from app.modules.SITEMST.model import Site
    site = Site.query.get(submission.site_id)
    form = Form.query.get(submission.form_id)
    try:
        parsed_desc = json.loads(form.description or "{}") if form else {}
    except Exception:
        parsed_desc = {}
    from app.modules.SUBMIT.service import format_period_label
    period = ReportingPeriod.query.get(submission.reporting_period_id)
    period_label = format_period_label(period.year, period.month) if period else ""
    
    return jsonify({
        "submission": {
            "id": submission.id,
            "site_id": submission.site_id,
            "site_name": site.name if site else "",
            "form_id": submission.form_id,
            "form_name": human_sheet_label(form),
            "reporting_period_id": submission.reporting_period_id,
            "period_label": period_label,
            "status": submission.status,
            "is_locked": submission.is_locked,
            "form_version_id": submission.form_version_id,
            "workflow_version_id": submission.workflow_version_id,
            "workflow_id": parsed_desc.get("workflow_id")
        },
        "fields": fields_data,
        "values": values_dict,
        "anomalies": anomalies
    })


@bp.route("/api/submissions/<int:submission_id>/autosave", methods=["PUT"])
@require_login
def autosave_endpoint(submission_id):
    """
    Saves form draft entries and computes calculated fields.
    """
    data = request.get_json() or {}
    values_dict = data.get("values", {})
    
    user = current_user()
    try:
        calc_errors = autosave_submission_values(submission_id, values_dict, user.id)
        db.session.commit()
        
        # Load updated values using the form's current version so that calculated
        # fields added after the submission was created appear in the response.
        submission = Submission.query.get(submission_id)
        form = Form.query.get(submission.form_id)
        current_version_id = (form.current_version_id if form else None) or submission.form_version_id
        db_values = SubmissionValue.query.filter_by(submission_id=submission_id).all()
        fields = get_form_version_fields(current_version_id)
        
        id_to_code = {f.id: f.field_code for fv, f in fields}
        fields_data = [{"field_id": f.id, "field_code": f.field_code, "field_type": fv.field_type} for fv, f in fields]
        
        values_dict = {}
        for val in db_values:
            code = id_to_code.get(val.field_id)
            if not code:
                continue
            f_info = next((fd for fd in fields_data if fd["field_id"] == val.field_id), None)
            if f_info and f_info["field_type"] == "file":
                proof = ProofDocument.query.filter_by(
                    submission_id=submission_id,
                    field_id=val.field_id,
                    is_deleted=False
                ).first()
                if proof:
                    values_dict[code] = {
                        "storage_key": proof.storage_key,
                        "original_name": proof.original_name
                    }
                else:
                    values_dict[code] = ""
            else:
                if val.calculated_value is not None:
                    values_dict[code] = float(val.calculated_value)
                else:
                    values_dict[code] = val.raw_value or ""
                    
        # Check anomalies
        from app.common.anomaly import check_anomalies
        anomalies = check_anomalies(submission_id)
        
        return success_response(
            data={
                "values": values_dict,
                "calculation_errors": calc_errors,
                "anomalies": anomalies
            },
            message="Autosaved successfully."
        )
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Submission autosave failed")
        return error_response("Could not save draft.", 500)


@bp.route("/api/submissions/<int:submission_id>/proof/<string:field_code>", methods=["POST"])
@require_permission("submission", "edit")
def upload_proof_endpoint(submission_id, field_code):
    """
    Handles proof file uploads for a specific field code.
    """
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        return error_response("Submission not found.", 404)
        
    if submission.status not in ("Draft", "Changes Requested"):
        return error_response(f"Cannot edit submission in status: {submission.status}", 400)
        
    if "file" not in request.files:
        return error_response("No file uploaded.", 400)
        
    file = request.files["file"]
    if file.filename == "":
        return error_response("No file selected.", 400)
        
    field = Field.query.filter_by(form_id=submission.form_id, field_code=field_code, is_deleted=False).first()
    if not field:
        return error_response("Field not found.", 404)
        
    field_version = FieldVersion.query.filter_by(field_id=field.id, form_version_id=submission.form_version_id).first()
    if not field_version:
        return error_response("Field version not found.", 404)
        
    try:
        user = current_user()
        saved_info = save_file(file)
        
        # Save ProofDocument metadata
        proof = ProofDocument(
            submission_id=submission_id,
            field_id=field.id,
            original_name=saved_info["original_name"],
            storage_key=saved_info["storage_key"],
            mime_type=saved_info["mime_type"],
            file_size_bytes=saved_info["file_size_bytes"],
            uploaded_by=user.id
        )
        db.session.add(proof)
        db.session.flush()
        
        # Save SubmissionValue field link
        val_row = SubmissionValue.query.filter_by(
            submission_id=submission_id,
            field_id=field.id
        ).first()
        
        if not val_row:
            val_row = SubmissionValue(
                submission_id=submission_id,
                field_id=field.id,
                field_version_id=field_version.id,
                created_by=user.id
            )
            db.session.add(val_row)
            
        val_row.raw_value = saved_info["storage_key"]
        val_row.calculated_value = None
        set_submission_value_state(val_row, CELL_STATE_DRAFT_FILLED)
        val_row.updated_by = user.id
        submission.updated_by = user.id
        
        db.session.commit()
        return success_response(
            data={
                "storage_key": saved_info["storage_key"],
                "original_name": saved_info["original_name"]
            },
            message="Proof uploaded successfully."
        )
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 400)


@bp.route("/api/submissions/<int:submission_id>/submit", methods=["POST"])
@require_login
def submit_endpoint(submission_id):
    """
    Submits a sheet for review.
    """
    user = current_user()
    try:
        data = request.get_json(silent=True) or {}
        if data.get("workbook_id"):
            assign_submission_workflow_from_workbook(submission_id, data.get("workbook_id"), user.id)
        submit_submission(submission_id, user.id)
        db.session.commit()
        return success_response(message="Sheet submitted successfully.")
    except SubmissionValidationError as e:
        db.session.rollback()
        return jsonify({
            "error": str(e),
            "validation_errors": e.errors
        }), 422
    except (ValueError, DuplicateSubmissionError) as e:
        db.session.rollback()
        return error_response(str(e), 400)
