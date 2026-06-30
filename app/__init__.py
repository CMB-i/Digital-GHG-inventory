from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlalchemy import text

from app.common.auth import current_user, require_login
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
from app.modules.WKBK import bp as wkbk_bp
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
        caps = build_user_capabilities(user)
        if caps["can_contribute"]:
            return redirect(url_for("submit.index"))
        elif caps["can_review"]:
            return redirect(url_for("approv.index"))
        else:
            return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @require_login
    def dashboard():
        user = current_user()

        from app.modules.RPTBLD.service import _get_user_allowed_sites, get_missing_submissions
        from app.modules.FORMBLD.model import Form
        from app.modules.APPROV.service import get_approver_queue, get_actioned_history
        from app.modules.SUBMIT.service import get_spoc_sheets_buckets, human_sheet_label

        capabilities = build_user_capabilities(user)
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

        missing_submissions = get_missing_submissions(user.id) if (
            capabilities["can_manage_setup"] or capabilities["can_view_reports"]
        ) else []
        actual_missing = [
            item
            for item in missing_submissions
            if item["status"] in ("Not Started", "Draft", "Changes Requested")
        ]
        for item in actual_missing:
            item["status_text"] = human_status(item["status"])
        missing_sheets_count = len(actual_missing)

        recent_submissions = []
        if allowed_site_ids:
            recent_query = Submission.query.filter(
                Submission.site_id.in_(list(allowed_site_ids)),
                Submission.is_deleted == False
            )
            if capabilities["can_contribute"] and not (
                capabilities["can_review"] or capabilities["can_manage_setup"]
            ):
                recent_query = recent_query.filter(Submission.submitted_by == user.id)
            recent_submissions = recent_query.order_by(Submission.updated_at.desc()).limit(5).all()

        sites_map = {s.id: s.name for s in Site.query.filter_by(is_deleted=False).all()}
        forms_map = {f.id: human_sheet_label(f) for f in Form.query.filter_by(is_deleted=False).all()}

        recent_activities = []
        for sub in recent_submissions:
            recent_activities.append({
                "id": sub.id,
                "site_name": sites_map.get(sub.site_id, "Unknown"),
                "sheet_name": forms_map.get(sub.form_id, "Unknown sheet"),
                "updated_at": sub.updated_at,
                "status": sub.status,
                "status_text": human_status(sub.status),
            })

        metrics = {
            "total_sheets": total_sheets,
            "approved_sheets": approved_sheets,
            "awaiting_review": awaiting_review,
            "missing_sheets": missing_sheets_count
        }

        my_work_items = []
        if capabilities["can_contribute"]:
            sheet_buckets = get_spoc_sheets_buckets(user.id)
            my_work_items.extend(
                dashboard_sheet_item(item, "Continue workbook")
                for item in sheet_buckets.get("action_needed", [])
            )
            my_work_items.extend(
                dashboard_sheet_item(item, "Start sheet")
                for item in sheet_buckets.get("not_started", [])
            )
            my_work_items.extend(
                dashboard_sheet_item(item, "View submitted sheet")
                for item in sheet_buckets.get("submitted", [])[:3]
            )
            my_work_items = my_work_items[:8]

        review_queue = []
        review_history = []
        if capabilities["can_review"]:
            review_queue = [dashboard_review_item(item) for item in get_approver_queue(user.id)[:8]]
            review_history = [
                {
                    "site_name": item["site_name"],
                    "period_label": item["period_label"],
                    "sheet_name": item["form_name"],
                    "status_text": item.get("current_status_text") or human_status(item["current_status"]),
                    "acted_at": item["acted_at"],
                    "href": (
                        f"/module/APPROV/packages/{item['package_id']}"
                        if item.get("package_id") else
                        f"/module/APPROV/submissions/{item['submission_id']}"
                    ),
                }
                for item in get_actioned_history(user.id)[:5]
            ]

        return render_template(
            "dashboard.html",
            capabilities=capabilities,
            dashboard_cards=build_dashboard_cards(user),
            setup_checklist=build_setup_checklist() if capabilities["can_manage_setup"] else [],
            metrics=metrics,
            my_work_items=my_work_items,
            review_queue=review_queue,
            review_history=review_history,
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


def dashboard_sheet_item(item, action_label):
    fy_start = item["year"] if item["month"] >= 4 else item["year"] - 1
    href = (
        f"/module/SUBMIT/annual?site_id={item['site_id']}"
        f"&form_id={item['form_id']}&fy={fy_start}&month={item['month']}"
    )
    return {
        "site_name": item["site_name"],
        "period_label": item["period_label"],
        "sheet_name": item["form_name"],
        "status": item.get("status", "Not Started"),
        "status_text": human_status(item.get("status", "Not Started")),
        "action_label": action_label,
        "href": href,
    }


def dashboard_review_item(item):
    included = item.get("included_submissions", [])
    submitted_statuses = ("Submitted", "Resubmitted", "Under Review", "Approved")
    submitted_count = len([
        sub for sub in included if sub.get("status") in submitted_statuses
    ]) if included else item.get("included_submission_count")
    waiting_on = ", ".join(
        sub["form_name"] for sub in included if sub.get("status") not in submitted_statuses
    )
    package_status = item["status"]
    if item.get("item_type") == "package" and included:
        package_status = "Ready for Review" if not waiting_on else "Partially Submitted"
    return {
        "site_name": item["site_name"],
        "period_label": item["period_label"],
        "status": package_status,
        "status_text": human_status(package_status),
        "submitted_count": submitted_count,
        "sheet_count": len(included) if included else item.get("included_submission_count"),
        "waiting_on": waiting_on,
        "action_label": "Review package" if item.get("is_my_turn") else "View package",
        "href": (
            f"/module/APPROV/packages/{item['package_id']}"
            if item.get("item_type") == "package" and item.get("package_id") else
            f"/module/APPROV/submissions/{item['submission_id']}"
        ),
    }


def build_nav_items(user):
    if not user:
        return []

    capabilities = build_user_capabilities(user)
    groups = [
        {
            "label": None,
            "items": [{"label": "Home", "href": "/dashboard", "visible": True}],
        },
        {
            "label": None,
            "items": [
                {
                    "label": "My Workbooks",
                    "href": "/module/SUBMIT/",
                    "visible": capabilities["can_contribute"],
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
                    "label": "Workflow Paths",
                    "href": "/module/WFLWBLD/",
                    "visible": capabilities["can_manage_setup"] and user_can(user, "workflow", "view"),
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


def build_dashboard_cards(user):
    capabilities = build_user_capabilities(user)
    cards = [
        {
            "title": "People",
            "href": "/module/ACCESS/",
            "description": "Add and manage users who contribute, review, or manage reporting.",
            "visible": capabilities["can_manage_setup"] and user_can(user, "user", "manage_users"),
        },
        {
            "title": "Sites",
            "href": "/module/SITEMST/",
            "description": "Manage ports and sites included in GHG reporting.",
            "visible": capabilities["can_manage_setup"] and user_can(user, "site", "view"),
        },
        {
            "title": "Workbooks",
            "href": "/workbooks/",
            "description": "Build reusable workbook and sheet structures for site reporting.",
            "visible": capabilities["can_manage_setup"] and user_can(user, "form", "manage_forms"),
        },
        {
            "title": "Workflow Paths",
            "href": "/module/WFLWBLD/",
            "description": "Configure who reviews and approves each site monthly package.",
            "visible": capabilities["can_manage_setup"] and user_can(user, "workflow", "view"),
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
            "People and access configured",
            User.query.filter_by(is_deleted=False).count() > 0
            and AccessMatrix.query.filter_by(is_deleted=False).count() > 0,
        ),
        ("Sites ready", Site.query.filter_by(is_deleted=False).count() > 0),
        (
            "Reporting months opened",
            ReportingPeriod.query.filter_by(is_deleted=False, status="OPEN").count() > 0,
        ),
        (
            "Value Sets approved",
            ValueSetVersion.query.filter_by(status="Approved").count() > 0,
        ),
        (
            "Formula Builder rules published",
            FormulaVersion.query.filter(FormulaVersion.published_at.is_not(None)).count() > 0,
        ),
        (
            "Sheets configured",
            FormVersion.query.filter(FormVersion.published_at.is_not(None)).count() > 0,
        ),
        (
            "Workflow Paths assigned",
            WorkflowLevelApprover.query.filter_by(is_deleted=False).count() > 0,
        ),
        (
            "Approved monthly package available",
            Submission.query.filter_by(is_deleted=False, status="Approved").count() > 0,
        ),
    ]
    return [{"label": label, "done": done} for label, done in checks]
