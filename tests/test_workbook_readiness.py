import pytest

from app.modules.WKBK.model import WorkbookSiteSubmitter
from app.modules.WKBK.service import add_site_submitter, check_workbook_readiness


def test_workbook_readiness_passes_when_assigned_submitter_has_submission_permission(
    make_user, make_site, make_access_grant, make_form, make_field,
    make_workflow, make_workbook,
):
    submitter = make_user()
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    make_field(form, form_version, "field_a")
    workflow_version = make_workflow([approver])
    workbook = make_workbook(form, site, workflow_version=workflow_version, submitters=[submitter])
    make_access_grant(submitter, "submission", scope_type="site", scope_site_id=site.id, can_submit=True)

    checklist = check_workbook_readiness(workbook.id)

    assert checklist["submitters"]["ok"] is True
    assert checklist["all_ok"] is True


def test_workbook_readiness_fails_when_assigned_submitter_lacks_submission_permission(
    make_user, make_site, make_form, make_field, make_workflow,
    make_workbook,
):
    submitter = make_user(email="invalid-submit-permission@example.com")
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    make_field(form, form_version, "field_a")
    workflow_version = make_workflow([approver])
    workbook = make_workbook(form, site, workflow_version=workflow_version, submitters=[submitter])

    checklist = check_workbook_readiness(workbook.id)

    assert checklist["submitters"]["ok"] is False
    assert checklist["all_ok"] is False
    assert "invalid-submit-permission@example.com" in checklist["submitters"]["detail"]
    assert "cannot submit" in checklist["submitters"]["detail"]


def test_add_site_submitter_rejects_user_without_submission_permission(
    make_user, make_site, make_form, make_field, make_workflow,
    make_workbook,
):
    submitter = make_user()
    actor = make_user()
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    make_field(form, form_version, "field_a")
    workflow_version = make_workflow([approver])
    workbook = make_workbook(form, site, workflow_version=workflow_version)

    with pytest.raises(ValueError, match="submission permission"):
        add_site_submitter(workbook.id, site.id, submitter.id, actor.id)


def test_add_site_submitter_accepts_user_with_submission_permission(
    make_user, make_site, make_access_grant, make_form, make_field, make_workflow,
    make_workbook, created_objects,
):
    submitter = make_user()
    actor = make_user()
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    make_field(form, form_version, "field_a")
    workflow_version = make_workflow([approver])
    workbook = make_workbook(form, site, workflow_version=workflow_version)
    make_access_grant(submitter, "submission", scope_type="site", scope_site_id=site.id, can_submit=True)

    row = add_site_submitter(workbook.id, site.id, submitter.id, actor.id)
    created_objects.append(row)

    assert WorkbookSiteSubmitter.query.filter_by(
        workbook_id=workbook.id,
        site_id=site.id,
        user_id=submitter.id,
    ).one() == row
