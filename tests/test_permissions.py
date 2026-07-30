"""
Priority 2: permission scoping -- the class of bug that caused the
notification-link investigation (global-only permission decorators silently
blocking site-scoped-only users, and the entity_type == "all" wildcard being
missed by hand-rolled AccessMatrix queries).
"""
import pytest
from sqlalchemy import text

from app.common.permissions import has_permission
from app.modules.ACCESS.service import build_permission_matrix, get_user_permissions, upsert_access_row


ACCESS_UNIQUE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_access_matrix_permission_scope
ON access_matrix (
    user_id,
    scope_type,
    coalesce(scope_site_id, 0),
    coalesce(scope_region_id, 0),
    entity_type,
    coalesce(entity_id, 0)
)
WHERE is_deleted = false
"""


class TestHasPermissionScoping:
    def test_global_grant_allows_any_site(self, make_user, make_access_grant, make_site):
        user = make_user()
        make_access_grant(user, "submission", scope_type="global", can_view=True)
        site = make_site()

        assert has_permission(user.id, "submission", "view", scope_site_id=site.id) is True
        assert has_permission(user.id, "submission", "view") is True  # global check too

    def test_site_scoped_grant_only_allows_that_site(self, make_user, make_access_grant, make_site):
        user = make_user()
        site_a = make_site()
        site_b = make_site()
        make_access_grant(user, "submission", scope_type="site", scope_site_id=site_a.id, can_view=True)

        assert has_permission(user.id, "submission", "view", scope_site_id=site_a.id) is True
        assert has_permission(user.id, "submission", "view", scope_site_id=site_b.id) is False

    def test_site_scoped_grant_does_not_satisfy_global_check(self, make_user, make_access_grant, make_site):
        user = make_user()
        site = make_site()
        make_access_grant(user, "submission", scope_type="site", scope_site_id=site.id, can_view=True)

        # A check with no scope_site_id means "does the user have a global grant" --
        # a site-scoped-only grant must not satisfy that.
        assert has_permission(user.id, "submission", "view") is False

    def test_no_grant_at_all_is_blocked(self, make_user, make_site):
        user = make_user()
        site = make_site()
        assert has_permission(user.id, "submission", "view", scope_site_id=site.id) is False

    def test_entity_type_all_wildcard_grants_any_entity_type(self, make_user, make_access_grant, make_site):
        user = make_user()
        site = make_site()
        make_access_grant(user, "all", scope_type="site", scope_site_id=site.id, can_view=True, can_approve=True)

        assert has_permission(user.id, "submission", "view", scope_site_id=site.id) is True
        assert has_permission(user.id, "report", "view", scope_site_id=site.id) is True
        assert has_permission(user.id, "submission", "approve", scope_site_id=site.id) is True

    def test_unrelated_entity_type_does_not_grant_access(self, make_user, make_access_grant, make_site):
        user = make_user()
        site = make_site()
        make_access_grant(user, "site", scope_type="site", scope_site_id=site.id, can_view=True)

        assert has_permission(user.id, "submission", "view", scope_site_id=site.id) is False

    def test_get_user_permissions_ors_wildcard_alongside_specific_entity_type(self, make_user, make_access_grant, make_site):
        user = make_user()
        site = make_site()
        # can_view via the specific entity type, can_approve only via the wildcard.
        make_access_grant(user, "submission", scope_type="site", scope_site_id=site.id, can_view=True)
        make_access_grant(user, "all", scope_type="site", scope_site_id=site.id, can_approve=True)

        perms = get_user_permissions(user_id=user.id, scope_type="site", scope_site_id=site.id, entity_type="submission")
        assert perms["can_view"] is True
        assert perms["can_approve"] is True

    def test_duplicate_active_rows_are_collapsed_when_revoked(
        self, db_session, make_user, system_user,
    ):
        from app.modules.ACCESS.model import AccessMatrix

        db_session.execute(text("DROP INDEX IF EXISTS uq_active_access_matrix_permission_scope"))
        db_session.commit()
        user = None
        try:
            user = make_user()
            for _ in range(2):
                db_session.add(
                    AccessMatrix(
                        user_id=user.id,
                        scope_type="global",
                        entity_type="submission",
                        can_view=True,
                        created_by=system_user,
                        updated_by=system_user,
                    )
                )
            db_session.flush()
            assert has_permission(user.id, "submission", "view") is True

            upsert_access_row(
                user_id=user.id,
                scope_type="global",
                scope_site_id=None,
                entity_type="submission",
                permission_values={"can_view": False},
                actor_id=system_user,
            )
            db_session.flush()

            assert has_permission(user.id, "submission", "view") is False
            active_rows = AccessMatrix.query.filter_by(
                user_id=user.id,
                scope_type="global",
                entity_type="submission",
                is_deleted=False,
            ).all()
            assert len(active_rows) == 1
            assert active_rows[0].can_view is False
        finally:
            if user is not None:
                db_session.execute(text("DELETE FROM access_matrix WHERE user_id = :user_id"), {"user_id": user.id})
            db_session.execute(text(ACCESS_UNIQUE_INDEX_SQL))
            db_session.commit()

    def test_user_creation_writes_non_sensitive_audit_log(
        self, db_session, make_user, created_objects,
    ):
        from app.modules.AUDITL.model import AuditLog
        from app.modules.USRMGMT.service import create_user

        actor = make_user()
        temporary_password = "TempPass123!"
        user = create_user(
            full_name="Created User",
            email="created-user@example.com",
            phone="9876543210",
            temporary_password=temporary_password,
            actor_id=actor.id,
        )
        db_session.flush()
        created_objects.append(user)

        audit = AuditLog.query.filter_by(
            entity_type="user",
            entity_id=str(user.id),
            action="USER_CREATED",
        ).one()
        assert audit.actor_user_id == actor.id
        assert set(audit.new_values.keys()) == {"id", "full_name", "email", "phone", "is_active"}
        assert audit.new_values["id"] == user.id
        assert audit.new_values["email"] == "created-user@example.com"
        payload = f"{audit.old_values} {audit.new_values} {audit.metadata_json}"
        assert temporary_password not in payload
        assert "password" not in payload.lower()

    def test_wildcard_all_grant_can_be_created_edited_and_revoked_through_access_service(
        self, db_session, make_user, system_user,
    ):
        user = make_user()

        row = upsert_access_row(
            user_id=user.id,
            scope_type="global",
            scope_site_id=None,
            entity_type="all",
            permission_values={"can_view": True},
            actor_id=system_user,
        )
        db_session.flush()
        assert row.entity_type == "all"
        assert has_permission(user.id, "report", "view") is True
        assert build_permission_matrix(user.id, "global")["all"]["can_view"] is True

        upsert_access_row(
            user_id=user.id,
            scope_type="global",
            scope_site_id=None,
            entity_type="all",
            permission_values={"can_view": True, "can_export": True},
            actor_id=system_user,
        )
        db_session.flush()
        assert has_permission(user.id, "report", "export") is True

        upsert_access_row(
            user_id=user.id,
            scope_type="global",
            scope_site_id=None,
            entity_type="all",
            permission_values={},
            actor_id=system_user,
        )
        db_session.flush()
        assert has_permission(user.id, "report", "view") is False
        assert has_permission(user.id, "report", "export") is False


@pytest.fixture()
def site_scoped_submitter_setup(
    make_user, make_site, make_access_grant, make_form, make_field, make_reporting_period,
    make_workflow, make_workbook, make_submission,
):
    """
    A user with an AccessMatrix submission grant at exactly one site, plus a
    WorkbookSiteSubmitter assignment there (both required per the SUBMIT
    module's AND requirement -- see README), and one Draft submission of
    their own at that site.
    """
    form, form_version = make_form()
    make_field(form, form_version, "field_a", field_type="number")

    submitter = make_user()
    approver = make_user()
    allowed_site = make_site()
    other_site = make_site()
    period = make_reporting_period(allowed_site)
    workflow_version = make_workflow([approver])
    make_workbook(form, allowed_site, workflow_version=workflow_version, submitters=[submitter])

    make_access_grant(submitter, "submission", scope_type="site", scope_site_id=allowed_site.id, can_view=True, can_submit=True, can_edit=True)

    submission = make_submission(allowed_site, form, form_version, period, workflow_version, status="Draft", submitted_by=None)

    return {
        "submitter": submitter,
        "allowed_site": allowed_site,
        "other_site": other_site,
        "submission": submission,
    }


class TestSiteScopedSubmitterAccess:
    def test_can_access_own_submission_and_dashboard(self, client, site_scoped_submitter_setup):
        ctx = site_scoped_submitter_setup
        with client.session_transaction() as sess:
            sess["user_id"] = ctx["submitter"].id

        # Single-site users skip the dashboard entirely and land straight in
        # their one workbook (see app/modules/SUBMIT/views.py::index).
        resp = client.get("/module/SUBMIT/")
        assert resp.status_code == 302
        assert resp.headers["Location"].startswith("/module/SUBMIT/annual?")

        resp = client.get(resp.headers["Location"])
        assert resp.status_code == 200

        resp = client.get("/module/SUBMIT/api/sheets")
        assert resp.status_code == 200

        resp = client.get(f"/module/SUBMIT/submissions/{ctx['submission'].id}")
        assert resp.status_code in (200, 302)  # 302 if it redirects to the edit page

    def test_blocked_from_unrelated_site(self, client, site_scoped_submitter_setup, make_access_grant):
        """
        A user with access ONLY at allowed_site must not be able to view a
        submission at other_site, even via has_permission's scope check.
        """
        ctx = site_scoped_submitter_setup
        assert has_permission(ctx["submitter"].id, "submission", "view", scope_site_id=ctx["other_site"].id) is False

    def test_user_with_zero_access_is_blocked_from_dashboard(self, client, make_user):
        stranger = make_user()
        with client.session_transaction() as sess:
            sess["user_id"] = stranger.id

        resp = client.get("/module/SUBMIT/", follow_redirects=False)
        assert resp.status_code == 403


class TestWildcardGrantAuthorizationDecisions:
    def test_wildcard_approve_grant_drives_landing_nav_and_approv_index(
        self, client, make_user, make_access_grant,
    ):
        user = make_user()
        make_access_grant(user, "all", scope_type="global", can_approve=True)
        with client.session_transaction() as sess:
            sess["user_id"] = user.id

        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/module/APPROV/")

        resp = client.get("/module/APPROV/")
        assert resp.status_code == 200
        assert b"Review Queue" in resp.data

    def test_wildcard_submission_grant_is_honored_by_submit_list_helpers(
        self, make_user, make_site, make_access_grant, make_form, make_field,
        make_reporting_period, make_workflow, make_workbook,
    ):
        from app.modules.SUBMIT.service import _user_submission_site_ids, get_spoc_sheets_buckets

        submitter = make_user()
        approver = make_user()
        site = make_site()
        form, form_version = make_form()
        make_field(form, form_version, "field_a", field_type="number")
        make_reporting_period(site)
        workflow_version = make_workflow([approver])
        make_workbook(form, site, workflow_version=workflow_version, submitters=[submitter])
        make_access_grant(
            submitter,
            "all",
            scope_type="site",
            scope_site_id=site.id,
            can_view=True,
            can_submit=True,
        )

        assert site.id in _user_submission_site_ids(submitter.id)

        buckets = get_spoc_sheets_buckets(submitter.id)
        bucket_site_ids = {
            item["site_id"]
            for bucket_name in ("action_needed", "not_started", "submitted")
            for item in buckets[bucket_name]
        }
        assert site.id in bucket_site_ids
        assert buckets["needs_submitter_assignment"] is False


class TestRptbldRouteScoping:
    def _make_template(self, db_session, created_objects, system_user, site):
        from app.modules.RPTBLD.model import ReportTemplate

        template = ReportTemplate(
            name=f"Site Report {site.id}",
            code=f"site-report-{site.id}",
            scope_type="site",
            scope_site_id=site.id,
            config_json={"site_ids": [site.id]},
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(template)
        db_session.flush()
        created_objects.append(template)
        return template

    def _login(self, client, user):
        with client.session_transaction() as sess:
            sess["user_id"] = user.id

    def test_global_report_access_can_load_report_template(
        self, client, make_user, make_site, make_access_grant, db_session,
        created_objects, system_user,
    ):
        site = make_site()
        template = self._make_template(db_session, created_objects, system_user, site)
        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_view=True)
        self._login(client, user)

        resp = client.get(f"/module/RPTBLD/api/templates/{template.id}")
        assert resp.status_code == 200

    def test_site_scoped_report_access_can_load_matching_report_template(
        self, client, make_user, make_site, make_access_grant, db_session,
        created_objects, system_user,
    ):
        site = make_site()
        template = self._make_template(db_session, created_objects, system_user, site)
        user = make_user()
        make_access_grant(user, "report", scope_type="site", scope_site_id=site.id, can_view=True)
        self._login(client, user)

        resp = client.get(f"/module/RPTBLD/api/templates/{template.id}")
        assert resp.status_code == 200

    def test_site_scoped_report_access_is_denied_for_different_site_template(
        self, client, make_user, make_site, make_access_grant, db_session,
        created_objects, system_user,
    ):
        allowed_site = make_site()
        other_site = make_site()
        template = self._make_template(db_session, created_objects, system_user, other_site)
        user = make_user()
        make_access_grant(
            user,
            "report",
            scope_type="site",
            scope_site_id=allowed_site.id,
            can_view=True,
        )
        self._login(client, user)

        resp = client.get(f"/module/RPTBLD/api/templates/{template.id}")
        assert resp.status_code == 403
