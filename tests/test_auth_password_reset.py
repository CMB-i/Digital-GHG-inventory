from datetime import timedelta

import pytest

from app.common.validators import ValidationError
from app.database import db
from app.modules.USRMGMT.model import PasswordResetOTP
from app.modules.USRMGMT.service import (
    _utc_now,
    hash_password,
    request_password_reset_otp,
    reset_password_with_otp,
    verify_password,
)


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
