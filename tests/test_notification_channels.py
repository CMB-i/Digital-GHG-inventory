from app.modules.NOTIFY.model import Notification, NotificationConfig, UserNotificationPreference
from app.modules.NOTIFY.service import dispatch_notification_event


def test_configured_multi_channel_dispatch_respects_preferences_and_records_attempts(
    make_user, db_session, created_objects, monkeypatch, system_user,
):
    user = make_user(email="notify-channel@example.com", phone="+919999999999")
    pref = UserNotificationPreference(
        user_id=user.id,
        pref_in_app=True,
        pref_desktop=True,
        pref_email=True,
        pref_whatsapp=True,
    )
    config = NotificationConfig(
        name="TEST_Period_Opened_Alert",
        event_type="TEST_PERIOD_OPEN",
        message_template="Period {period_label} is now open for site {site_name}.",
        recipient_type="users",
        recipient_user_ids=str(user.id),
        channels="in_app,desktop,email,whatsapp",
        created_by=system_user,
        updated_by=system_user,
    )
    db_session.add_all([pref, config])
    db_session.flush()
    created_objects.extend([pref, config])

    email_calls = []
    whatsapp_calls = []
    monkeypatch.setattr(
        "app.modules.NOTIFY.service.send_mock_email",
        lambda to_email, subject, body: email_calls.append((to_email, subject, body)) or (True, None),
    )
    monkeypatch.setattr(
        "app.modules.NOTIFY.service.send_mock_whatsapp",
        lambda to_phone, body: whatsapp_calls.append((to_phone, body)) or (True, None),
    )

    dispatched = dispatch_notification_event(
        event_type="TEST_PERIOD_OPEN",
        entity_type="reporting_period",
        entity_id=999,
        context={"site_id": 999, "site_name": "Test Port Site A", "period_label": "FY 2026-Q1"},
    )
    db_session.commit()
    created_objects.extend(dispatched)

    expected_message = "Period FY 2026-Q1 is now open for site Test Port Site A."
    rows = Notification.query.filter_by(
        user_id=user.id,
        event_type="TEST_PERIOD_OPEN",
        entity_type="reporting_period",
        entity_id=999,
    ).all()

    assert {row.channel for row in rows} == {"in_app", "desktop", "email", "whatsapp"}
    assert all(row.message == expected_message for row in rows)
    assert all(row.delivery_status == "sent" for row in rows)
    assert email_calls == [(user.email, "GHG Platform Notification: TEST_Period_Opened_Alert", expected_message)]
    assert whatsapp_calls == [(user.phone, expected_message)]
