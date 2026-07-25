"""
Tests for PERIOD bulk transitions (app/modules/PERIOD/service.py) and the
Last Updated intra-month-group sort used by the Reporting Periods page.
"""
from datetime import datetime, timedelta, timezone

from app.modules.PERIOD.model import ReportingPeriod
from app.modules.PERIOD.service import bulk_transition_periods, sort_period_group


def _grant_global(make_access_grant, user, **flags):
    make_access_grant(user, "period", scope_type="global", **flags)


class TestBulkTransitionFullyEligible:
    def test_all_periods_succeed(self, make_site, make_reporting_period, make_user, make_access_grant):
        actor = make_user()
        _grant_global(make_access_grant, actor, can_edit=True)

        site_a = make_site()
        site_b = make_site()
        site_c = make_site()
        periods = [
            make_reporting_period(site_a, year=2026, month=4, status="OPEN"),
            make_reporting_period(site_b, year=2026, month=4, status="OPEN"),
            make_reporting_period(site_c, year=2026, month=4, status="OPEN"),
        ]

        results = bulk_transition_periods(
            period_ids=[p.id for p in periods],
            target_status="SUBMISSION_CLOSED",
            actor_id=actor.id,
        )

        assert len(results["succeeded"]) == 3
        assert results["skipped"] == []
        assert results["failed"] == []
        succeeded_ids = {p.id for p in results["succeeded"]}
        assert succeeded_ids == {p.id for p in periods}

        for period in periods:
            refreshed = ReportingPeriod.query.get(period.id)
            assert refreshed.status == "SUBMISSION_CLOSED"


class TestBulkTransitionMixedEligibility:
    def test_ineligible_periods_are_skipped_not_failed(
        self, make_site, make_reporting_period, make_user, make_access_grant,
    ):
        actor = make_user()
        _grant_global(make_access_grant, actor, can_edit=True)

        site_a = make_site()
        site_b = make_site()
        site_c = make_site()
        eligible_1 = make_reporting_period(site_a, year=2026, month=5, status="OPEN")
        eligible_2 = make_reporting_period(site_b, year=2026, month=5, status="OPEN")
        ineligible = make_reporting_period(site_c, year=2026, month=5, status="LOCKED")

        results = bulk_transition_periods(
            period_ids=[eligible_1.id, eligible_2.id, ineligible.id],
            target_status="SUBMISSION_CLOSED",
            actor_id=actor.id,
        )

        assert {p.id for p in results["succeeded"]} == {eligible_1.id, eligible_2.id}
        assert len(results["skipped"]) == 1
        assert results["skipped"][0]["period_id"] == ineligible.id
        assert "LOCKED" in results["skipped"][0]["reason"]
        assert results["failed"] == []

        assert ReportingPeriod.query.get(eligible_1.id).status == "SUBMISSION_CLOSED"
        assert ReportingPeriod.query.get(eligible_2.id).status == "SUBMISSION_CLOSED"
        # The batch failing on one row must not roll back the others.
        assert ReportingPeriod.query.get(ineligible.id).status == "LOCKED"

    def test_missing_period_is_skipped(self, make_site, make_reporting_period, make_user, make_access_grant):
        actor = make_user()
        _grant_global(make_access_grant, actor, can_edit=True)

        site = make_site()
        period = make_reporting_period(site, year=2026, month=6, status="OPEN")
        bogus_id = period.id + 999999

        results = bulk_transition_periods(
            period_ids=[period.id, bogus_id],
            target_status="SUBMISSION_CLOSED",
            actor_id=actor.id,
        )

        assert {p.id for p in results["succeeded"]} == {period.id}
        assert len(results["skipped"]) == 1
        assert results["skipped"][0]["period_id"] == bogus_id
        assert "not found" in results["skipped"][0]["reason"].lower()


class TestBulkTransitionPermission:
    def test_caller_without_required_action_is_rejected_per_row(
        self, make_site, make_reporting_period, make_user, make_access_grant,
    ):
        # Actor has "edit" but not "reopen" -- transitioning LOCKED -> OPEN
        # requires "reopen" specifically (required_transition_action treats
        # this pair differently from every other transition reaching OPEN).
        actor = make_user()
        _grant_global(make_access_grant, actor, can_edit=True)

        site_a = make_site()
        site_b = make_site()
        period_1 = make_reporting_period(site_a, year=2026, month=7, status="LOCKED")
        period_2 = make_reporting_period(site_b, year=2026, month=7, status="LOCKED")

        results = bulk_transition_periods(
            period_ids=[period_1.id, period_2.id],
            target_status="OPEN",
            actor_id=actor.id,
            reopen_reason="Needed for correction.",
        )

        assert results["succeeded"] == []
        assert results["failed"] == []
        assert len(results["skipped"]) == 2
        skipped_ids = {entry["period_id"] for entry in results["skipped"]}
        assert skipped_ids == {period_1.id, period_2.id}
        for entry in results["skipped"]:
            assert "permission" in entry["reason"].lower()

        # Nothing should have actually transitioned.
        assert ReportingPeriod.query.get(period_1.id).status == "LOCKED"
        assert ReportingPeriod.query.get(period_2.id).status == "LOCKED"

    def test_caller_with_reopen_permission_succeeds(
        self, make_site, make_reporting_period, make_user, make_access_grant,
    ):
        actor = make_user()
        _grant_global(make_access_grant, actor, can_reopen=True)

        site = make_site()
        period = make_reporting_period(site, year=2026, month=8, status="LOCKED")

        results = bulk_transition_periods(
            period_ids=[period.id],
            target_status="OPEN",
            actor_id=actor.id,
            reopen_reason="Needed for correction.",
        )

        assert {p.id for p in results["succeeded"]} == {period.id}
        assert ReportingPeriod.query.get(period.id).status == "OPEN"

    def test_edit_only_actor_can_still_close_submission(
        self, make_site, make_reporting_period, make_user, make_access_grant,
    ):
        # The other half of the fix: an edit-only actor must still be able to
        # perform transitions that were never the reopen step in the first
        # place (OPEN -> SUBMISSION_CLOSED doesn't need "reopen").
        actor = make_user()
        _grant_global(make_access_grant, actor, can_edit=True)

        site = make_site()
        period = make_reporting_period(site, year=2026, month=8, status="OPEN")

        results = bulk_transition_periods(
            period_ids=[period.id],
            target_status="SUBMISSION_CLOSED",
            actor_id=actor.id,
        )

        assert {p.id for p in results["succeeded"]} == {period.id}
        assert ReportingPeriod.query.get(period.id).status == "SUBMISSION_CLOSED"


class TestSortPeriodGroup:
    def test_sorts_by_last_updated_within_group(self, make_site, make_reporting_period, db_session):
        site_a = make_site()
        site_b = make_site()
        site_c = make_site()

        oldest = make_reporting_period(site_a, year=2026, month=9, status="OPEN")
        middle = make_reporting_period(site_b, year=2026, month=9, status="OPEN")
        newest = make_reporting_period(site_c, year=2026, month=9, status="OPEN")

        base = datetime(2026, 9, 1, tzinfo=timezone.utc)
        oldest.updated_at = base
        middle.updated_at = base + timedelta(days=1)
        newest.updated_at = base + timedelta(days=2)
        db_session.flush()

        site_map = {site_a.id: site_a, site_b.id: site_b, site_c.id: site_c}
        periods = [middle, newest, oldest]

        sort_period_group(periods, site_map, sort_by="updated_at", sort_dir="asc")
        assert [p.id for p in periods] == [oldest.id, middle.id, newest.id]

        sort_period_group(periods, site_map, sort_by="updated_at", sort_dir="desc")
        assert [p.id for p in periods] == [newest.id, middle.id, oldest.id]

    def test_default_sort_is_by_site_name(self, make_site, make_reporting_period):
        site_z = make_site(name="Zulu Site")
        site_a = make_site(name="Alpha Site")

        period_z = make_reporting_period(site_z, year=2026, month=10, status="OPEN")
        period_a = make_reporting_period(site_a, year=2026, month=10, status="OPEN")

        site_map = {site_z.id: site_z, site_a.id: site_a}
        periods = [period_z, period_a]

        sort_period_group(periods, site_map, sort_by=None)
        assert [p.id for p in periods] == [period_a.id, period_z.id]
