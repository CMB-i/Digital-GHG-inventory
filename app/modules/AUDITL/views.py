from flask import Blueprint, render_template

from app.common.decorators import require_permission


MODULE_CODE = "AUDITL"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("audit_log", "view")
def index():
    return render_template("modules/AUDITL/audit_log.html", module_code=MODULE_CODE)
