"""Integration tests: who can see and do what. Every cell of the permission
matrix in README.md is asserted here, plus the anonymous privacy model."""

import uuid

import pytest

from conftest import auth, register, sample_bytes, upload


def anon(session_id):
    return {"X-Anon-Session": session_id}


@pytest.fixture
def anon_scan(client):
    session = uuid.uuid4().hex
    scan_id = upload(client, sample_bytes("DME"), headers=anon(session)).json()["scan_id"]
    return session, scan_id


# --- anonymous privacy -----------------------------------------------------

def test_anonymous_session_sees_only_its_own_scans(client, anon_scan):
    session, scan_id = anon_scan
    mine = client.get("/api/scans", headers=anon(session)).json()
    assert [s["scan_id"] for s in mine] == [scan_id]
    assert client.get(f"/api/scans/{scan_id}", headers=anon(session)).status_code == 200


def test_other_anonymous_session_cannot_see_or_open_it(client, anon_scan):
    _, scan_id = anon_scan
    other = uuid.uuid4().hex
    assert client.get("/api/scans", headers=anon(other)).json() == []
    assert client.get(f"/api/scans/{scan_id}", headers=anon(other)).status_code == 404


def test_missing_session_header_matches_nothing(client, anon_scan):
    # Regression: omitting the header must not fall back to "all anonymous scans".
    _, scan_id = anon_scan
    assert client.get("/api/scans").json() == []
    assert client.get(f"/api/scans/{scan_id}").status_code == 404


def test_signed_in_viewer_cannot_borrow_an_anonymous_session(client, viewer, anon_scan):
    session, scan_id = anon_scan
    headers = {**auth(viewer), **anon(session)}
    assert scan_id not in [s["scan_id"] for s in client.get("/api/scans", headers=headers).json()]
    assert client.get(f"/api/scans/{scan_id}", headers=headers).status_code == 404


# --- signed-in visibility --------------------------------------------------

def test_viewer_sees_own_scans_only(client):
    a, b = register(client), register(client)
    a_scan = upload(client, sample_bytes("CNV"), headers=auth(a)).json()["scan_id"]
    b_scan = upload(client, sample_bytes("NORMAL"), headers=auth(b)).json()["scan_id"]
    a_list = [s["scan_id"] for s in client.get("/api/scans", headers=auth(a)).json()]
    assert a_scan in a_list and b_scan not in a_list
    assert client.get(f"/api/scans/{b_scan}", headers=auth(a)).status_code == 404


def test_reviewer_sees_everyone_including_anonymous(client, reviewer, anon_scan):
    _, scan_id = anon_scan
    viewer = register(client)
    v_scan = upload(client, sample_bytes("CNV"), headers=auth(viewer)).json()["scan_id"]
    ids = [s["scan_id"] for s in client.get("/api/scans?limit=200", headers=auth(reviewer)).json()]
    assert scan_id in ids and v_scan in ids
    detail = client.get(f"/api/scans/{v_scan}", headers=auth(reviewer)).json()
    assert detail["can_review"] is True


def test_scan_list_limit_is_bounded(client, reviewer):
    for bad in (0, -1, 201):
        assert client.get(f"/api/scans?limit={bad}", headers=auth(reviewer)).status_code == 422


# --- permission matrix -----------------------------------------------------

def test_metrics_permission_matrix(client, viewer, reviewer, admin):
    assert client.get("/api/metrics").status_code == 401
    assert client.get("/api/metrics", headers=auth(viewer)).status_code == 403
    for acc in (reviewer, admin):
        r = client.get("/api/metrics", headers=auth(acc))
        assert r.status_code == 200
        splits = {m["dataset_split"] for m in r.json()}
        assert splits == {"kermany_test", "external_test"}  # seeded from the committed export


def test_published_metrics_match_the_report(client, reviewer):
    rows = {m["dataset_split"]: m for m in client.get("/api/metrics", headers=auth(reviewer)).json()}
    assert rows["kermany_test"]["accuracy"] == pytest.approx(0.9517, abs=5e-4)
    assert rows["kermany_test"]["f1_macro"] == pytest.approx(0.9233, abs=5e-4)
    assert rows["external_test"]["accuracy"] == pytest.approx(0.8813, abs=5e-4)


def test_admin_users_permission_matrix(client, viewer, reviewer, admin):
    assert client.get("/api/admin/users").status_code == 401
    assert client.get("/api/admin/users", headers=auth(viewer)).status_code == 403
    assert client.get("/api/admin/users", headers=auth(reviewer)).status_code == 403
    assert client.get("/api/admin/users", headers=auth(admin)).status_code == 200


def test_feedback_permission_matrix(client, viewer, reviewer, admin):
    scan_id = upload(client, sample_bytes("CNV"), headers=auth(viewer)).json()["scan_id"]
    body = {"is_correct": True}
    assert client.put(f"/api/scans/{scan_id}/feedback", json=body).status_code == 401
    # The viewer OWNS this scan and still cannot label it: ownership governs
    # visibility, role governs authority.
    assert client.put(f"/api/scans/{scan_id}/feedback", json=body, headers=auth(viewer)).status_code == 403
    assert client.put(f"/api/scans/{scan_id}/feedback", json=body, headers=auth(reviewer)).status_code == 200
    assert client.put(f"/api/scans/{scan_id}/feedback", json=body, headers=auth(admin)).status_code == 200


# --- review workflow -------------------------------------------------------

def test_feedback_validation_and_upsert(client, reviewer):
    scan_id = upload(client, sample_bytes("DRUSEN"), headers=auth(reviewer)).json()["scan_id"]
    url = f"/api/scans/{scan_id}/feedback"

    assert client.put(url, json={"is_correct": False}, headers=auth(reviewer)).status_code == 400  # class required
    assert client.put(url, json={"is_correct": False, "corrected_class": "GLAUCOMA"}, headers=auth(reviewer)).status_code == 400

    first = client.put(url, json={"is_correct": False, "corrected_class": "CNV", "comment": "subtle"}, headers=auth(reviewer))
    assert first.status_code == 200
    assert first.json()["corrected_class"] == "CNV" and first.json()["reviewer_name"]

    second = client.put(url, json={"is_correct": True}, headers=auth(reviewer))
    assert second.status_code == 200
    fb = client.get(f"/api/scans/{scan_id}", headers=auth(reviewer)).json()["feedback"]
    assert fb["is_correct"] is True and fb["corrected_class"] is None  # replaced, not duplicated


def test_feedback_on_missing_scan_is_404(client, reviewer):
    assert client.put("/api/scans/99999999/feedback", json={"is_correct": True}, headers=auth(reviewer)).status_code == 404


# --- administration --------------------------------------------------------

def test_admin_promotion_takes_effect_immediately(client, admin):
    target = register(client)
    assert client.get("/api/metrics", headers=auth(target)).status_code == 403
    r = client.patch(f"/api/admin/users/{target['id']}/role", json={"role": "reviewer"}, headers=auth(admin))
    assert r.status_code == 200 and r.json()["role"] == "reviewer"
    # Same token as before: roles are read from the database per request.
    assert client.get("/api/metrics", headers=auth(target)).status_code == 200
    client.patch(f"/api/admin/users/{target['id']}/role", json={"role": "viewer"}, headers=auth(admin))
    assert client.get("/api/metrics", headers=auth(target)).status_code == 403


def test_admin_cannot_grant_admin_touch_admins_or_self(client, admin):
    target = register(client)
    other_admin = register(client, role="admin")
    url = "/api/admin/users/{}/role"
    assert client.patch(url.format(target["id"]), json={"role": "admin"}, headers=auth(admin)).status_code == 400
    assert client.patch(url.format(other_admin["id"]), json={"role": "viewer"}, headers=auth(admin)).status_code == 400
    assert client.patch(url.format(admin["id"]), json={"role": "viewer"}, headers=auth(admin)).status_code == 400
    assert client.patch(url.format(99999999), json={"role": "reviewer"}, headers=auth(admin)).status_code == 404


def test_admin_user_list_flags(client, admin):
    rows = {u["id"]: u for u in client.get("/api/admin/users", headers=auth(admin)).json()}
    me = rows[admin["id"]]
    assert me["is_self"] is True and me["is_editable"] is False
