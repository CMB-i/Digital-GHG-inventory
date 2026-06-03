from app.modules.ACCESS.model import AccessMatrix


PERMISSION_FLAGS = (
    "can_view",
    "can_create",
    "can_edit",
    "can_delete",
    "can_submit",
    "can_approve",
    "can_reject",
    "can_reopen",
    "can_export",
    "can_manage_forms",
    "can_manage_users",
)


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

    for row in query.all():
        for flag in PERMISSION_FLAGS:
            permissions[flag] = permissions[flag] or bool(getattr(row, flag))

    return permissions
