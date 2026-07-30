from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.common.auth import is_safe_internal_path
from app.common.validators import ValidationError
from app.database import db
from app.modules.USRMGMT.service import (
    authenticate_user,
    record_successful_login,
    request_password_reset_otp,
    reset_password_with_otp,
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
            session["user_session_version"] = user.session_version
            from app import default_landing_url
            next_url = request.args.get("next")
            return redirect(next_url if is_safe_internal_path(next_url) else default_landing_url(user))
        error = "Invalid email or password, or the user is inactive."

    return render_template("login.html", error=error)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        return send_forgot_password_otp()
    return render_template("forgot_password.html")


@auth_bp.route("/forgot-password/send-otp", methods=["POST"])
def send_forgot_password_otp():
    email = request.form.get("email")
    try:
        request_password_reset_otp(email)
        db.session.commit()
        flash("If that email is registered, a reset code has been sent.", "success")
        return redirect(url_for("auth.reset_password", email=(email or "").strip().lower()))
    except ValidationError as error:
        db.session.rollback()
        return render_template("forgot_password.html", error=str(error), email=email), 400
    except Exception:
        db.session.rollback()
        return render_template("forgot_password.html", error="Could not send reset code. Try again later.", email=email), 500


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = request.values.get("email", "")
    if request.method == "POST":
        try:
            if request.form.get("new_password") != request.form.get("confirm_password"):
                raise ValidationError("Passwords do not match.")
            reset_password_with_otp(
                request.form.get("email"),
                request.form.get("otp_code"),
                request.form.get("new_password"),
            )
            db.session.commit()
            flash("Password reset. Sign in with your new password.", "success")
            return redirect(url_for("auth.login"))
        except ValidationError as error:
            db.session.commit()
            return render_template("reset_password.html", error=str(error), email=request.form.get("email", "")), 400
        except Exception:
            db.session.rollback()
            return render_template("reset_password.html", error="Could not reset password. Try again later.", email=request.form.get("email", "")), 500

    return render_template("reset_password.html", email=email)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
