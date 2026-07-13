"""
Tests for collapsing the REOPENED reporting-period status into OPEN.

LOCKED now transitions directly to OPEN -- the one-step replacement for the
old two-step Lock -> Reopen -> Mark-Open cycle. reopen_reason/reopened_at/
reopened_by are still captured on that step, and it still requires the
"reopen" permission specifically: required_transition_action is keyed by the
(current_status, target_status) pair precisely because target_status alone
can no longer tell "close-submission reversed" apart from "a locked period
was reopened" now that both would otherwise look like "-> OPEN".
"""
import pytest
from sqlalchemy import text

from app.common.validators import ValidationError
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.PERIOD.service import (
    VALID_STATUSES,
    VALID_TRANSITIONS,
    required_transition_action,
    transition_period,
)


def _grant_global(make_access_grant, user, **flags):
    make_access_grant(user, "period", scope_type="global", **flags)


class TestReopenedStatusRemoved:
    def test_reopened_is_not_a_valid_status_or_transition(self):
        assert "REOPENED" not in VALID_STATUSES
        assert "REOPENED" not in VALID_TRANSITIONS
        assert "REOPENED" not in VALID_TRANSITIONS.values()

    def test_locked_now_transitions_directly_to_open(self):
        assert VALID_TRANSITIONS["LOCKED"] == "OPEN"


class TestRequiredTransitionAction:
    def test_locked_to_open_requires_reopen(self):
        assert required_transition_action("LOCKED", "OPEN") == "reopen"

    def test_open_to_submission_closed_requires_edit(self):
        assert required_transition_action("OPEN", "SUBMISSION_CLOSED") == "edit"

    def test_submission_closed_to_locked_requires_edit(self):
        assert required_transition_action("SUBMISSION_CLOSED", "LOCKED") == "edit"

    def test_non_adjacent_pair_is_invalid(self):
        assert required_transition_action("OPEN", "LOCKED") is None
        assert required_transition_action("LOCKED", "SUBMISSION_CLOSED") is None

    def test_unknown_current_status_is_invalid(self):
        assert required_transition_action(None, "OPEN") is None
        assert required_transition_action("REOPENED", "OPEN") is None


class TestFullTransitionCycle:
    def test_open_close_lock_reopen_lands_on_open_in_one_step(
        self, make_site, make_reporting_period, make_user, make_access_grant,
    ):
        actor = make_user()
        _grant_global(make_access_grant, actor, can_edit=True, can_reopen=True)

        site = make_site()
        period = make_reporting_period(site, year=2026, month=11, status="OPEN")

        transition_period(period.id, "SUBMISSION_CLOSED", actor.id)
        assert period.status == "SUBMISSION_CLOSED"

        transition_period(period.id, "LOCKED", actor.id)
        assert period.status == "LOCKED"

        transitioned = transition_period(
            period.id, "OPEN", actor.id, reopen_reason="Correction needed."
        )

        # One step, not two: there is no intermediate REOPENED status to pass
        # through anymore -- LOCKED goes straight back to OPEN.
        assert transitioned.status == "OPEN"
        assert period.status == "OPEN"
        assert transitioned.reopen_reason == "Correction needed."
        assert transitioned.reopened_at is not None
        assert transitioned.reopened_by == actor.id

    def test_locked_to_open_still_requires_a_reason(
        self, make_site, make_reporting_period, make_user, make_access_grant,
    ):
        actor = make_user()
        _grant_global(make_access_grant, actor, can_reopen=True)
        site = make_site()
        period = make_reporting_period(site, year=2026, month=11, status="LOCKED")

        with pytest.raises(ValidationError):
            transition_period(period.id, "OPEN", actor.id, reopen_reason="   ")

        assert period.status == "LOCKED"


class TestCollapseMigrationDataUpdate:
    def test_reopened_rows_convert_to_open(self, make_site, make_reporting_period, db_session):
        site = make_site()
        period = make_reporting_period(site, year=2026, month=11, status="REOPENED")
        assert period.status == "REOPENED"

        # Mirrors migrations/versions/4e52328f2156_collapse_reopened_status_into_open.py's
        # upgrade(): status is a plain VARCHAR(30) with no CHECK constraint or
        # enum type, so this is a pure data update.
        db_session.execute(
            text("UPDATE reporting_periods SET status = 'OPEN' WHERE status = 'REOPENED'")
        )
        db_session.flush()
        db_session.refresh(period)

        assert period.status == "OPEN"

    def test_reopened_at_and_reason_survive_the_collapse(
        self, make_site, make_reporting_period, make_user, make_access_grant, db_session,
    ):
        actor = make_user()
        _grant_global(make_access_grant, actor, can_reopen=True)
        site = make_site()
        period = make_reporting_period(site, year=2026, month=11, status="LOCKED")

        transitioned = transition_period(period.id, "OPEN", actor.id, reopen_reason="Late correction.")
        assert transitioned.reopen_reason == "Late correction."
        reopened_at_before = transitioned.reopened_at

        # Simulate the migration running against a row that (hypothetically)
        # still had the old REOPENED status -- reopen_reason/reopened_at/
        # reopened_by must be untouched, since they're now the sole
        # "was this ever reopened" signal.
        db_session.execute(
            text("UPDATE reporting_periods SET status = 'OPEN' WHERE id = :id"),
            {"id": period.id},
        )
        db_session.flush()
        db_session.refresh(period)

        assert period.status == "OPEN"
        assert period.reopen_reason == "Late correction."
        assert period.reopened_at == reopened_at_before
        assert period.reopened_by == actor.id
