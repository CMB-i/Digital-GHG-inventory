"""
User-deactivation hardening: a self-deactivation guard on set_user_active,
and a fix for the "zero global admins" loophole that used to be reachable
two ways -- deactivating the last active user with global can_manage_users
(the existing can_deactivate_user guard), or revoking that same flag via the
permission-matrix endpoints (upsert_access_row / save_permission_matrix),
which previously had no guard at all. Both guards now resolve through
ACCESS.service.get_user_permissions()/count_global_user_managers() instead of
a raw AccessMatrix scan, so they can never quietly disagree with each other.
"""
import pytest

from app.common.validators import ValidationError
from app.modules.ACCESS.service import count_global_user_managers, upsert_access_row
from app.modules.USRMGMT.service import can_deactivate_user, set_user_active


class TestSelfDeactivationGuard:
    def test_self_deactivation_blocked_even_when_not_last_admin(self, make_user, make_access_grant):
        actor = make_user()
        other_admin = make_user()
        make_access_grant(actor, "user", can_manage_users=True)
        make_access_grant(other_admin, "user", can_manage_users=True)

        user, error = set_user_active(actor.id, False, actor.id)

        assert user is None
        assert error == "You cannot deactivate your own account."
        assert actor.is_active is True


class TestLastGlobalAdminDeactivationGuard:
    def test_deactivating_the_last_active_global_admin_is_blocked(self, make_user, make_access_grant):
        """Regression: this is the pre-existing can_deactivate_user behavior,
        now resolved via get_user_permissions()/count_global_user_managers()
        instead of a raw AccessMatrix scan."""
        admin = make_user()
        actor = make_user()
        make_access_grant(admin, "user", can_manage_users=True)

        assert can_deactivate_user(admin.id) is False

        user, error = set_user_active(admin.id, False, actor.id)

        assert user is None
        assert "last active user" in error
        assert admin.is_active is True

    def test_deactivating_a_non_last_admin_is_allowed(self, make_user, make_access_grant):
        admin_1 = make_user()
        admin_2 = make_user()
        actor = make_user()
        make_access_grant(admin_1, "user", can_manage_users=True)
        make_access_grant(admin_2, "user", can_manage_users=True)

        assert can_deactivate_user(admin_1.id) is True

        user, error = set_user_active(admin_1.id, False, actor.id)

        assert error is None
        assert user.is_active is False

    def test_deactivating_a_user_with_no_manage_users_grant_is_allowed(self, make_user):
        target = make_user()
        actor = make_user()

        assert can_deactivate_user(target.id) is True

        user, error = set_user_active(target.id, False, actor.id)

        assert error is None
        assert user.is_active is False


class TestPermissionMatrixLastAdminGuard:
    """The same "zero global admins" end state, reached instead via the
    permission-matrix endpoints (upsert_access_row, called directly by
    /assign and per-entity-type by save_permission_matrix for /assign-matrix)
    revoking the last admin's can_manage_users flag rather than deactivating
    them outright."""

    def test_revoking_can_manage_users_is_blocked_when_last_global_admin(self, make_user, make_access_grant):
        admin = make_user()
        actor = make_user()
        make_access_grant(admin, "user", can_manage_users=True)

        with pytest.raises(ValidationError, match="last active user"):
            upsert_access_row(
                user_id=admin.id,
                scope_type="global",
                scope_site_id=None,
                entity_type="user",
                permission_values={"can_manage_users": False},
                actor_id=actor.id,
            )

    def test_revoking_can_manage_users_is_allowed_when_another_admin_remains(self, make_user, make_access_grant):
        admin_1 = make_user()
        admin_2 = make_user()
        actor = make_user()
        make_access_grant(admin_1, "user", can_manage_users=True)
        make_access_grant(admin_2, "user", can_manage_users=True)

        row = upsert_access_row(
            user_id=admin_1.id,
            scope_type="global",
            scope_site_id=None,
            entity_type="user",
            permission_values={"can_manage_users": False},
            actor_id=actor.id,
        )

        assert row.can_manage_users is False

    def test_changing_other_flags_while_keeping_manage_users_true_is_unaffected(self, make_user, make_access_grant):
        """Even as the sole global admin, saving a row that keeps
        can_manage_users True (just toggling an unrelated flag) must never
        trip the guard."""
        admin = make_user()
        actor = make_user()
        make_access_grant(admin, "user", can_manage_users=True)

        row = upsert_access_row(
            user_id=admin.id,
            scope_type="global",
            scope_site_id=None,
            entity_type="user",
            permission_values={"can_manage_users": True, "can_view": True},
            actor_id=actor.id,
        )

        assert row.can_manage_users is True
        assert row.can_view is True

    def test_row_that_never_had_manage_users_is_unaffected_regardless_of_admin_count(self, make_user):
        """No global admin exists anywhere in the system here (count is 0),
        but this user never had can_manage_users in the first place -- saving
        a row that still leaves it False must not be treated as "revoking"
        anything."""
        target = make_user()
        actor = make_user()

        assert count_global_user_managers() == 0

        row = upsert_access_row(
            user_id=target.id,
            scope_type="global",
            scope_site_id=None,
            entity_type="user",
            permission_values={"can_view": True},
            actor_id=actor.id,
        )

        assert row.can_manage_users is False
        assert row.can_view is True


class TestSiteScopedGrantExcludedFromGlobalAdminCheck:
    def test_site_scoped_manage_users_grant_does_not_count_as_a_global_admin(
        self, make_user, make_access_grant, make_site,
    ):
        admin = make_user()
        site = make_site()
        make_access_grant(admin, "user", scope_type="site", scope_site_id=site.id, can_manage_users=True)

        assert count_global_user_managers() == 0
        assert can_deactivate_user(admin.id) is True

    def test_revoking_a_site_scoped_manage_users_grant_is_never_blocked(
        self, make_user, make_access_grant, make_site,
    ):
        """Confirms the guard is scoped to scope_type == "global" only: this
        user is the system's only "admin" of any kind (count_global_user_
        managers() == 0), but since the grant being edited is site-scoped,
        upsert_access_row must not raise."""
        admin = make_user()
        actor = make_user()
        site = make_site()
        make_access_grant(admin, "user", scope_type="site", scope_site_id=site.id, can_manage_users=True)

        row = upsert_access_row(
            user_id=admin.id,
            scope_type="site",
            scope_site_id=site.id,
            entity_type="user",
            permission_values={"can_manage_users": False},
            actor_id=actor.id,
        )

        assert row.can_manage_users is False
