"""
Tests for delete_period() (app/modules/PERIOD/service.py) and the DELETE
route wired up in PERIOD/views.py. Reporting Period previously had no delete
mechanism at all -- only the four-state status transition system (untouched
here). Unlike Site/Workbook's dependency checks, which only block on
in-progress submissions, delete_period must block on a submission of ANY
status -- RPTBLD reads historical Approved/Locked submissions by period, so
deleting the period out from under them would silently break past reports.
"""
import pytest

from app.modules.PERIOD.model import ReportingPeriod
from app.modules.PERIOD.service import delete_period


def _grant_global(make_access_grant, user, **flags):
    make_access_grant(user, "period", scope_type="global", **flags)


class TestDeletePeriodDependencyChecks:
    def test_delete_blocked_when_draft_submission_exists(
        self, make_site, make_reporting_period, make_form, make_workflow, make_submission, make_user,
    ):
        site = make_site()
        period = make_reporting_period(site, year=2026, month=5)
        form, form_version = make_form()
        workflow_version = make_workflow([])
        actor = make_user()
        make_submission(site, form, form_version, period, workflow_version, status="Draft")

        with pytest.raises(ValueError, match="submission"):
            delete_period(period.id, actor.id, reason="cleanup")

        assert ReportingPeriod.query.filter_by(id=period.id, is_deleted=False).first() is not None

    def test_delete_blocked_when_approved_submission_exists(
        self, make_site, make_reporting_period, make_form, make_workflow, make_submission, make_user,
    ):
        """Approved is NOT in IN_PROGRESS_SUBMISSION_STATUSES -- this proves
        delete_period blocks on it anyway, unlike deactivate_site/
        deactivate_workbook which would let this through."""
        site = make_site()
        period = make_reporting_period(site, year=2026, month=5)
        form, form_version = make_form()
        workflow_version = make_workflow([])
        actor = make_user()
        make_submission(site, form, form_version, period, workflow_version, status="Approved")

        with pytest.raises(ValueError, match="submission"):
            delete_period(period.id, actor.id, reason="cleanup")

        assert ReportingPeriod.query.filter_by(id=period.id, is_deleted=False).first() is not None

    def test_delete_blocked_when_submission_package_references_period_independently(
        self, make_site, make_reporting_period, make_user, db_session, created_objects, system_user,
    ):
        """SubmissionPackage.period_id is a real, independent FK -- not
        merely derived from member Submissions -- so a package with zero
        actual Submission rows must still block deletion on its own."""
        from app.modules.SUBMIT.model import SubmissionPackage

        site = make_site()
        period = make_reporting_period(site, year=2026, month=5)
        actor = make_user()

        package = SubmissionPackage(
            site_id=site.id,
            period_id=period.id,
            status="Draft",
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(package)
        db_session.flush()
        created_objects.append(package)

        with pytest.raises(ValueError, match="package"):
            delete_period(period.id, actor.id, reason="cleanup")

        assert ReportingPeriod.query.filter_by(id=period.id, is_deleted=False).first() is not None

    def test_delete_blocked_without_reason(self, make_site, make_reporting_period, make_user):
        site = make_site()
        period = make_reporting_period(site, year=2026, month=5)
        actor = make_user()

        with pytest.raises(ValueError, match="reason"):
            delete_period(period.id, actor.id, reason="")

        assert ReportingPeriod.query.filter_by(id=period.id, is_deleted=False).first() is not None

    def test_delete_succeeds_when_no_submissions_or_packages(self, make_site, make_reporting_period, make_user):
        site = make_site()
        period = make_reporting_period(site, year=2026, month=5)
        actor = make_user()

        deleted = delete_period(period.id, actor.id, reason="No longer needed")

        assert deleted.is_deleted is True
        assert deleted.delete_reason == "No longer needed"
        assert ReportingPeriod.query.filter_by(id=period.id, is_deleted=False).first() is None


class TestDeletePeriodRoute:
    def test_delete_route_requires_permission(self, client, make_user, make_site, make_reporting_period):
        site = make_site()
        period = make_reporting_period(site, year=2026, month=6)
        stranger = make_user()
        with client.session_transaction() as sess:
            sess["user_id"] = stranger.id

        resp = client.post(f"/module/PERIOD/{period.id}/delete", data={"delete_reason": "cleanup"})
        assert resp.status_code == 403

        assert ReportingPeriod.query.filter_by(id=period.id, is_deleted=False).first() is not None

    def test_delete_route_succeeds_and_removes_it_from_the_list(
        self, client, make_user, make_access_grant, make_site, make_reporting_period,
    ):
        site = make_site()
        period = make_reporting_period(site, year=2026, month=6)
        actor = make_user()
        _grant_global(make_access_grant, actor, can_delete=True, can_view=True)
        with client.session_transaction() as sess:
            sess["user_id"] = actor.id

        resp = client.post(
            f"/module/PERIOD/{period.id}/delete",
            data={"delete_reason": "No longer needed"},
            follow_redirects=False,
        )
        assert resp.status_code == 302

        assert ReportingPeriod.query.filter_by(id=period.id, is_deleted=False).first() is None

        # list_periods() (backing both the index page and this assertion)
        # filters is_deleted=False -- site.name itself would still appear in
        # the page's "All sites" filter dropdown regardless, so check the
        # actual period list rather than scraping the rendered HTML.
        from app.modules.PERIOD.service import list_periods

        remaining_ids = {p.id for p in list_periods(site_id=site.id)}
        assert period.id not in remaining_ids

        listing = client.get("/module/PERIOD/")
        assert listing.status_code == 200
