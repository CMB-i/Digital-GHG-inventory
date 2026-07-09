"""
Priority 2: permission scoping -- the class of bug that caused the
notification-link investigation (global-only permission decorators silently
blocking site-scoped-only users, and the entity_type == "all" wildcard being
missed by hand-rolled AccessMatrix queries).
"""
import pytest

from app.common.permissions import has_permission
from app.modules.ACCESS.service import get_user_permissions


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

        resp = client.get("/module/SUBMIT/")
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
