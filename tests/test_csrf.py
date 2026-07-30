import re


def _csrf_token(response):
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match.group(1)


def test_anonymous_password_reset_request_rejects_missing_csrf(app):
    app.config["CSRF_TESTING"] = True
    try:
        with app.test_client() as client:
            response = client.post(
                "/forgot-password/send-otp",
                data={"email": "csrf-anonymous@example.com"},
                follow_redirects=False,
            )
            assert response.status_code == 403
    finally:
        app.config["CSRF_TESTING"] = False


def test_anonymous_password_reset_request_accepts_valid_csrf(app):
    app.config["CSRF_TESTING"] = True
    try:
        with app.test_client() as client:
            token = _csrf_token(client.get("/forgot-password"))
            response = client.post(
                "/forgot-password/send-otp",
                data={"email": "csrf-anonymous@example.com", "csrf_token": token},
                follow_redirects=False,
            )
            assert response.status_code == 302
    finally:
        app.config["CSRF_TESTING"] = False


def test_authenticated_mutation_rejects_missing_csrf(app, make_user, db_session):
    user = make_user(email="csrf-auth@example.com")
    db_session.commit()

    app.config["CSRF_TESTING"] = True
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = user.id
                sess["user_session_version"] = user.session_version

            response = client.post("/module/NOTIFY/mark-all-read", follow_redirects=False)
            assert response.status_code == 403
    finally:
        app.config["CSRF_TESTING"] = False


def test_authenticated_mutation_accepts_valid_csrf(app, make_user, db_session):
    user = make_user(email="csrf-auth-valid@example.com")
    db_session.commit()

    app.config["CSRF_TESTING"] = True
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = user.id
                sess["user_session_version"] = user.session_version

            page = client.get("/module/NOTIFY/")
            token = re.search(r'name="csrf-token" content="([^"]+)"', page.get_data(as_text=True)).group(1)
            response = client.post(
                "/module/NOTIFY/mark-all-read",
                headers={"X-CSRFToken": token},
                follow_redirects=False,
            )
            assert response.status_code == 200
    finally:
        app.config["CSRF_TESTING"] = False
