from flask import Blueprint, render_template, request

from app.common.decorators import require_permission
from app.modules.FORMBLD.model import Form, FormVersion
from app.modules.FORMBLD.service import get_formula_compatible_fields
from app.modules.FRMULA.service import FormulaValidationError, validate_formula


MODULE_CODE = "FRMULA"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


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
        expression=expression,
        validation_message=validation_message,
        validation_error=validation_error,
    )
