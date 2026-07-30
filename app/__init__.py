from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlalchemy import text

from app.common.auth import current_user
from app.config import Config
from app.database import db
from app.modules.ACCESS import bp as access_bp
from app.modules.ACCESS.model import AccessMatrix
from app.modules.APPROV import bp as approv_bp
from app.modules.AUDITL import bp as auditl_bp
from app.modules.FORMBLD import bp as formbld_bp
from app.modules.FRMULA import bp as frmula_bp
from app.modules.NOTIFY import bp as notify_bp
from app.modules.PERIOD import bp as period_bp
from app.modules.RPTBLD import bp as rptbld_bp
from app.modules.SITEMST import bp as sitemst_bp
from app.modules.SUBMIT import bp as submit_bp
from app.modules.USRMGMT import auth_bp
from app.modules.VALSET import bp as valset_bp
from app.modules.WFLWBLD import bp as wflwbld_bp
from app.modules.WKBK import bp as wkbk_bp


MODULE_BLUEPRINTS = [
    access_bp,
    sitemst_bp,
    formbld_bp,
    frmula_bp,
    valset_bp,
    wflwbld_bp,
    submit_bp,
    approv_bp,
    rptbld_bp,
    auditl_bp,
    notify_bp,
    period_bp,
    wkbk_bp,
]


def create_app(config_class=Config):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_class)

    db.init_app(app)

    @app.template_filter("local_datetime")
    def local_datetime(value):
        if value is None:
            return "Never"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        local_value = value.astimezone(ZoneInfo("Asia/Kolkata"))
        return local_value.strftime("%d %b %Y, %I:%M %p IST")

    @app.template_filter("compact_local_datetime")
    def compact_local_datetime(value):
        if value is None:
            return "Never"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        local_value = value.astimezone(ZoneInfo("Asia/Kolkata"))
        return local_value.strftime("%d %b %Y, %I:%M %p")

    for blueprint in MODULE_BLUEPRINTS:
        app.register_blueprint(blueprint)

    app.register_blueprint(auth_bp)

    @app.after_request
    def disable_app_page_caching(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.context_processor
    def inject_auth_context():
        user = current_user()
        return {
            "current_user": user,
            "nav_items": build_nav_items(user),
        }

    @app.route("/")
    def index():
        user = current_user()
        if user is None:
            return redirect(url_for("auth.login"))
        return redirect(default_landing_url(user))

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/db-health")
    def db_health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"database": "connected"})
        except Exception as error:
            return jsonify({"database": "unavailable", "error": str(error)}), 503

    @app.route("/no-access")
    def no_access():
        return render_template("no_access.html"), 403

    with app.app_context():
        from app.modules.NOTIFY.service import seed_default_notification_configs
        from sqlalchemy import inspect
        try:
            if inspect(db.engine).has_table("notification_configs"):
                seed_default_notification_configs()
        except Exception as e:
            app.logger.warning(f"Failed to seed default notifications: {e}")

    return app


def user_can(user, entity_type, *actions):
    if not user:
        return False
    return any(user_has_access(user, entity_type, action) for action in actions)


def user_has_access(user, entity_type, action):
    if not user:
        return False
    flag = f"can_{action}"
    if action == "manage_forms":
        flag = "can_manage_forms"
    elif action == "manage_users":
        flag = "can_manage_users"
    if not hasattr(AccessMatrix, flag):
        return False
    return AccessMatrix.query.filter(
        AccessMatrix.user_id == user.id,
        AccessMatrix.entity_type == entity_type,
        AccessMatrix.is_deleted == False,
        getattr(AccessMatrix, flag) == True,
    ).first() is not None


def _submitter_site_count(user_id):
    """
    Number of sites this user actually has a live, assigned workbook to
    submit into (AccessMatrix scope intersected with a real
    WorkbookSiteSubmitter row) -- the same check my_sheets uses to pick its
    single-site vs multi-site layout. Distinct from the "submission" entity's
    can_view/can_create/can_edit/can_submit AccessMatrix flags, which a
    reviewer can also hold (they need can_view to see what they're
    approving) without ever being assigned a workbook.
    """
    from app.modules.SUBMIT.service import get_annual_workbook_options
    return len(get_annual_workbook_options(user_id).get("sites") or [])


def build_user_capabilities(user):
    can_contribute = user_can(user, "submission", "view", "create", "edit", "submit")
    can_review = user_can(user, "submission", "approve", "reject")
    can_manage_setup = any((
        user_can(user, "user", "manage_users", "view"),
        user_can(user, "site", "create", "edit", "delete"),
        user_can(user, "form", "manage_forms"),
        user_can(user, "value_set", "manage_forms"),
        user_can(user, "formula", "manage_forms"),
        user_can(user, "workflow", "manage_forms"),
        user_can(user, "period", "create", "edit", "reopen"),
    ))
    can_view_reports = user_can(user, "report", "view", "export")
    return {
        "can_contribute": can_contribute,
        "can_review": can_review,
        "can_manage_setup": can_manage_setup,
        "can_view_reports": can_view_reports,
    }


def default_landing_url(user):
    """
    Where a logged-in user should land with no more specific destination in
    play (root "/", and straight after login -- both call this so the two
    entry points can't drift apart). Contributor-with-an-actual-workbook
    wins if a user somehow has both (matches the one such account in
    current data, the global admin seed user); a reviewer-only user (no
    workbook assignment) goes straight to Review Queue instead of an empty
    My Workbooks dashboard.
    """
    caps = build_user_capabilities(user)
    if caps["can_contribute"] and _submitter_site_count(user.id) > 0:
        return url_for("submit.index")
    elif caps["can_review"]:
        return url_for("approv.index")
    else:
        return url_for("submit.index")


def human_status(status):
    return {
        "Approved": "Approved and locked",
        "Draft": "Draft saved",
        "Changes Requested": "Needs correction",
        "Rejected": "Sent back",
        "Resubmitted": "Sent again for review",
        "Under Review": "Under review",
        "Submitted": "Submitted",
        "Partially Submitted": "Partially submitted",
        "Ready for Review": "Ready for review",
        "Not Started": "Not started",
    }.get(status, status or "Unknown")


def build_nav_items(user):
    if not user:
        return []

    capabilities = build_user_capabilities(user)
    # A single-site contributor's "/module/SUBMIT/" now redirects straight
    # into their one workbook rather than a dashboard -- a nav item pointing
    # at a dashboard that no longer renders for them would be redundant, so
    # it's dropped for that case only. Multi-site users keep it unchanged.
    # A user with zero assigned sites (e.g. a reviewer who only has can_view
    # on "submission" to see what they're approving, never a workbook
    # assignment) has nothing behind that link at all, so it's dropped too.
    has_submitter_sites = False
    single_site_only = False
    if capabilities["can_contribute"]:
        site_count = _submitter_site_count(user.id)
        has_submitter_sites = site_count > 0
        single_site_only = site_count == 1

    groups = [
        {
            "label": None,
            "items": [
                {
                    "label": "My Workbooks",
                    "href": "/module/SUBMIT/",
                    "visible": capabilities["can_contribute"] and has_submitter_sites and not single_site_only,
                },
                {
                    "label": "Review Queue",
                    "href": "/module/APPROV/",
                    "visible": capabilities["can_review"],
                },
                {
                    "label": "Notifications",
                    "href": "/module/NOTIFY/",
                    "visible": user_can(user, "notification", "view"),
                },
            ],
        },
        {
            "label": "Setup",
            "items": [
                {
                    "label": "People",
                    "href": "/module/ACCESS/",
                    "visible": capabilities["can_manage_setup"] and user_can(user, "user", "view", "manage_users"),
                },
                {
                    "label": "Sites",
                    "href": "/module/SITEMST/",
                    "visible": capabilities["can_manage_setup"] and user_can(user, "site", "view"),
                },
                {
                    "label": "Workbooks",
                    "href": "/workbooks/",
                    "visible": capabilities["can_manage_setup"] and user_can(user, "form", "manage_forms"),
                },
                {
                    "label": "Value Sets",
                    "href": "/module/VALSET/",
                    "visible": capabilities["can_manage_setup"] and user_can(user, "value_set", "view"),
                },
                {
                    "label": "Notification Config",
                    "href": "/module/NOTIFY/manager",
                    "visible": capabilities["can_manage_setup"] and user_can(user, "notification", "view"),
                },
            ],
        },
        {
            "label": "Operations",
            "items": [
                {
                    "label": "Reporting Periods",
                    "href": "/module/PERIOD/",
                    "visible": capabilities["can_manage_setup"] and user_can(user, "period", "view"),
                },
                {
                    "label": "Reports",
                    "href": "/module/RPTBLD/",
                    "visible": capabilities["can_manage_setup"] or capabilities["can_view_reports"],
                },
                {
                    "label": "Audit Log",
                    "href": "/module/AUDITL/",
                    "visible": user_can(user, "audit", "view"),
                },
            ],
        },
    ]
    visible_groups = []
    for group in groups:
        items = [item for item in group["items"] if item["visible"]]
        if items:
            visible_groups.append({"label": group["label"], "items": items})
    return visible_groups
