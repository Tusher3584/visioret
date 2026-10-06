"""Shared fixtures for the Visioret test suite.

What these tests run against, and why
-------------------------------------
- A REAL PostgreSQL database, not SQLite or mocks. The schema relies on
  Postgres behaviour (JSON columns, the migration chain), and the privacy
  rules under test are SQL filters -- a stand-in database would test a
  different system. A throwaway database named `visioret_test` is dropped and
  recreated on the same server the dev stack uses (localhost:5433), then
  brought to the current schema by running the real Alembic migrations.
- The REAL trained model and the REAL CLIP gate, loaded once per session
  through the app's own startup (lifespan). Slower than mocking (~10-30 s
  once), but "the model classifies a known CNV scan as CNV" is exactly the
  kind of claim a mock cannot verify.
- A temporary media directory (VISIORET_MEDIA_DIR), so tests never write
  into backend/media/.

Requirements: the dev database container must be running
(`docker compose up -d db`). Override the server with TEST_DATABASE_ADMIN_URL.

Run:  python -m pytest           (from the repository root)
"""

import io
import os
import subprocess
import sys
import tempfile
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")

# --- Environment must be set BEFORE anything under backend/ is imported:
# auth.py reads JWT_SECRET_KEY at import, session.py reads DATABASE_URL,
# storage.py reads VISIORET_MEDIA_DIR, and main.py mounts /media at import.
ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL", "postgresql+psycopg2://visioret:visioret@localhost:5433/postgres"
)
TEST_DB_NAME = "visioret_test"
TEST_DATABASE_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"

_media_root = tempfile.mkdtemp(prefix="visioret-test-media-")
MEDIA_DIR = os.path.join(_media_root, "scans")
os.makedirs(MEDIA_DIR, exist_ok=True)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET_KEY"] = "test-only-signing-key-" + uuid.uuid4().hex
os.environ["VISIORET_MEDIA_DIR"] = MEDIA_DIR

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _recreate_test_database():
    from sqlalchemy import create_engine, text

    engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    engine.dispose()

    # The real migration chain, exactly as the backend container runs it.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", os.path.join("backend", "alembic.ini"), "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("alembic upgrade failed:\n" + result.stdout + result.stderr)


_recreate_test_database()


# ---------------------------------------------------------------------------
# App + client
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    from backend.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    """One TestClient for the whole run. Entering it runs the app's lifespan:
    loads ResNet-50 + CLIP, resolves the model version, seeds metrics."""
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The limiter is process-global; without this, one test's failed logins
    would leak into the next and produce order-dependent 429s."""
    from backend import rate_limit

    rate_limit._buckets.clear()
    yield
    rate_limit._buckets.clear()


@pytest.fixture
def db_session():
    from backend.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def unique_email(prefix="user"):
    # example.com is a real-looking domain; .test/.local are rejected by
    # registration validation (that rejection is itself tested).
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


PASSWORD = "Correct-Horse-9"


def register(client, role=None, name="Test User", email=None):
    """Register an account through the API; optionally set its role directly
    in the database, which is how roles are granted in reality
    (backend/grant_role.py) -- the API deliberately cannot grant admin."""
    email = email or unique_email(role or "viewer")
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    body = r.json()
    if role and role != "viewer":
        from backend.db.models import User
        from backend.db.session import SessionLocal

        s = SessionLocal()
        try:
            user = s.query(User).filter_by(id=body["user"]["id"]).one()
            user.role = role
            s.commit()
        finally:
            s.close()
    return {"id": body["user"]["id"], "email": email, "token": body["access_token"]}


def auth(account):
    return {"Authorization": f"Bearer {account['token']}"}


@pytest.fixture
def viewer(client):
    return register(client)


@pytest.fixture
def reviewer(client):
    return register(client, role="reviewer")


@pytest.fixture
def admin(client):
    return register(client, role="admin")


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

SAMPLE_FILES = {
    "CNV": "cnv_sample.jpg",
    "DME": "dme_sample.jpg",
    "DRUSEN": "drusen_sample.jpg",
    "NORMAL": "normal_sample.jpg",
}


def sample_bytes(cls):
    with open(os.path.join(SAMPLES, SAMPLE_FILES[cls]), "rb") as f:
        return f.read()


def colour_photo_bytes():
    """A synthetic colour image -- fails the grayscale stage of the OOD gate."""
    from PIL import Image

    img = Image.new("RGB", (320, 240))
    px = img.load()
    for x in range(320):
        for y in range(240):
            px[x, y] = (x % 256, (y * 2) % 256, 180)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def chart_bytes():
    """A real grayscale-ish chart (the committed confusion-matrix figure). This
    is the exact class of image that once slipped through the CLIP stage."""
    with open(os.path.join(ROOT, "model", "checkpoints", "confusion_matrix.png"), "rb") as f:
        return f.read()


def upload(client, data, filename="scan.jpg", content_type="image/jpeg", headers=None):
    return client.post(
        "/api/predict",
        files={"file": (filename, data, content_type)},
        headers=headers or {},
    )
