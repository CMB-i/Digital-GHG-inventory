from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify

from app.common.auth import current_user
from app.common.decorators import require_permission
from app.common.permissions import has_permission
from app.common.validators import ValidationError
from app.database import db
from app.modules.SITEMST.service import (
    create_site,
    deactivate_site,
    get_site,
    list_sites,
    reactivate_site,
    update_site,
)


MODULE_CODE = "SITEMST"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("site", "view")
def index():
    drawer = request.args.get("drawer")
    selected_site_id = request.args.get("site_id", type=int)

    user = current_user()
    perm_create = has_permission(user.id, "site", "create")
    perm_edit = has_permission(user.id, "site", "edit")
    perm_delete = has_permission(user.id, "site", "delete")

    create_drawer_open = drawer == "create" and perm_create
    edit_drawer_open = drawer == "edit" and selected_site_id is not None and perm_edit

    active_sites, inactive_sites = list_sites()
    selected_site = None
    if edit_drawer_open:
        selected_site = get_site(selected_site_id)
        if selected_site is None:
            edit_drawer_open = False

    return render_template(
        "modules/SITEMST/sites.html",
        module_code=MODULE_CODE,
        active_sites=active_sites,
        inactive_sites=inactive_sites,
        create_drawer_open=create_drawer_open,
        edit_drawer_open=edit_drawer_open,
        selected_site=selected_site,
        perm_create=perm_create,
        perm_edit=perm_edit,
        perm_delete=perm_delete,
    )


@bp.route("/create", methods=["POST"])
@require_permission("site", "create")
def create():
    actor = current_user()
    try:
        create_site(
            name=request.form.get("name"),
            code=request.form.get("code"),
            company_name=request.form.get("company_name"),
            description=request.form.get("description"),
            actor_id=actor.id,
        )
        db.session.commit()
        flash("Site created.", "success")
        return redirect(url_for("sitemst.index"))
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not create site.", "error")
    return redirect(url_for("sitemst.index", drawer="create"))


@bp.route("/<int:site_id>/edit", methods=["POST"])
@require_permission("site", "edit")
def edit(site_id):
    actor = current_user()
    try:
        site = update_site(
            site_id=site_id,
            name=request.form.get("name"),
            code=request.form.get("code"),
            company_name=request.form.get("company_name"),
            description=request.form.get("description"),
            actor_id=actor.id,
        )
        if not site:
            flash("Site not found.", "error")
        else:
            db.session.commit()
            flash("Site updated.", "success")
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not update site.", "error")
    return redirect(url_for("sitemst.index"))


@bp.route("/<int:site_id>/deactivate", methods=["POST"])
@require_permission("site", "delete")
def deactivate(site_id):
    actor = current_user()
    try:
        site = deactivate_site(site_id, actor.id)
        if not site:
            flash("Site not found or already deactivated.", "error")
        else:
            db.session.commit()
            flash("Site deactivated.", "success")
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not deactivate site.", "error")
    return redirect(url_for("sitemst.index"))


@bp.route("/<int:site_id>/reactivate", methods=["POST"])
@require_permission("site", "edit")
def reactivate(site_id):
    actor = current_user()
    try:
        site = reactivate_site(site_id, actor.id)
        if not site:
            flash("Site not found or already active.", "error")
        else:
            db.session.commit()
            flash("Site reactivated.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not reactivate site.", "error")
    return redirect(url_for("sitemst.index"))


@bp.route("/api", methods=["GET"])
@require_permission("site", "view")
def get_list():
    """Expose active sites list for use in Form Builder site applicability picker."""
    active_sites, _ = list_sites()
    return jsonify([{
        "id": s.id,
        "name": s.name,
        "code": s.code,
        "company_name": s.company_name
    } for s in active_sites])
