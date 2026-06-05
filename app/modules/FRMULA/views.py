from flask import Blueprint, render_template, request, jsonify

from app.common.decorators import require_permission
from app.common.auth import current_user
from app.common.responses import success_response, error_response
from app.database import db
from app.modules.FORMBLD.model import Form, FormVersion
from app.modules.FORMBLD.service import get_formula_compatible_fields
from app.modules.FRMULA.model import Formula, FormulaVersion
from app.modules.FRMULA.service import (
    FormulaValidationError,
    validate_formula,
    list_formulas,
    get_formula,
    create_formula,
    publish_formula_version,
    create_new_formula_draft,
)
from app.modules.USRMGMT.model import User
from app.modules.VALSET.model import ValueSet, ValueSetVersion, ValueSetEntry


MODULE_CODE = "FRMULA"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


def _get_active_valset_codes():
    """Return the set of all entry_code values from currently approved value sets."""
    approved = (
        ValueSet.query.filter_by(is_deleted=False)
        .join(ValueSetVersion, ValueSetVersion.id == ValueSet.current_version_id)
        .filter(ValueSetVersion.status == "Approved")
        .all()
    )
    codes = set()
    for vs in approved:
        entries = ValueSetEntry.query.filter_by(
            value_set_version_id=vs.current_version_id,
            is_deleted=False,
            is_active=True,
        ).all()
        for e in entries:
            codes.add(e.entry_code)
    return codes


@bp.route("/", methods=["GET", "POST"])
@require_permission("formula", "view")
def index():
    form_versions = (
        FormVersion.query.with_entities(FormVersion, Form)
        .join(Form, Form.id == FormVersion.form_id)
        .filter(Form.is_deleted.is_(False))
        .order_by(Form.name.asc(), FormVersion.version_number.desc())
        .all()
    )
    selected_form_version_id = request.values.get("form_version_id", type=int)
    if selected_form_version_id is None and form_versions:
        selected_form_version_id = form_versions[0][0].id

    compatible_fields = get_formula_compatible_fields(selected_form_version_id)
    
    # Load approved value sets for token constants insertion
    from app.modules.VALSET.model import ValueSet, ValueSetVersion, ValueSetEntry
    approved_valsets = (
        ValueSet.query.filter_by(is_deleted=False)
        .join(ValueSetVersion, ValueSetVersion.id == ValueSet.current_version_id)
        .filter(ValueSetVersion.status == "Approved")
        .all()
    )
    
    valset_options = []
    for vs in approved_valsets:
        entries = ValueSetEntry.query.filter_by(
            value_set_version_id=vs.current_version_id,
            is_deleted=False,
            is_active=True
        ).all()
        for entry in entries:
            # We want to enable inserting the entry code
            valset_options.append({
                "value_set_name": vs.name,
                "entry_code": entry.entry_code,
                "entry_label": entry.entry_label
            })

    expression = request.form.get("expression", "")
    validation_message = None
    validation_error = None
    if request.method == "POST":
        try:
            validate_formula(
                expression,
                {field["field_code"] for field in compatible_fields},
            )
            validation_message = "Formula is valid."
        except FormulaValidationError as error:
            validation_error = str(error)

    return render_template(
        "modules/FRMULA/formula_builder.html",
        module_code=MODULE_CODE,
        form_versions=form_versions,
        selected_form_version_id=selected_form_version_id,
        compatible_fields=compatible_fields,
        valset_options=valset_options,
        expression=expression,
        validation_message=validation_message,
        validation_error=validation_error,
    )


# --- REST API Endpoints ---

@bp.route("/api", methods=["GET"])
@require_permission("formula", "view")
def get_list():
    formulas = list_formulas()
    result = []
    for f in formulas:
        # Get latest version
        latest_version = FormulaVersion.query.filter_by(formula_id=f.id).order_by(FormulaVersion.version_number.desc()).first()
        result.append({
            "id": f.id,
            "name": f.name,
            "code": f.code,
            "current_version_id": f.current_version_id,
            "latest_version_id": latest_version.id if latest_version else None,
            "latest_version_num": latest_version.version_number if latest_version else None,
            "latest_version_expression": latest_version.expression if latest_version else None,
            "latest_version_tokens": latest_version.tokens if latest_version else {},
            "is_published": latest_version.published_at is not None if latest_version else False
        })
    return jsonify(result)


@bp.route("/api", methods=["POST"])
@require_permission("formula", "manage_forms")
def create():
    data = request.get_json() or {}
    name = data.get("name")
    code = data.get("code")
    expression = data.get("expression")
    tokens = data.get("tokens", {})

    user = current_user()
    try:
        # Merge token keys with all active valset codes for validation
        allowed_names = set(tokens.keys()) | _get_active_valset_codes()
        validate_formula(expression, allowed_names)

        formula = create_formula(name, code, expression, tokens, user.id)
        db.session.commit()
        return success_response(
            data={"id": formula.id, "name": formula.name, "code": formula.code},
            message="Formula created successfully."
        )
    except (ValueError, FormulaValidationError) as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:formula_id>", methods=["PUT"])
@require_permission("formula", "manage_forms")
def update_details(formula_id):
    data = request.get_json() or {}
    name = data.get("name")
    
    formula = get_formula(formula_id)
    if not formula:
        return error_response("Formula not found.", 404)
        
    try:
        if name:
            formula.name = name.strip()
        formula.updated_by = current_user().id
        db.session.commit()
        return success_response(message="Formula details updated successfully.")
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 400)


@bp.route("/api/validate", methods=["POST"])
@require_permission("formula", "view")
def validate_endpoint():
    data = request.get_json() or {}
    expression = data.get("expression")
    field_codes = set(data.get("field_codes", []))
    # Merge in all active value set entry codes so valset-only formulas pass
    field_codes |= _get_active_valset_codes()

    try:
        validate_formula(expression, field_codes)
        return jsonify({"valid": True, "message": "Formula is valid."})
    except FormulaValidationError as e:
        return jsonify({"valid": False, "error": str(e)})


@bp.route("/api/version/<int:version_id>", methods=["GET"])
@require_permission("formula", "view")
def get_version_details(version_id):
    version = FormulaVersion.query.get(version_id)
    if not version:
        return error_response("Formula version not found.", 404)
        
    parent = get_formula(version.formula_id)
    
    # Load username helper
    u = User.query.get(version.published_by) if version.published_by else None
    
    data = {
        "formula": {
            "id": parent.id,
            "name": parent.name,
            "code": parent.code,
        },
        "version": {
            "id": version.id,
            "version_number": version.version_number,
            "expression": version.expression,
            "tokens": version.tokens,
            "published_at": version.published_at.isoformat() if version.published_at else None,
            "published_by": u.full_name if u else None,
        }
    }
    return jsonify(data)


@bp.route("/api/version/<int:version_id>/publish", methods=["POST"])
@require_permission("formula", "manage_forms")
def publish_version(version_id):
    user = current_user()
    try:
        publish_formula_version(version_id, user.id)
        db.session.commit()
        return success_response(message="Formula published successfully.")
    except (ValueError, FormulaValidationError) as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:formula_id>/new-version", methods=["POST"])
@require_permission("formula", "manage_forms")
def create_new_version(formula_id):
    data = request.get_json() or {}
    expression = data.get("expression")
    tokens = data.get("tokens", {})

    user = current_user()
    try:
        # Merge token keys with all active valset codes for validation
        allowed_names = set(tokens.keys()) | _get_active_valset_codes()
        validate_formula(expression, allowed_names)
        new_version = create_new_formula_draft(formula_id, expression, tokens, user.id)
        db.session.commit()
        return success_response(
            data={"version_id": new_version.id, "version_number": new_version.version_number},
            message="New draft version created."
        )
    except (ValueError, FormulaValidationError) as e:
        return error_response(str(e), 400)
