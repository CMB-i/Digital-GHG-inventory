"""
delete_workflow() (app/modules/WFLWBLD/service.py) already existed with a real
dependency check, but nothing in the product could reach it -- WFLWBLD's own
standalone builder UI is disabled (before_request 404 hook, see README), so
this is wired up instead through WKBK's chain editor, the actually-live
configuration surface, via a new DELETE /workbooks/api/<id>/chain route
(app/modules/WKBK/views.py::api_delete_chain). These tests exercise that
route: permission enforcement, the blocked-delete path when another active
workbook still points at the same workflow, and a clean delete when it
doesn't.
"""
from app.modules.WFLWBLD.model import Workflow
from app.modules.WKBK.model import Workbook


def _grant_manage_forms(make_access_grant, user):
    make_access_grant(user, "form", scope_type="global", can_manage_forms=True)


class TestDeleteChainRoutePermission:
    def test_delete_blocked_without_manage_forms_permission(
        self, client, make_user, make_form, make_site, make_workflow, make_workbook,
    ):
        form, _fv = make_form()
        site = make_site()
        workflow_version = make_workflow([])
        workbook = make_workbook(form, site, workflow_version=workflow_version)

        stranger = make_user()
        with client.session_transaction() as sess:
            sess["user_id"] = stranger.id

        resp = client.delete(f"/workbooks/api/{workbook.id}/chain")
        assert resp.status_code == 403

        assert Workbook.query.get(workbook.id).workflow_id == workflow_version.workflow_id


class TestDeleteChainBlockedByOtherActiveWorkbook:
    def test_delete_blocked_when_another_active_workbook_still_uses_it(
        self, client, make_user, make_access_grant, make_form, make_site, make_workflow, make_workbook, db_session,
    ):
        form_a, _fva = make_form()
        form_b, _fvb = make_form()
        site_a = make_site()
        site_b = make_site()
        workflow_version = make_workflow([])

        workbook_a = make_workbook(form_a, site_a, workflow_version=workflow_version)
        workbook_b = make_workbook(form_b, site_b, workflow_version=workflow_version)

        actor = make_user()
        _grant_manage_forms(make_access_grant, actor)

        # The route rolls back on the ValueError this test expects to trigger
        # -- commit the setup first so that rollback only undoes the failed
        # delete attempt, not this test's own fixture data (everything in this
        # test otherwise shares one uncommitted transaction).
        db_session.commit()

        with client.session_transaction() as sess:
            sess["user_id"] = actor.id

        resp = client.delete(f"/workbooks/api/{workbook_a.id}/chain")
        assert resp.status_code == 400
        assert "still using it" in resp.get_json()["error"]
        assert workbook_b.name in resp.get_json()["error"]

        # Blocked delete must roll back cleanly -- workbook_a keeps its
        # original assignment rather than being left detached with no workflow.
        assert Workbook.query.get(workbook_a.id).workflow_id == workflow_version.workflow_id
        assert Workflow.query.filter_by(id=workflow_version.workflow_id, is_deleted=False).first() is not None


class TestDeleteChainSucceedsWhenUnreferenced:
    def test_delete_succeeds_and_clears_the_workbook_assignment(
        self, client, make_user, make_access_grant, make_form, make_site, make_workflow, make_workbook,
    ):
        form, _fv = make_form()
        site = make_site()
        workflow_version = make_workflow([])
        workbook = make_workbook(form, site, workflow_version=workflow_version)
        workflow_id = workflow_version.workflow_id

        actor = make_user()
        _grant_manage_forms(make_access_grant, actor)
        with client.session_transaction() as sess:
            sess["user_id"] = actor.id

        resp = client.delete(f"/workbooks/api/{workbook.id}/chain")
        assert resp.status_code == 200
        assert "error" not in resp.get_json()

        assert Workbook.query.get(workbook.id).workflow_id is None
        assert Workflow.query.filter_by(id=workflow_id, is_deleted=False).first() is None
        deleted_workflow = Workflow.query.get(workflow_id)
        assert deleted_workflow.is_deleted is True
