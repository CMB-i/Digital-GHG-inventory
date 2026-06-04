from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.common.auth import current_user
from app.common.decorators import require_permission
from app.common.permissions import has_permission
from app.common.validators import ValidationError
from app.database import db
from app.modules.PERIOD.service import (
    MONTH_NAMES,
    STATUS_LABELS,
    TRANSITION_ACTION,
    TRANSITION_LABELS,
    VALID_STATUSES,
    VALID_TRANSITIONS,
    create_period,
    list_periods,
    transition_period,
)
from app.modules.SITEMST.model import Site


MODULE_CODE = "PERIOD"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("period", "view")
def index():
    filter_site_id = request.args.get("site_id", type=int)
    filter_status = (request.args.get("status") or "").strip() or None

    if filter_status not in VALID_STATUSES:
        filter_status = None

    user = current_user()
    perm_create = has_permission(user.id, "period", "create")
    perm_edit = has_permission(user.id, "period", "edit")
    perm_reopen = has_permission(user.id, "period", "reopen")

    create_drawer_open = request.args.get("drawer") == "create" and perm_create

    sites = Site.query.filter_by(is_deleted=False).order_by(Site.name.asc()).all()
    periods = list_periods(site_id=filter_site_id, status=filter_status)
    site_map = {site.id: site for site in sites}

    today = date.today()
    years = list(range(today.year - 2, today.year + 2))

    return render_template(
        "modules/PERIOD/periods.html",
        module_code=MODULE_CODE,
        periods=periods,
        sites=sites,
        site_map=site_map,
        filter_site_id=filter_site_id,
        filter_status=filter_status,
        create_drawer_open=create_drawer_open,
        valid_statuses=VALID_STATUSES,
        valid_transitions=VALID_TRANSITIONS,
        transition_labels=TRANSITION_LABELS,
        status_labels=STATUS_LABELS,
        month_names=MONTH_NAMES,
        years=years,
        current_year=today.year,
        current_month=today.month,
        perm_create=perm_create,
        perm_edit=perm_edit,
        perm_reopen=perm_reopen,
    )


@bp.route("/create", methods=["POST"])
@require_permission("period", "create")
def create():
    actor = current_user()
    try:
        create_period(
            site_id=request.form.get("site_id", type=int),
            year=request.form.get("year"),
            month=request.form.get("month"),
            deadline=request.form.get("deadline"),
            actor_id=actor.id,
        )
        db.session.commit()
        flash("Reporting period opened.", "success")
        return redirect(url_for("period.index"))
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not open reporting period.", "error")
    return redirect(url_for("period.index", drawer="create"))


@bp.route("/<int:period_id>/transition", methods=["POST"])
@require_permission("period", ("edit", "reopen"))
def transition(period_id):
    actor = current_user()
    target_status = (request.form.get("target_status") or "").strip()
    reopen_reason = request.form.get("reopen_reason")

    required_action = TRANSITION_ACTION.get(target_status)
    if not required_action or not has_permission(actor.id, "period", required_action):
        flash("You do not have permission for this transition.", "error")
        return redirect(url_for("period.index"))

    try:
        transition_period(
            period_id=period_id,
            target_status=target_status,
            actor_id=actor.id,
            reopen_reason=reopen_reason,
        )
        db.session.commit()
        flash("Status updated.", "success")
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not update period status.", "error")
    return redirect(url_for("period.index"))
