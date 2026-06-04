from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.common.auth import current_user
from app.common.decorators import require_permission
from app.common.validators import ValidationError
from app.database import db
from app.modules.ACCESS.service import (
    ENTITY_LABELS,
    ENTITY_ROWS,
    ENTITY_TYPES,
    PERMISSION_COLUMNS,
    PERMISSION_FLAGS,
    PERMISSION_LABELS,
    SUPPORTED_PERMISSION_FLAGS,
    build_permission_matrix,
    build_user_access_summary,
    list_access_rows,
    list_access_rows_for_scope,
    save_permission_matrix,
    upsert_access_row,
)
from app.modules.SITEMST.model import Site
from app.modules.USRMGMT.service import (
    create_user,
    list_users,
    set_temporary_password,
    set_user_active,
    update_user,
)


MODULE_CODE = "ACCESS"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("user", "manage_users")
def index():
    selected_user_id = request.args.get("user_id", type=int)
    drawer_open = request.args.get("drawer") == "permissions"
    create_drawer_open = request.args.get("drawer") == "create"
    selected_scope_type = request.args.get("scope_type") or "global"
    selected_scope_site_id = request.args.get("scope_site_id", type=int)
    users = list_users()
    sites = Site.query.filter_by(is_deleted=False).order_by(Site.name.asc()).all()
    selected_user = next((user for user in users if user.id == selected_user_id), None)
    if selected_user is None:
        selected_user_id = None
        drawer_open = False
    if selected_scope_type not in ("global", "site"):
        selected_scope_type = "global"
    if selected_scope_type == "global":
        selected_scope_site_id = None
    elif selected_scope_site_id is None and sites:
        selected_scope_site_id = sites[0].id

    return render_template(
        "modules/ACCESS/access_matrix.html",
        module_code=MODULE_CODE,
        users=users,
        sites=sites,
        site_lookup={site.id: site.name for site in sites},
        access_rows=list_access_rows_for_scope(selected_user_id, selected_scope_type, selected_scope_site_id)
        if selected_user_id
        else [],
        access_summary=build_user_access_summary(users, sites),
        permission_matrix=build_permission_matrix(selected_user_id, selected_scope_type, selected_scope_site_id)
        if selected_user_id
        else {},
        selected_user=selected_user,
        selected_user_id=selected_user_id,
        selected_scope_type=selected_scope_type,
        selected_scope_site_id=selected_scope_site_id,
        drawer_open=drawer_open,
        create_drawer_open=create_drawer_open,
        permission_flags=PERMISSION_FLAGS,
        permission_labels=PERMISSION_LABELS,
        permission_columns=PERMISSION_COLUMNS,
        supported_permission_flags=SUPPORTED_PERMISSION_FLAGS,
        entity_types=ENTITY_TYPES,
        entity_labels=ENTITY_LABELS,
        entity_rows=ENTITY_ROWS,
    )


@bp.route("/users/create", methods=["POST"])
@require_permission("user", "manage_users")
def create():
    actor = current_user()
    try:
        user = create_user(
            full_name=request.form.get("full_name"),
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            temporary_password=request.form.get("temporary_password"),
            actor_id=actor.id,
        )
        db.session.commit()
        flash("User created.", "success")
        return redirect(url_for("access.index"))
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not create user.", "error")
    return redirect(url_for("access.index", drawer="create"))


@bp.route("/users/<int:user_id>/edit", methods=["POST"])
@require_permission("user", "manage_users")
def edit(user_id):
    try:
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
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not update user.", "error")
    return redirect(url_for("access.index"))


@bp.route("/users/<int:user_id>/password", methods=["POST"])
@require_permission("user", "manage_users")
def password(user_id):
    try:
        user = set_temporary_password(user_id, request.form.get("temporary_password"))
        if not user:
            flash("User not found.", "error")
        else:
            db.session.commit()
            flash("Temporary password updated.", "success")
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not update temporary password.", "error")
    return redirect(url_for("access.index"))


@bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@require_permission("user", "manage_users")
def toggle_active(user_id):
    user, error = set_user_active(user_id, request.form.get("is_active") == "true")
    if error:
        flash(error, "error")
    elif not user:
        flash("User not found.", "error")
    else:
        db.session.commit()
        flash("User status updated.", "success")
    return redirect(url_for("access.index"))


@bp.route("/assign", methods=["POST"])
@require_permission("user", "manage_users")
def assign():
    actor = current_user()
    user_id = request.form.get("user_id", type=int)
    scope_type = request.form.get("scope_type")
    scope_site_id = request.form.get("scope_site_id", type=int)
    entity_type = request.form.get("entity_type")

    permissions = {flag: request.form.get(flag) == "on" for flag in PERMISSION_FLAGS}
    try:
        upsert_access_row(
            user_id=user_id,
            scope_type=scope_type,
            scope_site_id=scope_site_id,
            entity_type=entity_type,
            permission_values=permissions,
            actor_id=actor.id,
        )
        db.session.commit()
        flash("Permissions saved.", "success")
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not save permissions.", "error")
    return redirect(url_for("access.index", user_id=user_id, drawer="permissions"))


@bp.route("/assign-matrix", methods=["POST"])
@require_permission("user", "manage_users")
def assign_matrix():
    actor = current_user()
    user_id = request.form.get("user_id", type=int)
    scope_type = request.form.get("scope_type")
    scope_site_id = request.form.get("scope_site_id", type=int)
    matrix_values = {
        entity_type: {
            flag: request.form.get(f"perm__{entity_type}__{flag}") == "on"
            for flag in PERMISSION_FLAGS
        }
        for entity_type in ENTITY_TYPES
    }

    try:
        save_permission_matrix(
            user_id=user_id,
            scope_type=scope_type,
            scope_site_id=scope_site_id,
            matrix_values=matrix_values,
            actor_id=actor.id,
        )
        db.session.commit()
        flash("Access Matrix saved.", "success")
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not save the Access Matrix.", "error")
    return redirect(
        url_for(
            "access.index",
            user_id=user_id,
            drawer="permissions",
            scope_type=scope_type,
            scope_site_id=scope_site_id if scope_type == "site" else None,
        )
    )
