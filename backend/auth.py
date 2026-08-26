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


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


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


def is_reviewer(user: User | None) -> bool:
    return user is not None and user.role == ROLE_REVIEWER


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
