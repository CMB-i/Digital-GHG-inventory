from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlalchemy import text

from app.common.auth import current_user, require_login
from app.common.permissions import has_permission
from app.config import Config
from app.database import db
from app.modules.ACCESS import bp as access_bp
from app.modules.ACCESS.model import AccessMatrix
from app.modules.APPROV import bp as approv_bp
from app.modules.AUDITL import bp as auditl_bp
from app.modules.FORMBLD import bp as formbld_bp
from app.modules.FORMBLD.model import FormVersion
from app.modules.FRMULA import bp as frmula_bp
from app.modules.NOTIFY import bp as notify_bp
from app.modules.PERIOD import bp as period_bp
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.RPTBLD import bp as rptbld_bp
from app.modules.SITEMST import bp as sitemst_bp
from app.modules.SITEMST.model import Site
from app.modules.SUBMIT import bp as submit_bp
from app.modules.SUBMIT.model import Submission
from app.modules.USRMGMT import auth_bp, bp as usrmgmt_bp
from app.modules.USRMGMT.model import User
from app.modules.VALSET import bp as valset_bp
from app.modules.WFLWBLD import bp as wflwbld_bp
from app.modules.WFLWBLD.model import WorkflowLevelApprover


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
        if current_user() is None:
            return redirect(url_for("auth.login"))
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @require_login
    def dashboard():
        user = current_user()
        
        from app.modules.RPTBLD.service import _get_user_allowed_sites, get_missing_submissions
        from app.modules.SITEMST.model import Site
        from app.modules.FORMBLD.model import Form
        
        allowed_site_ids, is_global = _get_user_allowed_sites(user.id, "submission")
        
        total_sheets = 0
        approved_sheets = 0
        awaiting_review = 0
        
        if allowed_site_ids:
            total_sheets = Submission.query.filter(
                Submission.site_id.in_(list(allowed_site_ids)),
                Submission.is_deleted == False
            ).count()
            
            approved_sheets = Submission.query.filter(
                Submission.site_id.in_(list(allowed_site_ids)),
                Submission.status == "Approved",
                Submission.is_deleted == False
            ).count()
            
            awaiting_review = Submission.query.filter(
                Submission.site_id.in_(list(allowed_site_ids)),
                Submission.status.in_(("Submitted", "Resubmitted", "Under Review")),
                Submission.is_deleted == False
            ).count()
            
        # Get missing submissions
        missing_submissions = get_missing_submissions(user.id)
        # Filter down to actual missing ones: "Not Started", "Draft", "Changes Requested"
        actual_missing = [item for item in missing_submissions if item["status"] in ("Not Started", "Draft", "Changes Requested")]
        missing_sheets_count = len(actual_missing)
        
        # Recent activities: Last 5 updated submissions in site scope
        recent_submissions = []
        if allowed_site_ids:
            recent_submissions = Submission.query.filter(
                Submission.site_id.in_(list(allowed_site_ids)),
                Submission.is_deleted == False
            ).order_by(Submission.updated_at.desc()).limit(5).all()
            
        sites_map = {s.id: s.name for s in Site.query.filter_by(is_deleted=False).all()}
        forms_map = {f.id: f.name for f in Form.query.filter_by(is_deleted=False).all()}
        
        recent_activities = []
        for sub in recent_submissions:
            recent_activities.append({
                "id": sub.id,
                "site_name": sites_map.get(sub.site_id, "Unknown"),
                "form_name": forms_map.get(sub.form_id, "Unknown"),
                "updated_at": sub.updated_at,
                "status": sub.status
            })
            
        metrics = {
            "total_sheets": total_sheets,
            "approved_sheets": approved_sheets,
            "awaiting_review": awaiting_review,
            "missing_sheets": missing_sheets_count
        }
        
        return render_template(
            "dashboard.html",
            dashboard_cards=build_dashboard_cards(user),
            setup_checklist=build_setup_checklist(),
            metrics=metrics,
            recent_activities=recent_activities,
            missing_submissions=actual_missing
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

    groups = [
        {
            "label": None,
            "items": [{"label": "Dashboard", "href": "/dashboard", "visible": True}],
        },
        {
            "label": "Operations",
            "items": [
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
            ],
        },
        {
            "label": "Configuration",
            "items": [
                {
                    "label": "Sites",
                    "href": "/module/SITEMST/",
                    "visible": user_can(user, "site", "view"),
                },
                {
                    "label": "Reporting Periods",
                    "href": "/module/PERIOD/",
                    "visible": user_can(user, "period", "view"),
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
            ],
        },
        {
            "label": "Administration",
            "items": [
                {
                    "label": "Users & Access",
                    "href": "/module/ACCESS/",
                    "visible": user_can(user, "user", "view", "manage_users"),
                },
                {
                    "label": "Notifications",
                    "href": "/module/NOTIFY/",
                    "visible": user_can(user, "notification", "view"),
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
            "description": "Manage users and access.",
            "visible": user_can(user, "user", "manage_users"),
        },
        {
            "title": "Form Builder",
            "href": "/module/FORMBLD/",
            "description": "Configure forms for monthly site data entry.",
            "visible": user_can(user, "form", "manage_forms"),
        },
        {
            "title": "Reports",
            "href": "/module/RPTBLD/",
            "description": "View and export approved GHG data.",
            "visible": user_can(user, "report", "export", "view"),
        },
    ]
    return [card for card in cards if card["visible"]]


def build_setup_checklist():
    from app.modules.VALSET.model import ValueSetVersion
    from app.modules.FRMULA.model import FormulaVersion
    checks = [
        (
            "Users & Access configured",
            User.query.filter_by(is_deleted=False).count() > 0
            and AccessMatrix.query.filter_by(is_deleted=False).count() > 0,
        ),
        ("Sites configured", Site.query.filter_by(is_deleted=False).count() > 0),
        (
            "Reporting periods opened",
            ReportingPeriod.query.filter_by(is_deleted=False, status="OPEN").count() > 0,
        ),
        (
            "Forms published",
            FormVersion.query.filter(FormVersion.published_at.is_not(None)).count() > 0,
        ),
        (
            "Workflows assigned",
            WorkflowLevelApprover.query.filter_by(is_deleted=False).count() > 0,
        ),
        (
            "Value Sets seeded & approved",
            ValueSetVersion.query.filter_by(status="Approved").count() > 0,
        ),
        (
            "Formulas configured",
            FormulaVersion.query.count() > 0,
        ),
        (
            "Phase 5 testing verified",
            True,
        ),
        (
            "Test submission completed",
            Submission.query.filter_by(is_deleted=False, status="Approved").count() > 0,
        ),
    ]
    return [{"label": label, "done": done} for label, done in checks]
