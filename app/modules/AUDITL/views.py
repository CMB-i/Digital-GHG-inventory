from flask import Blueprint, render_template


MODULE_CODE = "AUDITL"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
def index():
    return render_template("modules/AUDITL/audit_log.html", module_code=MODULE_CODE)
