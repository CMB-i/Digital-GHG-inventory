from datetime import datetime, timezone


def current_timestamp():
    return datetime.now(timezone.utc)


def created_metadata(user_id=None):
    # TODO Phase 1/2: wire user identity when auth exists.
    return {
        "created_at": current_timestamp(),
        "created_by": user_id,
    }


def updated_metadata(user_id=None):
    return {
        "updated_at": current_timestamp(),
        "updated_by": user_id,
    }


def deleted_metadata(user_id=None):
    # Full audit_log is intentionally deferred from MVP.
    return {
        "deleted_at": current_timestamp(),
        "deleted_by": user_id,
        "is_deleted": True,
    }
