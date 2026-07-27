"""
_resolve_notification_link()'s reporting_period branch builds a
/module/SUBMIT/annual deep link. annual_workbook.js hard-requires a
workbook_id to render anything at all (see its "Missing workbook context"
dead-end), so a link built without one is silently broken even when the
user's site access/assignment data is otherwise correct.
_annual_workbook_link() resolves workbook_id via
_get_user_live_workbooks_for_site() -- these tests cover both the resolvable
(exactly one live workbook at the site) and ambiguous (zero) cases.
"""
from types import SimpleNamespace

from app.modules.NOTIFY.views import _resolve_notification_link


class TestReportingPeriodNotificationLink:
    def test_includes_workbook_id_when_exactly_one_workbook_assigned(
        self, make_site, make_form, make_workbook, make_user, make_access_grant,
        make_reporting_period,
    ):
        site = make_site()
        form, _form_version = make_form()
        user = make_user()
        workbook = make_workbook(form, site, submitters=[user])
        make_access_grant(
            user, "submission", scope_type="global",
            can_view=True, can_create=True, can_edit=True, can_submit=True,
        )

        period = make_reporting_period(site, year=2026, month=6, status="OPEN")

        notification = SimpleNamespace(entity_type="reporting_period", entity_id=period.id)
        link = _resolve_notification_link(notification, user)

        assert link.startswith("/module/SUBMIT/annual?")
        assert f"site_id={site.id}" in link
        assert f"workbook_id={workbook.id}" in link
        assert "fy=2026" in link
        assert "month=6" in link

    def test_falls_back_to_my_workbooks_when_no_workbook_assigned(
        self, make_site, make_user, make_access_grant, make_reporting_period,
    ):
        """AccessMatrix grants site access, but there's no WorkbookSiteSubmitter
        assignment for this user at this site -- genuinely ambiguous/incomplete,
        so the link must not be a broken /module/SUBMIT/annual link missing a
        workbook_id; it should fall back to the plain My Workbooks page
        instead, where the user can see (and an admin can act on) the actual
        assignment gap."""
        site = make_site()
        user = make_user()
        make_access_grant(
            user, "submission", scope_type="global",
            can_view=True, can_create=True, can_edit=True, can_submit=True,
        )

        period = make_reporting_period(site, year=2026, month=6, status="OPEN")

        notification = SimpleNamespace(entity_type="reporting_period", entity_id=period.id)
        link = _resolve_notification_link(notification, user)

        assert link == "/module/SUBMIT/"

    def test_no_permission_returns_placeholder_link(
        self, make_site, make_user, make_reporting_period,
    ):
        """No AccessMatrix submission grant at all -- can_enter is False, so
        this must stay the existing "#" placeholder, unchanged by this fix."""
        site = make_site()
        user = make_user()

        period = make_reporting_period(site, year=2026, month=6, status="OPEN")

        notification = SimpleNamespace(entity_type="reporting_period", entity_id=period.id)
        link = _resolve_notification_link(notification, user)

        assert link == "#"
