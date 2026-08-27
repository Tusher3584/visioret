"""Minimal real authentication: bcrypt-hashed passwords + a stateless JWT
session. Deliberately not a full identity provider (see TODO.md Checkpoint
9) -- no email verification, no password reset, no OAuth. Just the core
mechanism, done properly rather than faked.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.db.session import get_db

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set. Add it to .env (local/host) and docker-compose.yml (container) -- "
        "see backend/auth.py. Never fall back to a hardcoded default here: that would silently make "
        "every deployment share the same signing key."
    )
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_LIFETIME = timedelta(days=7)  # a demo/research tool, not a bank -- long-lived is fine

# tokenUrl is where a client would normally POST to get a token; only used
# by FastAPI's auto-generated docs UI, not by our own frontend.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# bcrypt hashes at most 72 BYTES of input. bcrypt 5.x raises ValueError past
# that instead of silently truncating, so an over-long password used to reach
# hashpw() and surface as a 500. Note bytes, not characters: a passphrase with
# non-ASCII characters hits this sooner than its length suggests, which is why
# the check is done on the encoded form.
PASSWORD_MAX_BYTES = 72


def password_too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > PASSWORD_MAX_BYTES


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """False rather than raising, for any input that cannot possibly match.

    Callers use this to decide 401 vs 200, so it must not raise: an over-long
    password, or a row whose hash is empty or malformed, is simply a failed
    login. Letting bcrypt's ValueError escape here turned "wrong password"
    into "500 Internal Server Error".
    """
    if not password_hash or password_too_long(password):
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# A real bcrypt hash of a value nobody can supply, used to spend the same CPU
# time on a login for an unknown email as for a known one. Without it,
# verify_password is skipped entirely when the email doesn't exist, and the
# response comes back measurably faster -- which turns login into an oracle
# for "does this address have an account here", the exact thing the
# deliberately-vague "Incorrect email or password" message avoids leaking.
_TIMING_EQUALIZER_HASH = bcrypt.hashpw(b"visioret-timing-equalizer", bcrypt.gensalt()).decode("utf-8")


def spend_password_verification_time() -> None:
    """Burn one bcrypt verification, so a failed lookup costs what a real one does."""
    try:
        bcrypt.checkpw(b"visioret-timing-equalizer-miss", _TIMING_EQUALIZER_HASH.encode("utf-8"))
    except ValueError:
        pass


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + ACCESS_TOKEN_LIFETIME,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode_user_id(token: str) -> int | None:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User | None:
    """None if there's no token or it's invalid/expired -- callers that
    allow anonymous use (e.g. predicting without an account) depend on
    this instead of get_current_user."""
    if not token:
        return None
    user_id = _decode_user_id(token)
    if user_id is None:
        return None
    return db.query(User).filter_by(id=user_id).first()


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    """Raises 401 if not authenticated -- for endpoints that require login."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user


# Two roles, and the split is grounded in what the data means rather than in an
# invented org chart:
#
#   viewer   -- can submit scans and read their own results.
#   reviewer -- can additionally see every scan and record corrections.
#
# A correction writes `feedback.corrected_class`: a human label asserting the
# model got it wrong. Those labels are exactly what would feed back into
# retraining, so they need provenance and a qualified author. A reviewer also
# needs cross-user visibility precisely because reviewing other people's
# predictions is the job.
#
# Roles are NOT self-assignable: registration always creates a viewer, and
# promotion is an out-of-band administrative action (backend/grant_role.py),
# the same way real systems bootstrap privileged accounts.
ROLE_VIEWER = "viewer"
ROLE_REVIEWER = "reviewer"
# Admin adds user management on top of everything a reviewer can do. It is
# never obtainable through the API -- not by registering, not by another admin
# promoting you. An admin account is created by hand against the database
# (backend/grant_role.py), so the privilege chain always terminates in someone
# with direct database access rather than in the app itself.
ROLE_ADMIN = "admin"

ROLES = (ROLE_VIEWER, ROLE_REVIEWER, ROLE_ADMIN)
# What an admin is allowed to assign through the API. Deliberately excludes
# admin, so the role cannot spread without database access.
ASSIGNABLE_ROLES = (ROLE_VIEWER, ROLE_REVIEWER)


def is_reviewer(user: User | None) -> bool:
    """Admin is a superset of reviewer -- an administrator who could not read
    the metrics they administer would be a strange kind of administrator."""
    return user is not None and user.role in (ROLE_REVIEWER, ROLE_ADMIN)


def is_admin(user: User | None) -> bool:
    return user is not None and user.role == ROLE_ADMIN


def require_admin(user: User = Depends(get_current_user)) -> User:
    """403 unless the caller is an administrator."""
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="This action requires the admin role.")
    return user


def require_reviewer(user: User = Depends(get_current_user)) -> User:
    """403 unless the caller holds the reviewer role. Enforced server-side --
    the frontend also hides these actions, but that is presentation only and
    must never be the thing that actually protects them."""
    if not is_reviewer(user):
        raise HTTPException(
            status_code=403,
            detail="This action requires the reviewer role.",
        )
    return user
