from app.modules.ACCESS.model import AccessMatrix
from app.database import db
from app.common.validators import ValidationError, validate_code


PERMISSION_COLUMNS = (
    {"key": "can_view", "label": "View", "style": "read"},
    {"key": "can_create", "label": "Create", "style": "admin"},
    {"key": "can_edit", "label": "Edit", "style": "admin"},
    {"key": "can_delete", "label": "Delete", "style": "warning"},
    {"key": "can_submit", "label": "Submit", "style": "workflow"},
    {"key": "can_approve", "label": "Approve", "style": "workflow"},
    {"key": "can_reject", "label": "Reject", "style": "workflow"},
    {"key": "can_reopen", "label": "Reopen", "style": "workflow"},
    {"key": "can_export", "label": "Export", "style": "read"},
    {"key": "can_manage_forms", "label": "Manage Forms", "style": "admin"},
    {"key": "can_manage_users", "label": "Manage Users", "style": "warning"},
)

PERMISSION_FLAGS = tuple(column["key"] for column in PERMISSION_COLUMNS)
PERMISSION_LABELS = {column["key"]: column["label"] for column in PERMISSION_COLUMNS}


def empty_permissions():
    return {flag: False for flag in PERMISSION_FLAGS}


def get_user_permissions(
    user_id,
    scope_type=None,
    scope_site_id=None,
    entity_type=None,
    entity_id=None,
):
    permissions = empty_permissions()
    if not user_id:
        return permissions

    query = AccessMatrix.query.filter_by(user_id=user_id, is_deleted=False)

    if scope_type == "global":
        query = query.filter(AccessMatrix.scope_type == "global")
    elif scope_type == "site":
        query = query.filter(
            AccessMatrix.scope_type.in_(("global", "site")),
            (
                (AccessMatrix.scope_type == "global")
                | (AccessMatrix.scope_site_id == scope_site_id)
            ),
        )

    if entity_type:
        query = query.filter(
            (AccessMatrix.entity_type == entity_type)
            | (AccessMatrix.entity_type == "all")
        )

    if entity_id is not None:
        query = query.filter(
            (AccessMatrix.entity_id.is_(None))
            | (AccessMatrix.entity_id == entity_id)
        )

    requested_entity_flags = (
        SUPPORTED_PERMISSION_FLAGS.get(entity_type, set())
        if entity_type
        else set(PERMISSION_FLAGS)
    )
    for row in query.all():
        row_flags = SUPPORTED_PERMISSION_FLAGS.get(row.entity_type, set(PERMISSION_FLAGS))
        allowed_flags = row_flags & requested_entity_flags
        for flag in allowed_flags:
            permissions[flag] = permissions[flag] or bool(getattr(row, flag))

    return permissions


ENTITY_ROWS = (
    {"key": "user", "label": "Users"},
    {"key": "site", "label": "Sites"},
    {"key": "form", "label": "Forms"},
    {"key": "workflow", "label": "Workflows"},
    {"key": "submission", "label": "Submissions"},
    {"key": "report", "label": "Reports"},
    {"key": "period", "label": "Reporting Periods"},
    {"key": "value_set", "label": "Value Sets"},
    {"key": "formula", "label": "Formulas"},
    {"key": "notification", "label": "Notifications"},
    {"key": "audit", "label": "Audit"},
)

ENTITY_TYPES = tuple(row["key"] for row in ENTITY_ROWS)
ENTITY_LABELS = {row["key"]: row["label"] for row in ENTITY_ROWS}
ENTITY_CHIP_CATEGORIES = {
    "user": "admin",
    "site": "admin",
    "period": "admin",
    "form": "config",
    "formula": "config",
    "value_set": "config",
    "workflow": "config",
    "submission": "workflow",
    "report": "read",
    "audit": "read",
    "notification": "neutral",
    "all": "neutral",
}

SUPPORTED_PERMISSION_FLAGS = {
    "user": {"can_view", "can_create", "can_edit", "can_delete", "can_manage_users"},
    "site": {"can_view", "can_create", "can_edit", "can_delete", "can_export"},
    "form": {"can_view", "can_create", "can_edit", "can_delete", "can_export", "can_manage_forms"},
    "workflow": {"can_view", "can_create", "can_edit", "can_delete", "can_manage_forms"},
    "submission": {
        "can_view",
        "can_create",
        "can_edit",
        "can_delete",
        "can_submit",
        "can_approve",
        "can_reject",
        "can_reopen",
        "can_export",
    },
    "report": {"can_view", "can_create", "can_edit", "can_delete", "can_export"},
    "period": {"can_view", "can_create", "can_edit", "can_delete", "can_reopen"},
    "value_set": {"can_view", "can_create", "can_edit", "can_delete", "can_approve", "can_reject", "can_manage_forms"},
    "formula": {"can_view", "can_create", "can_edit", "can_delete", "can_manage_forms"},
    "notification": {"can_view"},
    "audit": {"can_view", "can_export"},
}


def sanitize_permission_values(entity_type, submitted_values):
    if entity_type not in ENTITY_TYPES:
        raise ValidationError("Invalid entity type.")

    allowed_flags = SUPPORTED_PERMISSION_FLAGS[entity_type]
    return {
        flag: bool(submitted_values.get(flag)) if flag in allowed_flags else False
        for flag in PERMISSION_FLAGS
    }


def list_access_rows(user_id=None):
    query = AccessMatrix.query.filter_by(is_deleted=False)
    if user_id:
        query = query.filter_by(user_id=user_id)
    return query.order_by(
        AccessMatrix.user_id.asc(),
        AccessMatrix.scope_type.asc(),
        AccessMatrix.entity_type.asc(),
        AccessMatrix.id.asc(),
    ).all()


def list_access_rows_for_scope(user_id, scope_type, scope_site_id=None):
    normalized_scope_site_id = scope_site_id if scope_type == "site" else None
    return (
        AccessMatrix.query.filter_by(
            user_id=user_id,
            scope_type=scope_type,
            scope_site_id=normalized_scope_site_id,
            scope_region_id=None,
            entity_id=None,
            is_deleted=False,
        )
        .order_by(AccessMatrix.entity_type.asc(), AccessMatrix.id.asc())
        .all()
    )


def build_permission_matrix(user_id, scope_type, scope_site_id=None):
    rows_by_entity = {
        row.entity_type: row for row in list_access_rows_for_scope(user_id, scope_type, scope_site_id)
    }
    matrix = {}
    for entity_type in ENTITY_TYPES:
        row = rows_by_entity.get(entity_type)
        allowed_flags = SUPPORTED_PERMISSION_FLAGS[entity_type]
        matrix[entity_type] = {
            flag: bool(getattr(row, flag)) if row and flag in allowed_flags else False
            for flag in PERMISSION_FLAGS
        }
    return matrix


def summarize_access(rows, site_names=None):
    site_names = site_names or {}
    scopes = set()
    entities = {}
    for row in rows:
        allowed_flags = SUPPORTED_PERMISSION_FLAGS.get(row.entity_type, set(PERMISSION_FLAGS))
        if not any(bool(getattr(row, flag)) for flag in allowed_flags):
            continue
        if row.scope_type == "global":
            scopes.add("Global")
        else:
            scopes.add(site_names.get(row.scope_site_id, f"Site {row.scope_site_id}"))
        entity_label = ENTITY_LABELS.get(
            row.entity_type,
            "All entities" if row.entity_type == "all" else row.entity_type,
        )
        entities[entity_label] = ENTITY_CHIP_CATEGORIES.get(row.entity_type, "neutral")

    ordered_scopes = sorted(scopes, key=lambda scope: (scope != "Global", scope))
    ordered_entities = [
        {"label": label, "category": entities[label]}
        for label in sorted(entities)
    ]
    return {
        "has_access": bool(ordered_scopes and ordered_entities),
        "has_global_access": "Global" in scopes,
        "primary_scope": ordered_scopes[0] if ordered_scopes else None,
        "primary_scope_category": "global" if ordered_scopes and ordered_scopes[0] == "Global" else "site",
        "site_scopes": [scope for scope in ordered_scopes if scope != "Global"][:2],
        "additional_site_scope_count": max(len([scope for scope in ordered_scopes if scope != "Global"]) - 2, 0),
        "additional_scope_count": max(len(ordered_scopes) - 1, 0),
        "entities": ordered_entities[:3],
        "additional_entity_count": max(len(ordered_entities) - 3, 0),
    }


def build_user_access_summary(users, sites=None):
    site_names = {site.id: site.name for site in sites or []}
    summaries = {}
    for user in users:
        summaries[user.id] = summarize_access(list_access_rows(user.id), site_names)
    return summaries


def upsert_access_row(
    user_id,
    scope_type,
    scope_site_id,
    entity_type,
    permission_values,
    actor_id,
):
    if not user_id:
        raise ValidationError("User is required.")
    if scope_type not in ("global", "site"):
        raise ValidationError("Scope type must be global or site.")
    if scope_type == "site" and not scope_site_id:
        raise ValidationError("Site scope requires a site.")
    validated_entity_type = validate_code(entity_type, "Entity type")
    if validated_entity_type not in ENTITY_TYPES:
        raise ValidationError("Invalid entity type.")
    permission_values = sanitize_permission_values(validated_entity_type, permission_values)

    normalized_scope_site_id = scope_site_id if scope_type == "site" else None
    row = AccessMatrix.query.filter_by(
        user_id=user_id,
        scope_type=scope_type,
        scope_site_id=normalized_scope_site_id,
        scope_region_id=None,
        entity_type=validated_entity_type,
        entity_id=None,
        is_deleted=False,
    ).first()

    if row is None:
        row = AccessMatrix(
            user_id=user_id,
            scope_type=scope_type,
            scope_site_id=normalized_scope_site_id,
            scope_region_id=None,
            entity_type=validated_entity_type,
            entity_id=None,
            created_by=actor_id,
        )
        db.session.add(row)

    for flag in PERMISSION_FLAGS:
        setattr(row, flag, bool(permission_values.get(flag)))

    return row


def save_permission_matrix(user_id, scope_type, scope_site_id, matrix_values, actor_id):
    saved_rows = []
    for entity_type in ENTITY_TYPES:
        permission_values = sanitize_permission_values(
            entity_type,
            matrix_values.get(entity_type, {}),
        )
        saved_rows.append(
            upsert_access_row(
                user_id=user_id,
                scope_type=scope_type,
                scope_site_id=scope_site_id,
                entity_type=entity_type,
                permission_values=permission_values,
                actor_id=actor_id,
            )
        )
    return saved_rows
