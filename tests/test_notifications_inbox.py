from app.modules.NOTIFY.model import Notification
from app.modules.NOTIFY.service import (
    create_notification,
    get_recent_notifications,
    get_unread_count,
    mark_all_as_read,
    mark_as_read,
)


def test_notification_inbox_unread_recent_mark_read_and_mark_all(
    make_user, db_session, created_objects,
):
    user = make_user()

    initial_unread = get_unread_count(user.id)
    first = create_notification(
        user_id=user.id,
        event_type="TEST_EVENT",
        entity_type="test",
        entity_id=999,
        message="Test notification message: Hello World!",
    )
    db_session.commit()
    created_objects.append(first)

    assert get_unread_count(user.id) == initial_unread + 1

    recent = get_recent_notifications(user.id, limit=5)
    assert any(
        item.id == first.id
        and item.message == "Test notification message: Hello World!"
        and item.event_type == "TEST_EVENT"
        and item.is_read is False
        for item in recent
    )

    mark_as_read(first.id, user.id)
    assert get_unread_count(user.id) == initial_unread
    assert Notification.query.get(first.id).is_read is True

    second = create_notification(user.id, "TEST1", "test", 1, "Msg 1")
    third = create_notification(user.id, "TEST2", "test", 2, "Msg 2")
    db_session.commit()
    created_objects.extend([second, third])

    assert get_unread_count(user.id) == initial_unread + 2
    assert mark_all_as_read(user.id) == 2
    assert get_unread_count(user.id) == initial_unread
    assert all(
        item.is_read
        for item in Notification.query.filter(Notification.id.in_([second.id, third.id])).all()
    )
