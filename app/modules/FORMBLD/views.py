from flask import Blueprint, render_template, request

from app.common.decorators import require_permission
from app.database import db


MODULE_CODE = "FORMBLD"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("form", "manage_forms")
def index():
    return render_template("modules/FORMBLD/form_builder.html", module_code=MODULE_CODE)


# --- REST API Endpoints ---
from flask import jsonify
from app.common.auth import current_user
from app.common.responses import success_response, error_response
from app.modules.FORMBLD.service import (
    list_forms,
    get_form,
    get_form_by_code,
    create_form,
    get_form_version,
    get_form_version_fields,
    save_form_draft_fields,
    publish_form_version,
    create_new_form_version_draft
)
from app.modules.FORMBLD.model import FormVersion
from app.modules.USRMGMT.model import User

@bp.route("/api", methods=["GET"])
@require_permission("form", "view")
def get_list():
    forms = list_forms()
    result = []
    import json
    for f in forms:
        # Get latest version
        latest_version = FormVersion.query.filter_by(form_id=f.id).order_by(FormVersion.version_number.desc()).first()
        
        # Parse description JSON
        parsed_desc = {
            "display_name": f.name,
            "gri_code": "",
            "sites": [],
            "frequency": "Monthly",
            "workflow_id": None,
            "description_text": f.description or ""
        }
        if f.description and f.description.startswith("{"):
            try:
                parsed_desc.update(json.loads(f.description))
            except Exception:
                pass
                
        result.append({
            "id": f.id,
            "name": f.name,
            "code": f.code,
            "description": parsed_desc["description_text"],
            "display_name": parsed_desc["display_name"],
            "gri_code": parsed_desc["gri_code"],
            "sites": parsed_desc["sites"],
            "frequency": parsed_desc["frequency"],
            "workflow_id": parsed_desc["workflow_id"],
            "current_version_id": f.current_version_id,
            "latest_version_id": latest_version.id if latest_version else None,
            "latest_version_num": latest_version.version_number if latest_version else None,
            "latest_version_status": latest_version.status if latest_version else None
        })
    return jsonify(result)


@bp.route("/api", methods=["POST"])
@require_permission("form", "manage_forms")
def create():
    data = request.get_json() or {}
    name = data.get("name")
    code = data.get("code")
    
    # Serialize metadata in description
    import json
    metadata = {
        "display_name": data.get("display_name", name),
        "gri_code": data.get("gri_code", ""),
        "sites": data.get("sites", []),
        "frequency": data.get("frequency", "Monthly"),
        "workflow_id": data.get("workflow_id"),
        "description_text": data.get("description", "")
    }
    desc_str = json.dumps(metadata)

    user = current_user()
    try:
        form = create_form(name, code, desc_str, user.id)
        db.session.commit()
        return success_response(
            data={"id": form.id, "name": form.name, "code": form.code},
            message="Form created successfully."
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:form_id>", methods=["PUT"])
@require_permission("form", "manage_forms")
def update_details(form_id):
    data = request.get_json() or {}
    name = data.get("name")
    code = data.get("code")
    
    form = get_form(form_id)
    if not form:
        return error_response("Form not found.", 404)
        
    try:
        # Check code uniqueness if code changed
        if code and code != form.code:
            existing = get_form_by_code(code)
            if existing:
                return error_response(f"Form with code '{code}' already exists.", 400)
            form.code = code
            
        if name:
            form.name = name
            
        # Serialize metadata in description
        import json
        metadata = {
            "display_name": data.get("display_name", name),
            "gri_code": data.get("gri_code", ""),
            "sites": data.get("sites", []),
            "frequency": data.get("frequency", "Monthly"),
            "workflow_id": data.get("workflow_id"),
            "description_text": data.get("description_text", "")
        }
        form.description = json.dumps(metadata)
        form.updated_by = current_user().id
        db.session.commit()
        return success_response(message="Form details updated successfully.")
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 400)


@bp.route("/api/version/<int:version_id>", methods=["GET"])
@require_permission("form", "view")
def get_version_details(version_id):
    version = get_form_version(version_id)
    if not version:
        return error_response("Form version not found.", 404)
        
    parent = get_form(version.form_id)
    fields = get_form_version_fields(version_id)
    
    # Check permissions
    user = current_user()
    from app.common.permissions import has_permission
    can_edit = has_permission(user.id, "form", "manage_forms")
    
    # Get all versions
    versions = FormVersion.query.filter_by(form_id=version.form_id).order_by(FormVersion.version_number.desc()).all()
    version_list = [{
        "id": v.id,
        "version_number": v.version_number,
        "status": v.status
    } for v in versions]

    # Query for approved value sets and published formulas so the builder right panel can populate dropdown lists
    from app.modules.VALSET.model import ValueSet, ValueSetVersion
    approved_valsets = (
        ValueSet.query.filter_by(is_deleted=False)
        .join(ValueSetVersion, ValueSetVersion.id == ValueSet.current_version_id)
        .filter(ValueSetVersion.status == "Approved")
        .all()
    )
    valsets_data = [{
        "id": vs.id,
        "current_version_id": vs.current_version_id,
        "name": vs.name,
        "code": vs.code
    } for vs in approved_valsets]

    from app.modules.FRMULA.model import Formula, FormulaVersion
    published_formulas = (
        Formula.query.filter_by(is_deleted=False)
        .join(FormulaVersion, FormulaVersion.id == Formula.current_version_id)
        .filter(FormulaVersion.published_at.is_not(None))
        .all()
    )
    formulas_data = [{
        "id": f.id,
        "current_version_id": f.current_version_id,
        "name": f.name,
        "code": f.code
    } for f in published_formulas]

    from app.modules.WFLWBLD.model import Workflow
    all_workflows = (
        Workflow.query.filter_by(is_deleted=False)
        .all()
    )
    workflows_data = [{
        "id": w.id,
        "current_version_id": w.current_version_id,
        "name": w.name,
        "code": w.code
    } for w in all_workflows]

    import json
    parsed_desc = {
        "display_name": parent.name,
        "gri_code": "",
        "sites": [],
        "frequency": "Monthly",
        "workflow_id": None,
        "description_text": parent.description or ""
    }
    if parent.description and parent.description.startswith("{"):
        try:
            parsed_desc.update(json.loads(parent.description))
        except Exception:
            pass

    data = {
        "form": {
            "id": parent.id,
            "name": parent.name,
            "code": parent.code,
            "description": parsed_desc["description_text"],
            "display_name": parsed_desc["display_name"],
            "gri_code": parsed_desc["gri_code"],
            "sites": parsed_desc["sites"],
            "frequency": parsed_desc["frequency"],
            "workflow_id": parsed_desc["workflow_id"],
        },
        "version": {
            "id": version.id,
            "version_number": version.version_number,
            "status": version.status,
            "published_at": version.published_at.isoformat() if version.published_at else None,
        },
        "fields": [{
            "id": fv.field_id,
            "field_version_id": fv.id,
            "field_code": f.field_code,
            "display_order": f.display_order,
            "field_name": fv.field_name,
            "field_type": fv.field_type,
            "field_config": fv.field_config or {},
        } for fv, f in fields],
        "all_versions": version_list,
        "available_value_sets": valsets_data,
        "available_formulas": formulas_data,
        "available_workflows": workflows_data,
        "permissions": {
            "can_edit": can_edit and version.status == "Draft",
            "can_publish": can_edit and version.status == "Draft",
            "can_create_version": can_edit and version.status == "Published"
        }
    }
    return jsonify(data)


@bp.route("/api/version/<int:version_id>/fields", methods=["POST"])
@require_permission("form", "manage_forms")
def save_fields(version_id):
    data = request.get_json() or {}
    fields_list = data.get("fields")
    if not isinstance(fields_list, list):
        return error_response("Fields must be a list.", 400)
        
    user = current_user()
    try:
        save_form_draft_fields(version_id, fields_list, user.id)
        db.session.commit()
        return success_response(message="Form fields saved successfully.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/version/<int:version_id>/publish", methods=["POST"])
@require_permission("form", "manage_forms")
def publish(version_id):
    user = current_user()
    try:
        publish_form_version(version_id, user.id)
        db.session.commit()
        return success_response(message="Form published successfully.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:form_id>/new-version", methods=["POST"])
@require_permission("form", "manage_forms")
def create_new_version(form_id):
    user = current_user()
    try:
        new_version = create_new_form_version_draft(form_id, user.id)
        db.session.commit()
        return success_response(
            data={"version_id": new_version.id, "version_number": new_version.version_number},
            message="New draft version created."
        )
    except ValueError as e:
        return error_response(str(e), 400)
