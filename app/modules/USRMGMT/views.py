from flask import Blueprint, redirect, render_template, request, session, url_for

from app.common.decorators import require_permission
from app.modules.USRMGMT.service import authenticate_user


MODULE_CODE = "USRMGMT"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")
auth_bp = Blueprint("auth", __name__)


@bp.route("/")
@require_permission("user", "manage_users")
def index():
    return render_template("modules/USRMGMT/users.html", module_code=MODULE_CODE)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = authenticate_user(email, password)
        if user:
            session.clear()
            session["user_id"] = user.id
            return redirect(request.args.get("next") or url_for("dashboard"))
        error = "Invalid email or password, or the user is inactive."

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
