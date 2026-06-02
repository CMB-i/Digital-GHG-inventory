def get_user_permissions(user_id=None):
    # TODO Phase 3: load permissions from access management configuration.
    return {
        "user_id": user_id,
        "modules": {},
        "is_authenticated": False,
    }
