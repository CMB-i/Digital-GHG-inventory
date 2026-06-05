from app.database import db
from app.modules.NOTIFY.model import Notification

def create_notification(user_id, event_type, entity_type, entity_id, message, channel="in_app"):
    """
    Creates and stores a notification record in the database.
    """
    notif = Notification(
        user_id=user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        channel=channel
    )
    db.session.add(notif)
    db.session.flush()
    return notif
