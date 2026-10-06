"""Integration tests: accounts and authentication over HTTP."""

from conftest import PASSWORD, auth, register, unique_email


def test_health_reports_model_and_gate(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checkpoint_loaded"] is True
    assert body["classes"] == ["CNV", "DME", "DRUSEN", "NORMAL"]
    assert body["ood_gate_active"] is True


def test_register_creates_a_viewer_and_returns_a_token(client):
    email = unique_email()
    r = client.post("/api/auth/register", json={"name": "Ada", "email": email, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "viewer"  # registration can never grant more
    assert body["user"]["email"] == email
    assert body["access_token"]


def test_register_rejects_duplicate_email(client):
    acc = register(client)
    r = client.post("/api/auth/register", json={"name": "Dup", "email": acc["email"], "password": PASSWORD})
    assert r.status_code == 400


def test_register_validates_input(client):
    cases = [
        {"name": "A", "email": "not-an-email", "password": PASSWORD},  # malformed email
        {"name": "A", "email": unique_email(), "password": "short"},  # < 8 chars
        {"name": "", "email": unique_email(), "password": PASSWORD},  # empty name
        {"name": "A", "email": "someone@site.test", "password": PASSWORD},  # reserved TLD
        {"name": "A" * 121, "email": unique_email(), "password": PASSWORD},  # over column width
    ]
    for body in cases:
        assert client.post("/api/auth/register", json=body).status_code == 422, body


def test_login_success(client):
    acc = register(client)
    r = client.post("/api/auth/login", json={"email": acc["email"], "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["user"]["id"] == acc["id"]


def test_login_failures_are_indistinguishable(client):
    acc = register(client)
    wrong_pw = client.post("/api/auth/login", json={"email": acc["email"], "password": "Wrong-password-1"})
    no_user = client.post("/api/auth/login", json={"email": unique_email(), "password": "Wrong-password-1"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["detail"] == no_user.json()["detail"]  # no account enumeration


def test_me_requires_a_valid_token(client):
    acc = register(client)
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    r = client.get("/api/auth/me", headers=auth(acc))
    assert r.status_code == 200 and r.json()["id"] == acc["id"]


def test_profile_update_name_and_password(client):
    acc = register(client)
    r = client.patch("/api/auth/me", json={"name": "Renamed"}, headers=auth(acc))
    assert r.status_code == 200 and r.json()["name"] == "Renamed"

    # Changing the password requires the current one.
    bad = client.patch("/api/auth/me", json={"new_password": "New-password-1", "current_password": "nope"}, headers=auth(acc))
    assert bad.status_code == 400
    ok = client.patch("/api/auth/me", json={"new_password": "New-password-1", "current_password": PASSWORD}, headers=auth(acc))
    assert ok.status_code == 200
    login = client.post("/api/auth/login", json={"email": acc["email"], "password": "New-password-1"})
    assert login.status_code == 200


def test_profile_update_cannot_change_role(client):
    acc = register(client)
    r = client.patch("/api/auth/me", json={"name": "X", "role": "admin"}, headers=auth(acc))
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"  # unknown field ignored; role is not self-assignable


def test_login_rate_limit_then_success_clears_it(client):
    acc = register(client)
    for _ in range(10):
        assert client.post("/api/auth/login", json={"email": acc["email"], "password": "Wrong-password-1"}).status_code == 401
    blocked = client.post("/api/auth/login", json={"email": acc["email"], "password": PASSWORD})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_successful_login_resets_the_failure_count(client):
    acc = register(client)
    for _ in range(9):
        client.post("/api/auth/login", json={"email": acc["email"], "password": "Wrong-password-1"})
    assert client.post("/api/auth/login", json={"email": acc["email"], "password": PASSWORD}).status_code == 200
    for _ in range(9):  # a fresh allowance after success
        assert client.post("/api/auth/login", json={"email": acc["email"], "password": "Wrong-password-1"}).status_code == 401


def test_registration_rate_limit(client):
    for i in range(5):
        assert client.post("/api/auth/register", json={"name": "R", "email": unique_email(), "password": PASSWORD}).status_code == 200
    assert client.post("/api/auth/register", json={"name": "R", "email": unique_email(), "password": PASSWORD}).status_code == 429
