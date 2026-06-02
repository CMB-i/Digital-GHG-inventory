from flask import Blueprint, render_template


MODULE_CODE = "NOTIFY"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
def index():
    return render_template("modules/NOTIFY/notifications.html", module_code=MODULE_CODE)
