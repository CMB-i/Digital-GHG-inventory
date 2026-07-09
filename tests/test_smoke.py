def test_app_and_fixtures_work(make_user, make_site, make_access_grant):
    user = make_user()
    site = make_site()
    grant = make_access_grant(user, "submission", scope_type="site", scope_site_id=site.id, can_view=True)
    assert user.id is not None
    assert site.id is not None
    assert grant.id is not None
