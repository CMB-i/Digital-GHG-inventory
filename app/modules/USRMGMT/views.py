from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.common.auth import current_user
from app.common.decorators import require_permission
from app.database import db
from app.modules.USRMGMT.service import (
    authenticate_user,
    create_user,
    list_users,
    record_successful_login,
    set_temporary_password,
    set_user_active,
    update_user,
)


MODULE_CODE = "USRMGMT"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")
auth_bp = Blueprint("auth", __name__)


@bp.route("/")
@require_permission("user", "manage_users")
def index():
    return render_template(
        "modules/USRMGMT/users.html",
        module_code=MODULE_CODE,
        users=list_users(),
    )


@bp.route("/create", methods=["POST"])
@require_permission("user", "manage_users")
def create():
    actor = current_user()
    temporary_password = request.form.get("temporary_password")
    if not temporary_password:
        flash("Temporary password is required.", "error")
        return redirect(url_for("usrmgmt.index"))

    try:
        create_user(
            full_name=request.form.get("full_name"),
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            temporary_password=temporary_password,
            actor_id=actor.id,
        )
        db.session.commit()
        flash("User created.", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"Could not create user: {error}", "error")
    return redirect(url_for("usrmgmt.index"))


@bp.route("/<int:user_id>/edit", methods=["POST"])
@require_permission("user", "manage_users")
def edit(user_id):
    user = update_user(
        user_id=user_id,
        full_name=request.form.get("full_name"),
        email=request.form.get("email"),
        phone=request.form.get("phone"),
    )
    if not user:
        flash("User not found.", "error")
    else:
        db.session.commit()
        flash("User updated.", "success")
    return redirect(url_for("usrmgmt.index"))


@bp.route("/<int:user_id>/password", methods=["POST"])
@require_permission("user", "manage_users")
def password(user_id):
    temporary_password = request.form.get("temporary_password")
    if not temporary_password:
        flash("Temporary password is required.", "error")
        return redirect(url_for("usrmgmt.index"))

    user = set_temporary_password(user_id, temporary_password)
    if not user:
        flash("User not found.", "error")
    else:
        db.session.commit()
        flash("Temporary password updated.", "success")
    return redirect(url_for("usrmgmt.index"))


@bp.route("/<int:user_id>/toggle-active", methods=["POST"])
@require_permission("user", "manage_users")
def toggle_active(user_id):
    is_active = request.form.get("is_active") == "true"
    _, error = set_user_active(user_id, is_active)
    if error:
        flash(error, "error")
    else:
        db.session.commit()
        flash("User status updated.", "success")
    return redirect(url_for("usrmgmt.index"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = authenticate_user(email, password)
        if user:
            record_successful_login(user)
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            return redirect(request.args.get("next") or url_for("dashboard"))
        error = "Invalid email or password, or the user is inactive."

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
