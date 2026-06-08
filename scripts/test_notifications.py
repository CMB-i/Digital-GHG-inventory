import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.USRMGMT.model import User
from app.modules.NOTIFY.service import (
    create_notification,
    get_unread_count,
    get_recent_notifications,
    mark_as_read,
    mark_all_as_read
)


def run_tests():
    app = create_app()
    with app.app_context():
        print("Starting notification service tests...")
        
        # 1. Fetch seed user
        test_user = User.query.filter_by(email="admin@example.com").first()
        if not test_user:
            print("FAILED: admin@example.com user not found. Please run seed script first.")
            sys.exit(1)
            
        initial_unread = get_unread_count(test_user.id)
        print(f"Initial unread count: {initial_unread}")
        
        # 2. Create notification
        msg = "Test notification message: Hello World!"
        notif = create_notification(
            user_id=test_user.id,
            event_type="TEST_EVENT",
            entity_type="test",
            entity_id=999,
            message=msg
        )
        
        db.session.commit()
        print(f"Created notification ID: {notif.id}")
        
        # 3. Verify unread count increased
        new_unread = get_unread_count(test_user.id)
        print(f"New unread count: {new_unread}")
        assert new_unread == initial_unread + 1, f"Unread count mismatch: expected {initial_unread + 1}, got {new_unread}"
        
        # 4. Verify recent notifications contains the new one
        recent = get_recent_notifications(test_user.id, limit=5)
        found = False
        for r in recent:
            if r.id == notif.id:
                found = True
                assert r.message == msg
                assert r.event_type == "TEST_EVENT"
                assert r.is_read is False
                
        assert found, "Created notification not found in recent list!"
        print("Recent list verified successfully.")
        
        # 5. Mark read and verify
        mark_as_read(notif.id, test_user.id)
        final_unread = get_unread_count(test_user.id)
        print(f"After marking read, unread count: {final_unread}")
        assert final_unread == initial_unread, f"Unread count mismatch after read: expected {initial_unread}, got {final_unread}"
        
        # 6. Test mark all read
        # Create two more unread notifications
        create_notification(test_user.id, "TEST1", "test", 1, "Msg 1")
        create_notification(test_user.id, "TEST2", "test", 2, "Msg 2")
        db.session.commit()
        
        mid_unread = get_unread_count(test_user.id)
        assert mid_unread == initial_unread + 2
        
        marked_count = mark_all_as_read(test_user.id)
        print(f"Marked all read: {marked_count} notifications updated.")
        assert marked_count == 2
        
        post_all_unread = get_unread_count(test_user.id)
        assert post_all_unread == initial_unread
        print("Mark all read verified successfully.")
        
        # Clean up test notifications
        from app.modules.NOTIFY.model import Notification
        Notification.query.filter_by(entity_type="test", entity_id=999).delete()
        Notification.query.filter_by(event_type="TEST1").delete()
        Notification.query.filter_by(event_type="TEST2").delete()
        db.session.commit()
        
        print("All notification service tests PASSED successfully!")


if __name__ == "__main__":
    run_tests()
