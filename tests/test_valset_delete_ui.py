"""
Tests for the Value Set delete route (app/modules/VALSET/views.py). delete_value_set()
itself (service.py) already has its dependency check and reason-required validation
covered elsewhere -- these tests exercise the HTTP route that was newly wired up to it:
permission enforcement, the server-side reason-required rule, and the full
route -> service -> response flow for both a clean delete and one blocked by an
active field reference.
"""
from datetime import date

import pytest

from app.modules.VALSET.model import ValueSet, ValueSetVersion


@pytest.fixture()
def value_set_with_draft_version(make_user, db_session, created_objects, system_user):
    author = make_user()
    vs = ValueSet(name="Test VS", code=f"test-vs-ui-{author.id}", created_by=system_user, updated_by=system_user)
    db_session.add(vs)
    db_session.flush()
    created_objects.append(vs)

    version = ValueSetVersion(
        value_set_id=vs.id, version_number=1, status="Draft",
        effective_from=date.today(), created_by=author.id,
    )
    db_session.add(version)
    db_session.flush()
    created_objects.append(version)

    return vs, version, author


class TestValueSetDeleteRoutePermission:
    def test_delete_blocked_without_manage_forms_permission(self, client, make_user, value_set_with_draft_version):
        vs, _version, _author = value_set_with_draft_version
        stranger = make_user()
        with client.session_transaction() as sess:
            sess["user_id"] = stranger.id

        resp = client.delete(f"/module/VALSET/api/{vs.id}", json={"reason": "cleanup"})
        assert resp.status_code == 403

        assert ValueSet.query.filter_by(id=vs.id, is_deleted=False).first() is not None


class TestValueSetDeleteReasonRequired:
    def test_delete_without_reason_is_rejected_server_side(
        self, client, make_access_grant, value_set_with_draft_version,
    ):
        vs, _version, author = value_set_with_draft_version
        make_access_grant(author, "value_set", scope_type="global", can_manage_forms=True)
        with client.session_transaction() as sess:
            sess["user_id"] = author.id

        resp = client.delete(f"/module/VALSET/api/{vs.id}", json={})
        assert resp.status_code == 400
        assert "reason" in resp.get_json()["error"].lower()

        assert ValueSet.query.filter_by(id=vs.id, is_deleted=False).first() is not None


class TestValueSetDeleteEndToEnd:
    def test_successful_delete_removes_it_from_the_list(
        self, client, make_access_grant, value_set_with_draft_version,
    ):
        vs, _version, author = value_set_with_draft_version
        make_access_grant(author, "value_set", scope_type="global", can_manage_forms=True, can_view=True)
        with client.session_transaction() as sess:
            sess["user_id"] = author.id

        resp = client.delete(f"/module/VALSET/api/{vs.id}", json={"reason": "no longer needed"})
        assert resp.status_code == 200
        assert "error" not in resp.get_json()

        listed = client.get("/module/VALSET/api").get_json()
        assert all(item["id"] != vs.id for item in listed)

    def test_blocked_delete_surfaces_the_field_reference_count(
        self, client, make_access_grant, make_form, make_field, value_set_with_draft_version,
    ):
        vs, version, author = value_set_with_draft_version
        make_access_grant(author, "value_set", scope_type="global", can_manage_forms=True)

        form, form_version = make_form()
        make_field(
            form, form_version, "dropdown_field", field_type="dropdown",
            field_config={"value_set_version_id": version.id},
        )

        with client.session_transaction() as sess:
            sess["user_id"] = author.id

        resp = client.delete(f"/module/VALSET/api/{vs.id}", json={"reason": "no longer needed"})
        assert resp.status_code == 400
        assert "Cannot delete value set" in resp.get_json()["error"]

        assert ValueSet.query.filter_by(id=vs.id, is_deleted=False).first() is not None
