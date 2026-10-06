"""Unit tests for backend/auth.py -- pure functions, no HTTP, no database."""

from datetime import datetime, timedelta, timezone

import jwt

from backend import auth
from backend.db.models import User


def test_password_hash_roundtrip():
    h = auth.hash_password("s3cret-password")
    assert h != "s3cret-password"  # never stored in plain text
    assert auth.verify_password("s3cret-password", h)
    assert not auth.verify_password("wrong-password", h)


def test_same_password_hashes_differently():
    # bcrypt salts every hash, so equal passwords are not visible as equal rows.
    assert auth.hash_password("same-password") != auth.hash_password("same-password")


def test_verify_password_never_raises_on_bad_input():
    # Regression: bcrypt's ValueError once turned "wrong password" into a 500.
    assert auth.verify_password("x" * 100, auth.hash_password("short-pass")) is False  # > 72 bytes
    assert auth.verify_password("anything", "") is False
    assert auth.verify_password("anything", "not-a-bcrypt-hash") is False


def test_password_byte_limit_counts_bytes_not_characters():
    # bcrypt's limit is 72 BYTES; a multibyte character counts several times.
    assert not auth.password_too_long("a" * 72)
    assert auth.password_too_long("a" * 73)
    assert auth.password_too_long("é" * 37)  # 74 bytes, 37 characters


def test_token_roundtrip():
    token = auth.create_access_token(42)
    assert auth._decode_user_id(token) == 42


def test_tampered_token_rejected():
    token = auth.create_access_token(42)
    header, payload, signature = token.split(".")
    flipped = signature[:-2] + ("A" if signature[-2] != "A" else "B") + signature[-1]
    assert auth._decode_user_id(f"{header}.{payload}.{flipped}") is None


def test_token_signed_with_another_key_rejected():
    forged = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(days=1)}, "attacker-key", "HS256")
    assert auth._decode_user_id(forged) is None


def test_alg_none_token_rejected():
    unsigned = jwt.encode({"sub": "1"}, key=None, algorithm="none")
    assert auth._decode_user_id(unsigned) is None


def test_expired_token_rejected():
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        auth.JWT_SECRET_KEY,
        auth.JWT_ALGORITHM,
    )
    assert auth._decode_user_id(expired) is None


def test_role_predicates():
    viewer, reviewer, admin = (User(role=r) for r in ("viewer", "reviewer", "admin"))
    assert not auth.is_reviewer(None)
    assert not auth.is_reviewer(viewer)
    assert auth.is_reviewer(reviewer)
    assert auth.is_reviewer(admin)  # admin is a superset of reviewer
    assert not auth.is_admin(reviewer)
    assert auth.is_admin(admin)
    assert "admin" not in auth.ASSIGNABLE_ROLES  # admin can never be granted via the API
