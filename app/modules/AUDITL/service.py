import json
from datetime import date, datetime

from app.database import db
from app.modules.AUDITL.model import AuditLog


def _json_safe(value):
    if value is None:
        return None
    return json.loads(json.dumps(value, default=_json_default))


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def log_audit(
    actor_user_id,
    entity_type,
    entity_id,
    action,
    old_values=None,
    new_values=None,
    metadata=None,
    ip_address=None,
    user_agent=None,
):
    audit_log = AuditLog(
        actor_user_id=actor_user_id,
        entity_type=str(entity_type),
        entity_id=str(entity_id) if entity_id is not None else None,
        action=str(action),
        old_values=_json_safe(old_values),
        new_values=_json_safe(new_values),
        metadata_json=_json_safe(metadata),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.session.add(audit_log)
    return audit_log


def resolve_entity_details(entity_type, entity_id):
    if not entity_id:
        return entity_type

    try:
        if entity_type == "submission":
            from app.modules.SUBMIT.model import Submission
            from app.modules.FORMBLD.model import Form
            from app.modules.SITEMST.model import Site
            from app.modules.PERIOD.model import ReportingPeriod
            from app.modules.WKBK.model import Workbook, WorkbookSite

            sub = db.session.get(Submission, int(entity_id)) if entity_id.isdigit() else None
            if sub:
                form = db.session.get(Form, sub.form_id)
                site = db.session.get(Site, sub.site_id)
                period = db.session.get(ReportingPeriod, sub.reporting_period_id)
                
                workbook = (
                    db.session.query(Workbook)
                    .join(WorkbookSite, WorkbookSite.workbook_id == Workbook.id)
                    .filter(WorkbookSite.site_id == sub.site_id, WorkbookSite.is_deleted == False, Workbook.is_active == True)
                    .first()
                )
                
                parts = []
                if workbook:
                    parts.append(f"Workbook: {workbook.name}")
                if form:
                    parts.append(f"Sheet: {form.name}")
                if site:
                    parts.append(f"Site: {site.name}")
                if period:
                    from app.modules.SUBMIT.service import format_period_label
                    parts.append(f"Period: {format_period_label(period.year, period.month)}")
                
                details = ", ".join(parts)
                return f"Submission #{entity_id} ({details})" if details else f"Submission #{entity_id}"
                
        elif entity_type == "submission_package":
            from app.modules.SUBMIT.model import SubmissionPackage
            from app.modules.SITEMST.model import Site
            from app.modules.PERIOD.model import ReportingPeriod
            from app.modules.WKBK.model import Workbook, WorkbookSite

            package = db.session.get(SubmissionPackage, int(entity_id)) if entity_id.isdigit() else None
            if package:
                site = db.session.get(Site, package.site_id)
                period = db.session.get(ReportingPeriod, package.period_id)
                workbook = (
                    db.session.query(Workbook)
                    .join(WorkbookSite, WorkbookSite.workbook_id == Workbook.id)
                    .filter(WorkbookSite.site_id == package.site_id, WorkbookSite.is_deleted == False, Workbook.is_active == True)
                    .first()
                )
                
                parts = []
                if workbook:
                    parts.append(f"Workbook: {workbook.name}")
                if site:
                    parts.append(f"Site: {site.name}")
                if period:
                    from app.modules.SUBMIT.service import format_period_label
                    parts.append(f"Period: {format_period_label(period.year, period.month)}")
                
                details = ", ".join(parts)
                return f"Submission Package #{entity_id} ({details})" if details else f"Submission Package #{entity_id}"

        elif entity_type == "user":
            from app.modules.USRMGMT.model import User
            user = db.session.get(User, int(entity_id)) if entity_id.isdigit() else None
            if user:
                return f"User #{entity_id} ({user.full_name}, {user.email})"

        elif entity_type == "site":
            from app.modules.SITEMST.model import Site
            site = db.session.get(Site, int(entity_id)) if entity_id.isdigit() else None
            if site:
                return f"Site #{entity_id} ({site.name}, Code: {site.code})"

        elif entity_type == "period":
            from app.modules.PERIOD.model import ReportingPeriod
            from app.modules.SITEMST.model import Site
            period = db.session.get(ReportingPeriod, int(entity_id)) if entity_id.isdigit() else None
            if period:
                site = db.session.get(Site, period.site_id)
                site_str = f", Site: {site.name}" if site else ""
                from app.modules.SUBMIT.service import format_period_label
                period_label = format_period_label(period.year, period.month)
                return f"Reporting Period #{entity_id} ({period_label}{site_str})"

        elif entity_type == "access_matrix":
            from app.modules.ACCESS.model import AccessMatrix
            from app.modules.USRMGMT.model import User
            from app.modules.SITEMST.model import Site
            matrix = db.session.get(AccessMatrix, int(entity_id)) if entity_id.isdigit() else None
            if matrix:
                user = db.session.get(User, matrix.user_id)
                site = db.session.get(Site, matrix.site_id) if matrix.site_id else None
                user_str = f"User: {user.full_name}" if user else f"User ID: {matrix.user_id}"
                site_str = f", Site: {site.name}" if site else ", Scope: Global"
                return f"Access Matrix Record #{entity_id} ({user_str}{site_str})"

    except Exception:
        pass

    # Fallback to simple format
    return f"{entity_type.replace('_', ' ').title()} #{entity_id}"


def list_audit_logs(limit=100):
    from app.modules.USRMGMT.model import User
    
    results = (
        db.session.query(AuditLog, User.full_name)
        .outerjoin(User, AuditLog.actor_user_id == User.id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    
    ACTION_LABELS = {
        "CREATE_DRAFT": "Created Draft Sheet",
        "SUBMIT": "Submitted Sheet",
        "APPROVE_LEVEL": "Approved Level",
        "FINAL_APPROVE": "Approved Sheet (Final)",
        "REQUEST_CHANGES": "Requested Changes",
        "REJECT": "Rejected Sheet",
        "SUBMIT_PACKAGE": "Submitted Workbook Package",
        "APPROVE_PACKAGE": "Approved Workbook Package",
        "RAISE_CELL_ISSUE": "Raised Issue on Cell",
        "ACCESS_UPDATED": "Updated Access Matrix",
        "PERIOD_STATUS_CHANGED": "Changed Period Status",
        "SITE_UPDATED": "Updated Site Master",
        "SITE_DEACTIVATED": "Deactivated Site",
        "SITE_REACTIVATED": "Reactivated Site",
        "USER_UPDATED": "Updated User Details",
        "USER_PASSWORD_RESET": "Reset User Password",
        "USER_ACTIVATED": "Activated User Account",
        "USER_DEACTIVATED": "Deactivated User Account",
    }

    logs = []
    for log, full_name in results:
        # 1. Actor Name
        if full_name:
            log.actor_name = f"{full_name} (ID: {log.actor_user_id})"
        else:
            log.actor_name = "System"
            
        # 2. Readable Action
        if log.action in ACTION_LABELS:
            log.readable_action = ACTION_LABELS[log.action]
        else:
            log.readable_action = log.action.replace("_", " ").title()
            
        # 3. Entity Details
        log.entity_details = resolve_entity_details(log.entity_type, log.entity_id)
        
        logs.append(log)
        
    return logs
