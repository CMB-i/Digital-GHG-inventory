"""
Priority 4: query-count regressions for the N+1 / O(n*m) patterns fixed in
RPTBLD.get_missing_submissions, SUBMIT.get_spoc_sheets_buckets, and
APPROV.get_approver_queue. "The tests still pass" doesn't prove a performance
fix helped -- these assert an actual SQL statement count stays low and, more
importantly, does not scale with the number of sites/forms/periods involved,
which is exactly what the old per-iteration-query pattern would have failed.

The exact query-count ceilings below were derived empirically: I temporarily
reverted each fix and reran these same scenarios, confirming the old code blew
past every ceiling here (see the PR description / commit message for the
before numbers), then restored the fix and confirmed these pass comfortably.
"""
import contextlib

import pytest
from sqlalchemy import event

from app.database import db


@contextlib.contextmanager
def count_queries():
    counter = {"n": 0}

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    event.listen(db.engine, "before_cursor_execute", _before_cursor_execute)
    try:
        yield counter
    finally:
        event.remove(db.engine, "before_cursor_execute", _before_cursor_execute)


def _make_live_workbook(db_session, created_objects, system_user, forms, sites, submitter=None):
    """
    One active, published workbook assigning every form in `forms` to every
    site in `sites` (WorkbookForm x WorkbookSite, full cross product) --
    exactly the shape get_missing_submissions/get_spoc_sheets_buckets scan.
    If `submitter` is given, also grants that user WorkbookSiteSubmitter
    access at every site (needed by get_spoc_sheets_buckets).
    """
    from app.modules.WKBK.model import Workbook, WorkbookForm, WorkbookSite, WorkbookSiteSubmitter

    workbook = Workbook(
        name="Perf Test Workbook", code=f"perf-wbk-{id(forms)}-{id(sites)}",
        status="published", is_active=True, created_by=system_user,
    )
    db_session.add(workbook)
    db_session.flush()
    created_objects.append(workbook)

    for form in forms:
        wf = WorkbookForm(workbook_id=workbook.id, form_id=form.id, display_order=10)
        db_session.add(wf)
        created_objects.append(wf)

    for site in sites:
        ws = WorkbookSite(workbook_id=workbook.id, site_id=site.id, created_by=system_user)
        db_session.add(ws)
        created_objects.append(ws)
        if submitter:
            wss = WorkbookSiteSubmitter(workbook_id=workbook.id, site_id=site.id, user_id=submitter.id, created_by=system_user)
            db_session.add(wss)
            created_objects.append(wss)

    db_session.flush()
    return workbook


class TestGetMissingSubmissionsQueryCount:
    def test_query_count_does_not_scale_with_sites_times_forms(
        self, make_site, make_form, make_reporting_period, make_user,
        make_access_grant, db_session, created_objects, system_user,
    ):
        from app.modules.RPTBLD.service import get_missing_submissions

        user = make_user()
        # Global grant so _get_user_allowed_sites (a separate, unflagged
        # function) short-circuits to a fixed 2 queries regardless of how
        # many sites exist, keeping this test isolated to the fix under test.
        make_access_grant(user, "submission", scope_type="global", can_view=True)

        sites = [make_site() for _ in range(3)]
        forms = []
        for _ in range(4):
            form, form_version = make_form()
            forms.append(form)
        for site in sites:
            make_reporting_period(site)

        _make_live_workbook(db_session, created_objects, system_user, forms, sites)

        with count_queries() as counter:
            result = get_missing_submissions(user.id)

        # 3 sites x 4 forms x 1 period = 12 combinations. The old code ran up
        # to 2 queries per combination (24+) on top of its fixed setup
        # queries; the fix runs a fixed small handful of queries regardless.
        assert len(result) == 12
        assert counter["n"] < 12, (
            f"get_missing_submissions ran {counter['n']} queries for 12 "
            "(site, form) combinations -- expected a fixed small count, not "
            "one that scales with sites * forms."
        )


class TestGetSpocSheetsBucketsQueryCount:
    def test_query_count_does_not_scale_with_sites_times_forms(
        self, make_site, make_form, make_reporting_period, make_user,
        make_access_grant, db_session, created_objects, system_user,
    ):
        from app.modules.SUBMIT.service import get_spoc_sheets_buckets

        user = make_user()
        make_access_grant(user, "submission", scope_type="global", can_view=True, can_submit=True)

        sites = [make_site() for _ in range(3)]
        forms = []
        for _ in range(4):
            form, form_version = make_form()
            forms.append(form)
        for site in sites:
            make_reporting_period(site)

        _make_live_workbook(db_session, created_objects, system_user, forms, sites, submitter=user)

        with count_queries() as counter:
            result = get_spoc_sheets_buckets(user.id)

        # 3 sites x 4 forms x 1 period = 12 "not started" combinations expected.
        assert len(result["not_started"]) == 12
        assert counter["n"] < 15, (
            f"get_spoc_sheets_buckets ran {counter['n']} queries for 12 "
            "(site, form) combinations -- expected a fixed small count, not "
            "one that scales with sites * forms."
        )


class TestGetApproverQueueQueryCount:
    def test_query_count_does_not_scale_with_ineligible_submissions_system_wide(
        self, make_form, make_field, make_site, make_reporting_period, make_workflow,
        make_user, make_submission, make_access_grant, db_session, created_objects,
    ):
        """
        The specific bug: get_approver_queue loaded every reviewable submission
        system-wide with no site filter at the SQL level. This holds the
        number of submissions this approver is actually eligible for FIXED at
        2 (each costing a real, unavoidable has_permission + workflow-level-
        approver check -- that part isn't and shouldn't be batched away, see
        the comment in get_approver_queue on not reimplementing AccessMatrix
        scoping), while scaling up the number of *other* reviewable
        submissions at sites this approver has no grant for at all. Those
        must be excluded at the SQL query itself, not loaded and filtered out
        in Python -- so the query count must not grow with them.
        """
        from app.modules.APPROV.service import get_approver_queue

        approver = make_user()
        submitter = make_user()

        def add_eligible_submission():
            form, form_version = make_form()
            make_field(form, form_version, "field_a", field_type="number")
            site = make_site()
            make_access_grant(approver, "submission", scope_type="site", scope_site_id=site.id, can_approve=True)
            period = make_reporting_period(site)
            workflow_version = make_workflow([approver])
            make_submission(
                site, form, form_version, period, workflow_version,
                status="Submitted", submitted_by=submitter, current_level=1,
            )

        def add_noise_submission():
            # Reviewable, but at a site this approver has no grant for at all.
            form, form_version = make_form()
            make_field(form, form_version, "field_a", field_type="number")
            site = make_site()
            period = make_reporting_period(site)
            workflow_version = make_workflow([make_user()])
            make_submission(
                site, form, form_version, period, workflow_version,
                status="Submitted", submitted_by=submitter, current_level=1,
            )

        for _ in range(2):
            add_eligible_submission()

        with count_queries() as small_counter:
            small_result = get_approver_queue(approver.id)

        for _ in range(6):
            add_noise_submission()

        with count_queries() as large_counter:
            large_result = get_approver_queue(approver.id)

        assert len(small_result) == 2
        assert len(large_result) == 2
        assert large_counter["n"] == small_counter["n"], (
            f"query count went from {small_counter['n']} to {large_counter['n']} "
            "after adding 6 more reviewable submissions at sites this approver "
            "has no access to -- those must be excluded by the SQL site "
            "filter, not loaded and discarded in Python."
        )
