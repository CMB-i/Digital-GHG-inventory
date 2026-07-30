from app import create_app
from scripts._script_safety import ScriptSafety
from tests.conftest import TestConfig


def test_create_app_does_not_seed_notification_configs(monkeypatch):
    calls = []

    def fail_if_seeded():
        calls.append("seeded")
        raise AssertionError("create_app must not seed notification configs")

    monkeypatch.setattr(
        "app.modules.NOTIFY.service.seed_default_notification_configs",
        fail_if_seeded,
    )

    create_app(TestConfig)

    assert calls == []


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_script_safety_dry_run_rolls_back_instead_of_committing():
    session = FakeSession()

    result = ScriptSafety(env="staging", dry_run=True).commit_or_rollback(session)

    assert result is False
    assert session.commits == 0
    assert session.rollbacks == 1


def test_script_safety_confirm_commits_once():
    session = FakeSession()

    result = ScriptSafety(env="production", confirm=True).commit_or_rollback(session)

    assert result is True
    assert session.commits == 1
    assert session.rollbacks == 0
