"""
resolve_entity_details() (app/modules/AUDITL/service.py) wraps all of its
entity-description building in a broad try/except Exception: pass. That's how
the WorkbookSite.is_deleted bug (fixed alongside these tests -- see below)
degraded silently instead of surfacing anywhere. An audit of every attribute
access in this function (Submission/Form/Site/ReportingPeriod/Workbook/
WorkbookSite/SubmissionPackage/User/AccessMatrix, all cross-checked against
their actual model columns) found no other currently-live bug of the same
class. Every "entity legitimately doesn't exist" case in this function is
already handled without raising at all, via `if sub:` / `if user:` / etc.
guards -- so there is no genuinely-expected exception case being silenced
here; anything the broad except catches is, by construction, an unexpected
bug. These tests confirm that such a failure now gets logged (instead of
silently vanishing) while the user-facing fallback behavior is unchanged.
"""
from datetime import date

from app.modules.AUDITL.service import resolve_entity_details
from app.modules.WKBK.model import WorkbookSite


def _submission_scenario(make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission):
    form, form_version = make_form()
    site = make_site()
    period = make_reporting_period(site)
    workflow_version = make_workflow([])
    workbook = make_workbook(form, site, workflow_version=workflow_version)
    submission = make_submission(site, form, form_version, period, workflow_version, status="Draft")
    return form, site, period, workbook, submission


class TestResolveEntityDetailsHappyPath:
    """Confirms the WorkbookSite.is_deleted fix: the label is fully populated
    when the WorkbookSite link genuinely exists, and degrades gracefully
    (just omitting "Workbook: ...") once it's hard-deleted -- without
    crashing either way."""

    def test_includes_workbook_when_workbooksite_link_exists(
        self, make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission,
    ):
        form, site, period, workbook, submission = _submission_scenario(
            make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission
        )

        label = resolve_entity_details("submission", str(submission.id))

        assert f"Workbook: {workbook.name}" in label
        assert f"Sheet: {form.name}" in label
        assert f"Site: {site.name}" in label

    def test_degrades_gracefully_when_workbooksite_hard_deleted(
        self, make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission, db_session,
    ):
        form, site, period, workbook, submission = _submission_scenario(
            make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission
        )

        WorkbookSite.query.filter_by(workbook_id=workbook.id, site_id=site.id).delete()
        db_session.flush()

        label = resolve_entity_details("submission", str(submission.id))

        assert "Workbook:" not in label
        assert f"Sheet: {form.name}" in label
        assert f"Site: {site.name}" in label


class TestResolveEntityDetailsLogsUnexpectedFailures:
    def test_exception_is_logged_but_fallback_is_still_returned(
        self, make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission,
        monkeypatch,
    ):
        from unittest.mock import MagicMock
        import app.modules.AUDITL.service as auditl_service
        import app.modules.SUBMIT.service as submit_service

        _form, _site, _period, _workbook, submission = _submission_scenario(
            make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission
        )

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated unexpected failure")

        # format_period_label is imported locally inside resolve_entity_details
        # on each call, so patching the module attribute it's re-imported from
        # is enough -- no need to reach into resolve_entity_details itself.
        monkeypatch.setattr(submit_service, "format_period_label", _boom)

        fake_logger = MagicMock()
        monkeypatch.setattr(auditl_service, "_module_logger", lambda: fake_logger)

        label = resolve_entity_details("submission", str(submission.id))

        # Graceful fallback, not a crash and not a partially-built label.
        assert label == f"Submission #{submission.id}"

        fake_logger.exception.assert_called_once()
        logged_message = fake_logger.exception.call_args[0][0]
        assert "submission" in logged_message
        assert str(submission.id) in logged_message
