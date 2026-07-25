"""
Tests for delete_sheet() (app/modules/FORMBLD/service.py) and the DELETE
route it's wired to in FORMBLD/views.py (called from the Workbook detail
page's JS, see static/js/workbooks.js -- FORMBLD's own Sheet Builder page no
longer surfaces this action itself, see workbooks.js/form_builder.js diffs).
Sheet (Form) previously had no delete mechanism at all -- Form.is_deleted
existed on the model but was never written anywhere.

Like Period's delete, this blocks on a Submission of ANY status, not just
in-progress, since RPTBLD may read historical Approved/Locked submissions by
form. It no longer blocks on workbook attachment -- "Reuse existing sheet"
and standalone sheet detachment were both removed, so delete now detaches
the sheet from every workbook that references it (normally at most one, but
legacy sheets attached via the now-removed reuse flow may still have more
than one) as part of one atomic delete, rather than requiring the caller to
detach first.
"""
import pytest

from app.modules.FORMBLD.model import Field, Form
from app.modules.WKBK.model import WorkbookForm
from app.modules.FORMBLD.service import delete_sheet


def _grant_manage_forms(make_access_grant, user, **extra_flags):
    make_access_grant(user, "form", scope_type="global", can_manage_forms=True, **extra_flags)


class TestDeleteSheetDependencyChecks:
    def test_delete_blocked_when_draft_submission_exists(
        self, make_form, make_site, make_reporting_period, make_workflow, make_submission, make_user,
    ):
        form, form_version = make_form()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([])
        actor = make_user()
        make_submission(site, form, form_version, period, workflow_version, status="Draft")

        with pytest.raises(ValueError, match="submission"):
            delete_sheet(form.id, actor.id, "cleanup")

        assert Form.query.filter_by(id=form.id, is_deleted=False).first() is not None

    def test_delete_blocked_when_approved_submission_exists(
        self, make_form, make_site, make_reporting_period, make_workflow, make_submission, make_user,
    ):
        """Approved is NOT in IN_PROGRESS_SUBMISSION_STATUSES -- this proves
        delete_sheet blocks on it anyway, unlike a check scoped to
        in-progress statuses only."""
        form, form_version = make_form()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([])
        actor = make_user()
        make_submission(site, form, form_version, period, workflow_version, status="Approved")

        with pytest.raises(ValueError, match="submission"):
            delete_sheet(form.id, actor.id, "cleanup")

        assert Form.query.filter_by(id=form.id, is_deleted=False).first() is not None

    def test_delete_blocked_without_reason(self, make_form, make_user):
        form, _fv = make_form()
        actor = make_user()

        with pytest.raises(ValueError, match="reason"):
            delete_sheet(form.id, actor.id, "")

        assert Form.query.filter_by(id=form.id, is_deleted=False).first() is not None

    def test_delete_succeeds_when_submission_free(
        self, make_form, make_field, make_user,
    ):
        form, form_version = make_form()
        field_a, _fva = make_field(form, form_version, "field_a")
        field_b, _fvb = make_field(form, form_version, "field_b")
        actor = make_user()

        deleted = delete_sheet(form.id, actor.id, "No longer needed")

        assert deleted.is_deleted is True
        assert deleted.delete_reason == "No longer needed"
        assert Form.query.filter_by(id=form.id, is_deleted=False).first() is None

        # Cascade: every active Field on the sheet is soft-deleted too.
        assert Field.query.filter_by(id=field_a.id, is_deleted=False).first() is None
        assert Field.query.filter_by(id=field_b.id, is_deleted=False).first() is None

    def test_delete_detaches_from_every_workbook_it_is_attached_to(
        self, make_form, make_site, make_workbook, make_user,
    ):
        """Legacy sheets attached to more than one workbook via the now-removed
        "Reuse existing sheet" flow must be detached from all of them as part
        of one atomic delete -- not left dangling in a second workbook
        pointing at a permanently-deleted Form."""
        form, _fv = make_form()
        site_a = make_site()
        site_b = make_site()
        workbook_a = make_workbook(form, site_a)
        workbook_b = make_workbook(form, site_b)
        actor = make_user()

        assert WorkbookForm.query.filter_by(form_id=form.id).count() == 2

        deleted = delete_sheet(form.id, actor.id, "No longer needed")

        assert deleted.is_deleted is True
        assert WorkbookForm.query.filter_by(form_id=form.id).count() == 0
        assert WorkbookForm.query.filter_by(workbook_id=workbook_a.id, form_id=form.id).first() is None
        assert WorkbookForm.query.filter_by(workbook_id=workbook_b.id, form_id=form.id).first() is None


class TestDeleteSheetRoute:
    def test_delete_route_requires_permission(self, client, make_user, make_form):
        form, _fv = make_form()
        stranger = make_user()
        with client.session_transaction() as sess:
            sess["user_id"] = stranger.id

        resp = client.delete(f"/module/FORMBLD/api/{form.id}", json={"reason": "cleanup"})
        assert resp.status_code == 403

        assert Form.query.filter_by(id=form.id, is_deleted=False).first() is not None

    def test_delete_route_succeeds_and_removes_it_from_the_list(
        self, client, make_user, make_access_grant, make_form,
    ):
        form, _fv = make_form()
        actor = make_user()
        _grant_manage_forms(make_access_grant, actor, can_view=True)
        with client.session_transaction() as sess:
            sess["user_id"] = actor.id

        resp = client.delete(f"/module/FORMBLD/api/{form.id}", json={"reason": "No longer needed"})
        assert resp.status_code == 200
        assert "error" not in resp.get_json()

        assert Form.query.filter_by(id=form.id, is_deleted=False).first() is None

        listed = client.get("/module/FORMBLD/api").get_json()
        assert all(item["id"] != form.id for item in listed)

    def test_delete_route_blocked_shows_the_specific_reason(
        self, client, make_user, make_access_grant, make_form, make_site,
        make_reporting_period, make_workflow, make_submission,
    ):
        form, form_version = make_form()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([])
        make_submission(site, form, form_version, period, workflow_version, status="Draft")
        actor = make_user()
        _grant_manage_forms(make_access_grant, actor)
        with client.session_transaction() as sess:
            sess["user_id"] = actor.id

        resp = client.delete(f"/module/FORMBLD/api/{form.id}", json={"reason": "cleanup"})
        assert resp.status_code == 400
        assert "submission" in resp.get_json()["error"]

        assert Form.query.filter_by(id=form.id, is_deleted=False).first() is not None


# See TestDeleteSheetDependencyChecks above for submission/workbook-detach
# checks; this class covers only the published-Formula-reference check on
# delete_sheet's field cascade -- reachable because a calculated field's
# formula can be published referencing a raw field on the same sheet before
# that sheet is ever deleted.
class TestDeleteSheetBlockedByFormulaReference:
    def test_delete_blocked_when_a_field_is_referenced_by_an_active_formula(
        self, make_form, make_field, make_user, created_objects,
    ):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version
        form, form_version = make_form()
        field_a, _fva = make_field(form, form_version, "field_a")
        publisher = make_user()
        formula = create_formula(
            "Diesel Emissions", f"test-sheet-delete-{publisher.id}", "field_a + 1",
            {"field_a": {}}, publisher.id, form_id=form.id,
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
        created_objects.append(version)
        publish_formula_version(version.id, publisher.id)
        actor = make_user()
        with pytest.raises(ValueError, match=formula.name):
            delete_sheet(form.id, actor.id, "cleanup")
        assert Form.query.filter_by(id=form.id, is_deleted=False).first() is not None
        assert Field.query.filter_by(id=field_a.id, is_deleted=False).first() is not None

    def test_delete_succeeds_when_no_field_is_referenced_by_a_formula(
        self, make_form, make_field, make_user,
    ):
        form, form_version = make_form()
        field_a, _fva = make_field(form, form_version, "field_a")
        actor = make_user()
        deleted = delete_sheet(form.id, actor.id, "No longer needed")
        assert deleted.is_deleted is True
        assert Field.query.filter_by(id=field_a.id, is_deleted=False).first() is None
