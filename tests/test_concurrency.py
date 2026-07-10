"""
Row-locking regression tests: two real threads, each with its own Flask app
context (and therefore its own DB session/connection), racing the same row
through the actual service functions -- not a single-threaded simulation.

This needs a real Postgres backend to mean anything (SELECT ... FOR UPDATE
blocking behavior can't be faithfully reproduced by a single-threaded test),
which is exactly what this project's test database already is (see
conftest.py's module docstring).

Setup rows are created via the fixtures' normal (main-thread) db_session, but
must be explicitly committed before any worker thread starts: each thread gets
an independent connection, and an uncommitted row in the main thread's
transaction is invisible to those connections until it's committed. Likewise,
db_session.expire_all() is required before asserting on final state, since
Query.get()/already-loaded ORM objects can otherwise return the main thread's
stale, pre-race copy instead of re-querying.
"""
import threading

import pytest

from app.database import db
from app.modules.APPROV.model import ApprovalAction
from app.modules.APPROV.service import approve_submission
from app.modules.SUBMIT.model import Submission
from app.modules.SUBMIT.service import submit_submission


def _grant(make_access_grant, user, site, action_flag):
    make_access_grant(user, "submission", scope_type="site", scope_site_id=site.id, **{action_flag: True})


def _run_concurrently(*workers):
    """Runs each zero-arg callable in its own thread, synchronized to start
    together via a barrier, and returns after both have finished."""
    barrier = threading.Barrier(len(workers))

    def wrap(fn):
        def runner():
            barrier.wait()
            fn()
        return runner

    threads = [threading.Thread(target=wrap(fn)) for fn in workers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


class TestConcurrentSubmitSubmission:
    def test_only_one_of_two_concurrent_submits_succeeds(
        self, app, make_form, make_field, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_access_grant, db_session,
    ):
        form, form_version = make_form()
        make_field(form, form_version, "field_a", field_type="number")

        submitter = make_user()
        approver = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([approver])
        _grant(make_access_grant, submitter, site, "can_submit")

        submission = make_submission(site, form, form_version, period, workflow_version, status="Draft")
        # Must be committed -- see module docstring.
        db_session.commit()

        results = []

        def worker():
            with app.app_context():
                try:
                    submit_submission(submission.id, submitter.id)
                    db.session.commit()
                    results.append(("ok", None))
                except Exception as exc:
                    db.session.rollback()
                    results.append(("error", str(exc)))

        _run_concurrently(worker, worker)

        oks = [r for r in results if r[0] == "ok"]
        errors = [r for r in results if r[0] == "error"]
        assert len(oks) == 1, results
        assert len(errors) == 1, results
        assert "Cannot submit submission in status" in errors[0][1]

        db_session.expire_all()
        refreshed = Submission.query.get(submission.id)
        assert refreshed.status == "Submitted"


class TestConcurrentApproveSubmission:
    def test_only_one_of_two_concurrent_approvals_finalizes(
        self, app, make_form, make_field, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_access_grant, db_session,
    ):
        form, form_version = make_form()
        make_field(form, form_version, "field_a", field_type="number")

        submitter = make_user()
        approver_1 = make_user()
        approver_2 = make_user()
        site = make_site()
        period = make_reporting_period(site)
        # Single ANY_ONE level, both approvers eligible -- either one alone can
        # finalize a single-level workflow.
        workflow_version = make_workflow([approver_1, approver_2], approval_mode="ANY_ONE")
        _grant(make_access_grant, approver_1, site, "can_approve")
        _grant(make_access_grant, approver_2, site, "can_approve")

        submission = make_submission(
            site, form, form_version, period, workflow_version,
            status="Submitted", submitted_by=submitter, current_level=1,
        )
        # Must be committed -- see module docstring.
        db_session.commit()

        results = []

        def make_worker(user_id):
            def worker():
                with app.app_context():
                    try:
                        approve_submission(submission.id, user_id)
                        db.session.commit()
                        results.append(("ok", user_id))
                    except Exception as exc:
                        db.session.rollback()
                        results.append(("error", str(exc)))
            return worker

        _run_concurrently(make_worker(approver_1.id), make_worker(approver_2.id))

        oks = [r for r in results if r[0] == "ok"]
        errors = [r for r in results if r[0] == "error"]
        assert len(oks) == 1, results
        assert len(errors) == 1, results
        assert "Cannot approve submission in status" in errors[0][1]

        db_session.expire_all()
        refreshed = Submission.query.get(submission.id)
        assert refreshed.status == "Approved"
        assert refreshed.approved_by == oks[0][1]

        approvals = ApprovalAction.query.filter_by(
            submission_id=submission.id, action="Approve", is_deleted=False
        ).all()
        assert len(approvals) == 1
