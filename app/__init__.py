from flask import Flask, jsonify, redirect, render_template
from sqlalchemy import text

from app.common.auth import current_user, require_login
from app.common.permissions import has_permission
from app.config import Config
from app.database import db
from app.modules.ACCESS import bp as access_bp
from app.modules.APPROV import bp as approv_bp
from app.modules.AUDITL import bp as auditl_bp
from app.modules.FORMBLD import bp as formbld_bp
from app.modules.FRMULA import bp as frmula_bp
from app.modules.NOTIFY import bp as notify_bp
from app.modules.PERIOD import bp as period_bp
from app.modules.RPTBLD import bp as rptbld_bp
from app.modules.SITEMST import bp as sitemst_bp
from app.modules.SUBMIT import bp as submit_bp
from app.modules.USRMGMT import auth_bp, bp as usrmgmt_bp
from app.modules.VALSET import bp as valset_bp
from app.modules.WFLWBLD import bp as wflwbld_bp


MODULE_BLUEPRINTS = [
    access_bp,
    usrmgmt_bp,
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
]


def create_app(config_class=Config):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_class)

    db.init_app(app)

    for blueprint in MODULE_BLUEPRINTS:
        app.register_blueprint(blueprint)

    app.register_blueprint(auth_bp)

    @app.context_processor
    def inject_auth_context():
        user = current_user()
        return {
            "current_user": user,
            "nav_items": build_nav_items(user),
        }

    @app.route("/")
    def index():
        return redirect("/dashboard")

    @app.route("/dashboard")
    @require_login
    def dashboard():
        user = current_user()
        return render_template(
            "dashboard.html",
            dashboard_cards=build_dashboard_cards(user),
        )

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

    return app


def user_can(user, entity_type, *actions):
    if not user:
        return False
    return any(has_permission(user.id, entity_type, action) for action in actions)


def build_nav_items(user):
    if not user:
        return []

    items = [
        {"label": "Dashboard", "href": "/dashboard", "visible": True},
        {
            "label": "Users & Access",
            "href": "/module/ACCESS/",
            "visible": user_can(user, "user", "manage_users"),
        },
        {
            "label": "Users",
            "href": "/module/USRMGMT/",
            "visible": user_can(user, "user", "manage_users"),
        },
        {
            "label": "Sites",
            "href": "/module/SITEMST/",
            "visible": user_can(user, "site", "view"),
        },
        {
            "label": "Form Builder",
            "href": "/module/FORMBLD/",
            "visible": user_can(user, "form", "manage_forms"),
        },
        {
            "label": "Formula Builder",
            "href": "/module/FRMULA/",
            "visible": user_can(user, "formula", "view"),
        },
        {
            "label": "Value Sets",
            "href": "/module/VALSET/",
            "visible": user_can(user, "value_set", "view"),
        },
        {
            "label": "Workflow Builder",
            "href": "/module/WFLWBLD/",
            "visible": user_can(user, "workflow", "view"),
        },
        {
            "label": "My Sheets",
            "href": "/module/SUBMIT/",
            "visible": user_can(user, "submission", "submit", "view")
            or user_can(user, "form", "view"),
        },
        {
            "label": "Review Queue",
            "href": "/module/APPROV/",
            "visible": user_can(user, "submission", "approve", "reject"),
        },
        {
            "label": "Reports",
            "href": "/module/RPTBLD/",
            "visible": user_can(user, "report", "export", "view"),
        },
        {
            "label": "Audit Log",
            "href": "/module/AUDITL/",
            "visible": user_can(user, "audit_log", "view"),
        },
        {
            "label": "Notifications",
            "href": "/module/NOTIFY/",
            "visible": user_can(user, "notification", "view"),
        },
        {
            "label": "Periods",
            "href": "/module/PERIOD/",
            "visible": user_can(user, "reporting_period", "view"),
        },
    ]
    return [item for item in items if item["visible"]]


def build_dashboard_cards(user):
    cards = [
        {
            "title": "My Sheets",
            "href": "/module/SUBMIT/",
            "description": "Monthly site submissions available to you.",
            "visible": user_can(user, "submission", "submit", "view")
            or user_can(user, "form", "view"),
        },
        {
            "title": "Review Queue",
            "href": "/module/APPROV/",
            "description": "Submissions waiting for review action.",
            "visible": user_can(user, "submission", "approve", "reject"),
        },
        {
            "title": "Users & Access",
            "href": "/module/ACCESS/",
            "description": "Permission matrix and user access foundation.",
            "visible": user_can(user, "user", "manage_users"),
        },
        {
            "title": "Form Builder",
            "href": "/module/FORMBLD/",
            "description": "Form configuration area for authorized users.",
            "visible": user_can(user, "form", "manage_forms"),
        },
        {
            "title": "Reports",
            "href": "/module/RPTBLD/",
            "description": "Report exports and reporting templates.",
            "visible": user_can(user, "report", "export", "view"),
        },
    ]
    return [card for card in cards if card["visible"]]
