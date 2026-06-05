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


def list_audit_logs(limit=100):
    return (
        AuditLog.query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .all()
    )
