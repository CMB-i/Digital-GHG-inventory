from flask import Blueprint, render_template

from app.common.decorators import require_permission


MODULE_CODE = "FRMULA"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("formula", "view")
def index():
    return render_template("modules/FRMULA/formula_builder.html", module_code=MODULE_CODE)
