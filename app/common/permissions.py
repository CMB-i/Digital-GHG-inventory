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


ACTION_TO_FLAG = {
    "view": "can_view",
    "create": "can_create",
    "edit": "can_edit",
    "delete": "can_delete",
    "submit": "can_submit",
    "approve": "can_approve",
    "reject": "can_reject",
    "reopen": "can_reopen",
    "export": "can_export",
    "manage_forms": "can_manage_forms",
    "manage_users": "can_manage_users",
}


def has_permission(user_id, entity_type, action, scope_site_id=None, entity_id=None):
    from app.modules.ACCESS.service import get_user_permissions

    flag = ACTION_TO_FLAG.get(action)
    if flag not in PERMISSION_FLAGS:
        return False

    scope_type = "site" if scope_site_id is not None else "global"
    permissions = get_user_permissions(
        user_id=user_id,
        scope_type=scope_type,
        scope_site_id=scope_site_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return permissions.get(flag, False)
