"""
resolve_entity_details() (app/modules/AUDITL/service.py) used to filter on
WorkbookSite.is_deleted when resolving the "Workbook: ..." detail for a
submission/package audit-log entry. WorkbookSite has no is_deleted column --
it's hard-deleted (see WKBK.remove_site_from_workbook) -- so that filter
raised an AttributeError the moment a workbook/site link had actually been
removed. The outer try/except swallowed the crash but silently discarded the
*entire* label (Sheet/Site/Period included), not just the missing Workbook
part. These tests confirm the label is fully populated when the WorkbookSite
row exists, and degrades gracefully -- just omitting "Workbook: ..." while
keeping everything else -- once that row is gone.
"""
from datetime import date, datetime, timezone

from app.database import db
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


class TestResolveSubmissionEntityDetails:
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

        # Simulate the real hard-delete path (WKBK.remove_site_from_workbook
        # deletes this row outright -- no is_deleted flag to flip).
        WorkbookSite.query.filter_by(workbook_id=workbook.id, site_id=site.id).delete()
        db_session.flush()

        label = resolve_entity_details("submission", str(submission.id))

        assert f"Workbook: {workbook.name}" not in label
        assert "Workbook:" not in label
        assert f"Sheet: {form.name}" in label
        assert f"Site: {site.name}" in label


class TestResolveSubmissionPackageEntityDetails:
    def _make_package(self, db_session, created_objects, system_user, site, period):
        from app.modules.SUBMIT.model import SubmissionPackage

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
        return package

    def test_includes_workbook_when_workbooksite_link_exists(
        self, make_form, make_site, make_reporting_period, make_workflow, make_workbook,
        db_session, created_objects, system_user,
    ):
        form, _fv = make_form()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([])
        workbook = make_workbook(form, site, workflow_version=workflow_version)
        package = self._make_package(db_session, created_objects, system_user, site, period)

        label = resolve_entity_details("submission_package", str(package.id))

        assert f"Workbook: {workbook.name}" in label
        assert f"Site: {site.name}" in label

    def test_degrades_gracefully_when_workbooksite_hard_deleted(
        self, make_form, make_site, make_reporting_period, make_workflow, make_workbook,
        db_session, created_objects, system_user,
    ):
        form, _fv = make_form()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([])
        workbook = make_workbook(form, site, workflow_version=workflow_version)
        package = self._make_package(db_session, created_objects, system_user, site, period)

        WorkbookSite.query.filter_by(workbook_id=workbook.id, site_id=site.id).delete()
        db_session.flush()

        label = resolve_entity_details("submission_package", str(package.id))

        assert "Workbook:" not in label
        assert f"Site: {site.name}" in label
