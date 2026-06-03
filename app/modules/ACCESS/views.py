from flask import Blueprint, render_template

from app.common.decorators import require_permission


MODULE_CODE = "ACCESS"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("user", "manage_users")
def index():
    return render_template("modules/ACCESS/access_matrix.html", module_code=MODULE_CODE)
