import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.USRMGMT.model import User
from app.modules.NOTIFY.model import Notification, UserNotificationPreference, NotificationConfig
from app.modules.NOTIFY.service import (
    dispatch_notification_event,
    get_user_preferences,
    seed_default_notification_configs
)


def run_tests():
    app = create_app()
    with app.app_context():
        print("Starting configured notifications module tests...")

        # 1. Fetch seed user
        test_user = User.query.filter_by(email="admin@example.com").first()
        if not test_user:
            print("FAILED: admin@example.com user not found. Please run seed script first.")
            sys.exit(1)

        # 2. Configure user preferences
        pref = UserNotificationPreference.query.filter_by(user_id=test_user.id).first()
        if not pref:
            pref = UserNotificationPreference(user_id=test_user.id)
            db.session.add(pref)
        
        pref.pref_in_app = True
        pref.pref_desktop = True
        pref.pref_email = True
        pref.pref_whatsapp = True
        db.session.commit()
        print("Configured user preferences to accept all channels.")

        # 3. Clear existing configurations for test clean state
        # We will keep track of them to restore or clean up later
        NotificationConfig.query.filter(NotificationConfig.name.like("TEST_%")).delete()
        db.session.commit()

        # 4. Create a test Notification configuration
        test_config = NotificationConfig(
            name="TEST_Period_Opened_Alert",
            event_type="TEST_PERIOD_OPEN",
            message_template="Period {period_label} is now open for site {site_name}.",
            recipient_type="users",
            recipient_user_ids=str(test_user.id),
            channels="in_app,desktop,email,whatsapp",
            created_by=test_user.id,
            updated_by=test_user.id
        )
        db.session.add(test_config)
        db.session.commit()
        print(f"Created test config ID: {test_config.id}")

        # 5. Clear mock logs before running dispatch
        uploads_dir = Path("/Users/shubhamindulkar/Digital-GHG-inventory/uploads")
        email_log = uploads_dir / "mock_emails.log"
        whatsapp_log = uploads_dir / "mock_whatsapp.log"
        
        if email_log.exists():
            email_log.unlink()
        if whatsapp_log.exists():
            whatsapp_log.unlink()

        # 6. Dispatch the event
        context = {
            "site_id": 999,
            "site_name": "Test Port Site A",
            "period_label": "FY 2026-Q1"
        }
        
        dispatched = dispatch_notification_event(
            event_type="TEST_PERIOD_OPEN",
            entity_type="reporting_period",
            entity_id=999,
            context=context
        )
        
        db.session.commit()
        print(f"Dispatched event. Created {len(dispatched)} in-app notifications.")

        # 7. Assertions
        # Check in-app & desktop database records
        db_notifications = Notification.query.filter_by(
            user_id=test_user.id,
            event_type="TEST_PERIOD_OPEN",
            entity_type="reporting_period",
            entity_id=999
        ).all()
        
        assert len(db_notifications) == 2, f"Expected 2 DB notifications (in_app + desktop), got {len(db_notifications)}"
        
        channels = {n.channel for n in db_notifications}
        assert "in_app" in channels, "In-app notification missing"
        assert "desktop" in channels, "Desktop notification missing"
        
        expected_msg = "Period FY 2026-Q1 is now open for site Test Port Site A."
        for n in db_notifications:
            assert n.message == expected_msg, f"Message mismatch: expected '{expected_msg}', got '{n.message}'"

        # Check mock email output
        assert email_log.exists(), "Email mock log file was not created"
        with open(email_log, "r") as f:
            email_content = f.read()
        assert "To: admin@example.com" in email_content, "Mock email did not contain recipient address"
        assert expected_msg in email_content, "Mock email did not contain the formatted message"
        print("Mock email delivery verified successfully.")

        # Check mock WhatsApp output
        assert whatsapp_log.exists(), "WhatsApp mock log file was not created"
        with open(whatsapp_log, "r") as f:
            whatsapp_content = f.read()
        # Admin mobile might be empty or a dummy string, but log exists and contains message
        assert expected_msg in whatsapp_content, "Mock WhatsApp did not contain the formatted message"
        print("Mock WhatsApp delivery verified successfully.")

        # 8. Clean up
        NotificationConfig.query.filter_by(id=test_config.id).delete()
        for n in db_notifications:
            Notification.query.filter_by(id=n.id).delete()
        db.session.commit()
        print("Cleaned up test configurations and records.")

        print("--------------------------------------------------")
        print("All notification system tests PASSED successfully!")
        print("--------------------------------------------------")


if __name__ == "__main__":
    run_tests()
