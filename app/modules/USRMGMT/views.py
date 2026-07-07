from flask import Blueprint, redirect, render_template, request, session, url_for

from app.database import db
from app.modules.USRMGMT.service import (
    authenticate_user,
    record_successful_login,
)


auth_bp = Blueprint("auth", __name__)


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
            return redirect(request.args.get("next") or url_for("index"))
        error = "Invalid email or password, or the user is inactive."

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
