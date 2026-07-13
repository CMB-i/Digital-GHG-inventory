from collections import defaultdict
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
    TRANSITION_LABELS,
    VALID_STATUSES,
    VALID_TRANSITIONS,
    bulk_open_month,
    bulk_transition_periods,
    create_period,
    get_period,
    list_periods,
    required_transition_action,
    sort_period_group,
    transition_period,
)
from app.modules.SITEMST.model import Site
from app.modules.NOTIFY.service import notify_period_open_for_entry


MODULE_CODE = "PERIOD"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


def _period_filter_args(source=None):
    source = source or request.args
    site_id = source.get("site_id", type=int)
    status = (source.get("status") or "").strip()
    sort = (source.get("sort") or "").strip()
    sort_dir = (source.get("dir") or "").strip().lower()
    args = {}
    if site_id:
        args["site_id"] = site_id
    if status in VALID_STATUSES:
        args["status"] = status
    if sort == "updated_at":
        args["sort"] = sort
        args["dir"] = sort_dir if sort_dir in ("asc", "desc") else "desc"
    return args


@bp.route("/")
@require_permission("period", "view")
def index():
    filter_site_id = request.args.get("site_id", type=int)
    filter_status = (request.args.get("status") or "").strip() or None

    if filter_status not in VALID_STATUSES:
        filter_status = None

    sort_by = (request.args.get("sort") or "").strip()
    if sort_by != "updated_at":
        sort_by = None
    sort_dir = (request.args.get("dir") or "").strip().lower()
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    user = current_user()
    perm_create = has_permission(user.id, "period", "create")
    perm_edit = has_permission(user.id, "period", "edit")
    perm_reopen = has_permission(user.id, "period", "reopen")

    create_drawer_open = request.args.get("drawer") == "create" and perm_create

    sites = Site.query.filter_by(is_deleted=False).order_by(Site.name.asc()).all()
    site_map = {site.id: site for site in sites}
    all_active_site_ids = {site.id for site in sites}

    periods = list_periods(site_id=filter_site_id, status=filter_status)

    # Need unfiltered data to accurately compute how many sites are missing a period
    # per month (used for the bulk-open button).
    if filter_site_id or filter_status:
        all_periods = list_periods()
    else:
        all_periods = periods

    existing_per_month = defaultdict(set)
    for p in all_periods:
        existing_per_month[(p.year, p.month)].add(p.site_id)

    # Group display periods by (year, month), sort months descending.
    grouped = defaultdict(list)
    for period in periods:
        grouped[(period.year, period.month)].append(period)

    month_groups = []
    for year_key, month_key in sorted(grouped.keys(), reverse=True):
        month_periods = grouped[(year_key, month_key)]
        sort_period_group(month_periods, site_map, sort_by=sort_by, sort_dir=sort_dir)

        status_counts = defaultdict(int)
        for p in month_periods:
            status_counts[p.status] += 1

        existing_sites = existing_per_month.get((year_key, month_key), set())
        missing_count = len(all_active_site_ids - existing_sites)

        month_groups.append({
            "year": year_key,
            "month": month_key,
            "month_name": MONTH_NAMES[month_key],
            "periods": month_periods,
            "status_counts": dict(status_counts),
            "can_bulk_open": missing_count > 0,
            "missing_count": missing_count,
        })

    today = date.today()
    years = list(range(today.year - 2, today.year + 2))

    next_sort_dir = "asc" if (sort_by == "updated_at" and sort_dir == "desc") else "desc"
    last_updated_sort_args = dict(_period_filter_args())
    last_updated_sort_args.update(sort="updated_at", dir=next_sort_dir)
    last_updated_sort_url = url_for("period.index", **last_updated_sort_args)

    return render_template(
        "modules/PERIOD/periods.html",
        module_code=MODULE_CODE,
        period_filter_args=_period_filter_args(),
        month_groups=month_groups,
        sites=sites,
        site_map=site_map,
        filter_site_id=filter_site_id,
        filter_status=filter_status,
        sort_by=sort_by,
        sort_dir=sort_dir,
        last_updated_sort_url=last_updated_sort_url,
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
        bulk_transition_url=url_for("period.bulk_transition", **_period_filter_args()),
    )


@bp.route("/create", methods=["POST"])
@require_permission("period", "create")
def create():
    actor = current_user()
    try:
        period = create_period(
            site_id=request.form.get("site_id", type=int),
            year=request.form.get("year"),
            month=request.form.get("month"),
            deadline=request.form.get("deadline"),
            actor_id=actor.id,
        )
        db.session.flush()
        notify_period_open_for_entry(period.id)
        db.session.commit()
        flash("Reporting period opened.", "success")
        return redirect(url_for("period.index", **_period_filter_args()))
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not open reporting period.", "error")
    return redirect(url_for("period.index", drawer="create", **_period_filter_args()))


@bp.route("/bulk-open", methods=["POST"])
@require_permission("period", "create")
def bulk_open_periods():
    actor = current_user()
    year = request.form.get("year", type=int)
    month = request.form.get("month", type=int)

    if not year or not month or not (1 <= month <= 12) or not (2000 <= year <= 2100):
        flash("Invalid reporting month.", "error")
        return redirect(url_for("period.index", **_period_filter_args()))

    sites = Site.query.filter_by(is_deleted=False).all()
    site_ids = [s.id for s in sites]

    try:
        created = bulk_open_month(year=year, month=month, actor_id=actor.id, site_ids=site_ids)
        db.session.flush()
        for period in created:
            notify_period_open_for_entry(period.id)
        db.session.commit()
        if created:
            flash(
                f"Opened {len(created)} reporting period(s) for "
                f"{MONTH_NAMES.get(month, month)} {year}.",
                "success",
            )
        else:
            flash("All active sites already have a period for this month.", "info")
    except Exception:
        db.session.rollback()
        flash("Could not open reporting periods.", "error")

    return redirect(url_for("period.index", **_period_filter_args()))


@bp.route("/<int:period_id>/transition", methods=["POST"])
@require_permission("period", ("edit", "reopen"))
def transition(period_id):
    actor = current_user()
    target_status = (request.form.get("target_status") or "").strip()
    reopen_reason = request.form.get("reopen_reason")

    # required_transition_action needs the period's CURRENT status too, since
    # LOCKED -> OPEN (reopen) and everything else -> OPEN can no longer be
    # told apart by target_status alone.
    existing_period = get_period(period_id)
    if existing_period:
        required_action = required_transition_action(existing_period.status, target_status)
        if not required_action or not has_permission(actor.id, "period", required_action):
            flash("You do not have permission for this transition.", "error")
            return redirect(url_for("period.index", **_period_filter_args()))

    try:
        period = transition_period(
            period_id=period_id,
            target_status=target_status,
            actor_id=actor.id,
            reopen_reason=reopen_reason,
        )
        if period.status == "OPEN":
            notify_period_open_for_entry(period.id)
        db.session.commit()
        flash("Status updated.", "success")
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "error")
    except Exception:
        db.session.rollback()
        flash("Could not update period status.", "error")
    return redirect(url_for("period.index", **_period_filter_args()))


def _bulk_transition_message(target_status, results):
    succeeded = len(results["succeeded"])
    skipped = len(results["skipped"])
    failed = len(results["failed"])
    label = STATUS_LABELS.get(target_status, target_status)

    parts = [f"{succeeded} updated to {label}"]
    if skipped:
        parts.append(f"{skipped} skipped")
    if failed:
        parts.append(f"{failed} failed")
    message = ", ".join(parts) + "."

    if failed:
        category = "error"
    elif succeeded:
        category = "success"
    else:
        category = "info"
    return message, category


@bp.route("/bulk-transition", methods=["POST"])
@require_permission("period", ("edit", "reopen"))
def bulk_transition():
    actor = current_user()
    target_status = (request.form.get("target_status") or "").strip()
    reopen_reason = request.form.get("reopen_reason")
    period_ids = [pid for pid in request.form.getlist("period_ids", type=int) if pid]

    if not period_ids:
        flash("No reporting periods were selected.", "error")
        return redirect(url_for("period.index", **_period_filter_args()))

    if target_status not in VALID_STATUSES:
        flash("Invalid target status.", "error")
        return redirect(url_for("period.index", **_period_filter_args()))

    # Permission can't be pre-checked here anymore: it depends on each
    # period's own current status (required_transition_action), and a single
    # batch can mix current statuses even though they share one target_status.
    # bulk_transition_periods does that check per period and buckets anyone
    # not permitted into "skipped" instead of silently proceeding.
    if target_status == "OPEN" and not (reopen_reason or "").strip():
        flash("A reopen reason is required.", "error")
        return redirect(url_for("period.index", **_period_filter_args()))

    try:
        results = bulk_transition_periods(
            period_ids=period_ids,
            target_status=target_status,
            actor_id=actor.id,
            reopen_reason=reopen_reason,
        )
        for period in results["succeeded"]:
            if period.status == "OPEN":
                notify_period_open_for_entry(period.id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Could not process bulk update.", "error")
        return redirect(url_for("period.index", **_period_filter_args()))

    message, category = _bulk_transition_message(target_status, results)
    flash(message, category)
    return redirect(url_for("period.index", **_period_filter_args()))
