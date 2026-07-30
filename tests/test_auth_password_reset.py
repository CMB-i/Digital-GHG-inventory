from datetime import timedelta

import pytest

from app.common.auth import is_safe_internal_path, require_login
from app.common.validators import ValidationError
from app.database import db
from app.modules.AUDITL.model import AuditLog
from app.modules.USRMGMT.model import PasswordResetOTP
from app.modules.USRMGMT.service import (
    OTP_MAX_FAILED_ATTEMPTS,
    _utc_now,
    hash_password,
    request_password_reset_otp,
    reset_password_with_otp,
    verify_password,
)


def _reset_form(email, code, password="NewPass123!", confirm_password="NewPass123!"):
    return {
        "email": email,
        "otp_code": code,
        "new_password": password,
        "confirm_password": confirm_password,
    }


@pytest.fixture()
def captured_otps(monkeypatch):
    sent = []

    def fake_send(to_email, subject, body):
        code = next(part.strip(".") for part in body.split() if part.strip(".").isdigit() and len(part.strip(".")) == 6)
        sent.append({"to": to_email, "subject": subject, "body": body, "code": code})
        return True, None

    monkeypatch.setattr("app.modules.USRMGMT.service.send_mock_email", fake_send)
    return sent


def test_password_reset_otp_generation_hashes_code_and_invalidates_previous(make_user, db_session, captured_otps):
    user = make_user(email="reset-generation@example.com")
    user.password_hash = hash_password("OldPass123!")
    db_session.commit()

    created, first = request_password_reset_otp(user.email)
    db.session.commit()
    created_again, second = request_password_reset_otp(user.email)
    db.session.commit()

    assert created is True
    assert created_again is True
    assert first.used is True
    assert second.used is False
    assert second.expires_at > second.created_at
    assert second.otp_hash != captured_otps[-1]["code"]
    assert verify_password(captured_otps[-1]["code"], second.otp_hash) is True


def test_password_reset_otp_expiry_blocks_reset(make_user, db_session):
    user = make_user(email="reset-expired@example.com")
    user.password_hash = hash_password("OldPass123!")
    otp = PasswordResetOTP(
        user_id=user.id,
        email=user.email,
        otp_hash=hash_password("123456"),
        created_at=_utc_now() - timedelta(minutes=20),
        expires_at=_utc_now() - timedelta(minutes=10),
        used=False,
    )
    db.session.add(otp)
    db_session.commit()

    with pytest.raises(ValidationError, match="Invalid or expired reset code"):
        reset_password_with_otp(user.email, "123456", "NewPass123!")

    assert otp.used is True
    assert verify_password("OldPass123!", user.password_hash) is True


def test_password_reset_with_valid_otp_updates_password_and_marks_otp_used(make_user, db_session, captured_otps):
    user = make_user(email="reset-success@example.com")
    user.password_hash = hash_password("OldPass123!")
    db_session.commit()
    request_password_reset_otp(user.email)
    db.session.commit()

    response_user = reset_password_with_otp(user.email, captured_otps[-1]["code"], "NewPass123!")
    db.session.commit()
    otp = PasswordResetOTP.query.filter_by(user_id=user.id).one()

    assert response_user.id == user.id
    assert otp.used is True
    assert otp.used_at is not None
    assert verify_password("NewPass123!", user.password_hash) is True
    assert verify_password("OldPass123!", user.password_hash) is False


def test_is_safe_internal_path_rejects_external_and_encoded_redirects():
    unsafe = (
        "//evil.test",
        "/\\evil.test",
        "\\/evil.test",
        "/%2F%2Fevil.test",
        "/%252F%252Fevil.test",
        "/%5Cevil.test",
        "http:evil.test",
        "/dashboard%0ASet-Cookie:%20x=y",
        "/dashboard%0DLocation:%20//evil.test",
        "/dashboard\r\nLocation:%20//evil.test",
    )

    for target in unsafe:
        assert is_safe_internal_path(target) is False

    assert is_safe_internal_path("/module/SUBMIT/annual") is True


def test_login_rejects_external_next_redirects_and_sets_session_version(app, make_user, db_session):
    user = make_user(email="login-redirect@example.com")
    user.password_hash = hash_password("OldPass123!")
    db_session.commit()

    with app.test_client() as client:
        for next_url in (
            "https://evil.test",
            "//evil.test",
            "/\\evil.test",
            "\\/evil.test",
            "/%2F%2Fevil.test",
            "/%252F%252Fevil.test",
            "http:evil.test",
            "/dashboard%0ASet-Cookie:%20x=y",
            "/dashboard%0DLocation:%20//evil.test",
        ):
            response = client.post(
                f"/login?next={next_url}",
                data={"email": user.email, "password": "OldPass123!"},
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert not response.headers["Location"].startswith(("https://evil.test", "//evil.test", "/\\evil.test"))

        response = client.post(
            "/login?next=/module/SUBMIT/annual",
            data={"email": user.email, "password": "OldPass123!"},
            follow_redirects=False,
        )
        assert response.headers["Location"] == "/module/SUBMIT/annual"
        with client.session_transaction() as sess:
            assert sess["user_session_version"] == user.session_version == 0


def test_password_reset_locks_otp_after_failed_attempts(app, make_user, db_session, captured_otps):
    user = make_user(email="reset-lock@example.com")
    user.password_hash = hash_password("OldPass123!")
    db_session.commit()
    request_password_reset_otp(user.email)
    db.session.commit()

    with app.test_client() as client:
        for _ in range(OTP_MAX_FAILED_ATTEMPTS):
            response = client.post("/reset-password", data=_reset_form(user.email, "000000"))
            assert response.status_code == 400

        otp = PasswordResetOTP.query.filter_by(user_id=user.id).one()
        assert otp.failed_attempts == OTP_MAX_FAILED_ATTEMPTS
        assert otp.locked_at is not None
        assert otp.used is True

        locked = client.post("/reset-password", data=_reset_form(user.email, captured_otps[-1]["code"]))
        assert locked.status_code == 400

        request_password_reset_otp(user.email)
        db.session.commit()
        new_otp = PasswordResetOTP.query.filter_by(user_id=user.id, used=False).one()
        assert new_otp.failed_attempts == 0
        assert new_otp.locked_at is None

        unlocked = client.post("/reset-password", data=_reset_form(user.email, captured_otps[-1]["code"]))
        assert unlocked.status_code == 302
    assert verify_password("NewPass123!", user.password_hash) is True


def test_password_reset_rejects_locked_unused_otp_even_with_correct_code(make_user, db_session):
    user = make_user(email="reset-locked-unused@example.com")
    user.password_hash = hash_password("OldPass123!")
    otp = PasswordResetOTP(
        user_id=user.id,
        email=user.email,
        otp_hash=hash_password("123456"),
        created_at=_utc_now(),
        expires_at=_utc_now() + timedelta(minutes=10),
        used=False,
        locked_at=_utc_now(),
    )
    db.session.add(otp)
    db_session.commit()

    with pytest.raises(ValidationError, match="Invalid or expired reset code"):
        reset_password_with_otp(user.email, "123456", "NewPass123!")

    assert verify_password("OldPass123!", user.password_hash) is True


def test_password_reset_bumps_session_version_and_invalidates_existing_session(app, make_user, db_session, captured_otps):
    user = make_user(email="reset-session@example.com")
    user.password_hash = hash_password("OldPass123!")
    db_session.commit()
    request_password_reset_otp(user.email)
    db.session.commit()

    with app.test_request_context("/protected"):
        from flask import session

        session["user_id"] = user.id
        assert require_login(lambda: "ok")() == "ok"
        session["user_session_version"] = user.session_version
        assert require_login(lambda: "ok")() == "ok"

        reset_password_with_otp(user.email, captured_otps[-1]["code"], "NewPass123!")
        db.session.commit()
        response = require_login(lambda: "ok")()

        assert response.status_code == 302
        assert response.headers["Location"].startswith("/login?next=")


def test_reset_password_confirmation_mismatch_does_not_consume_otp(app, make_user, db_session, captured_otps):
    user = make_user(email="reset-confirm@example.com")
    user.password_hash = hash_password("OldPass123!")
    db_session.commit()
    request_password_reset_otp(user.email)
    db.session.commit()

    with app.test_client() as client:
        mismatch = client.post(
            "/reset-password",
            data=_reset_form(user.email, captured_otps[-1]["code"], confirm_password="OtherPass123!"),
            follow_redirects=False,
        )

        otp = PasswordResetOTP.query.filter_by(user_id=user.id).one()
        assert mismatch.status_code == 400
        assert "Passwords do not match." in mismatch.get_data(as_text=True)
        assert otp.used is False
        assert otp.failed_attempts == 0

        retry = client.post(
            "/reset-password",
            data=_reset_form(user.email, captured_otps[-1]["code"]),
            follow_redirects=False,
        )

        assert retry.status_code == 302
        assert retry.headers["Location"] == "/login"
        assert otp.used is True
        assert verify_password("NewPass123!", user.password_hash) is True


def test_password_reset_does_not_expose_plaintext_secret_in_error_or_audit(app, make_user, db_session, captured_otps):
    user = make_user(email="reset-secret@example.com")
    user.password_hash = hash_password("OldPass123!")
    db_session.commit()
    request_password_reset_otp(user.email)
    db.session.commit()
    otp_code = captured_otps[-1]["code"]
    wrong_code = "000001" if otp_code != "000001" else "000002"
    new_password = "NewPass123!"

    with app.test_client() as client:
        response = client.post("/reset-password", data=_reset_form(user.email, wrong_code, new_password))
        assert response.status_code == 400
        error_body = response.get_data(as_text=True)
        assert wrong_code not in error_body
        assert otp_code not in error_body
        assert new_password not in error_body

        response = client.post("/reset-password", data=_reset_form(user.email, otp_code, new_password))
        assert response.status_code == 302

    audit = AuditLog.query.filter_by(
        actor_user_id=user.id,
        entity_type="user",
        entity_id=str(user.id),
        action="USER_PASSWORD_RESET",
    ).one()
    audit_payload = f"{audit.old_values} {audit.new_values} {audit.metadata_json}"
    assert otp_code not in audit_payload
    assert new_password not in audit_payload
