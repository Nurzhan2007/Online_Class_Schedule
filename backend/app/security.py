"""Password hashing (PBKDF2-SHA256) and JWT access tokens.

Pure functions only - no database, no FastAPI - so they are easy to test.

Stored password format (same idea as Django)::

    pbkdf2_sha256$600000$<salt, base64>$<hash, base64>

The iteration count is stored with every hash, so it can be raised later
without breaking existing accounts (see ``needs_rehash``).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import jwt

from app.config import Settings

# ---------------------------------------------------------------- passwords

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000  # OWASP recommendation for PBKDF2-HMAC-SHA256
SALT_BYTES = 16              # 128-bit random salt, unique for every hash
HASH_BYTES = 32              # 256-bit derived key


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _derive(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=HASH_BYTES
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    derived = _derive(password, salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(derived)}"


def _parse(stored_hash: str) -> tuple[int, bytes, bytes] | None:
    try:
        algorithm, iterations, salt_b64, hash_b64 = stored_hash.split("$")
        if algorithm != PBKDF2_ALGORITHM:
            return None
        rounds = int(iterations)
        if rounds <= 0:
            return None
        return rounds, base64.b64decode(salt_b64, validate=True), base64.b64decode(hash_b64, validate=True)
    except (ValueError, TypeError, AttributeError):
        return None


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a stored hash. Never raises; malformed -> False."""
    parsed = _parse(stored_hash)
    if parsed is None:
        return False
    iterations, salt, expected = parsed
    actual = _derive(password, salt, iterations)
    # Constant-time comparison: does not leak how many bytes matched.
    return hmac.compare_digest(actual, expected)


def needs_rehash(stored_hash: str) -> bool:
    """True if the hash uses fewer iterations than the current standard."""
    parsed = _parse(stored_hash)
    return parsed is None or parsed[0] < PBKDF2_ITERATIONS


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    """A hash nobody knows the password for.

    Used when a login names an email that does not exist: we still run one
    full PBKDF2 verification, so the response time does not reveal whether
    the account exists.
    """
    return hash_password(secrets.token_urlsafe(32))


# ---------------------------------------------------------------- JWT

TOKEN_TYPE = "access"


class TokenError(Exception):
    """Base class for token problems."""


class TokenExpiredError(TokenError):
    pass


class TokenInvalidError(TokenError):
    pass


@dataclass(frozen=True)
class IssuedToken:
    token: str
    jti: str
    expires_at: datetime  # timezone-aware UTC


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    user_id: int,
    role: str,
    settings: Settings,
    now: datetime | None = None,
) -> IssuedToken:
    issued_at = now or utcnow()
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    jti = uuid.uuid4().hex  # unique id, lets us revoke this exact token on logout

    payload = {
        "sub": str(user_id),
        "role": role,  # informational only - the server always re-reads the role from the DB
        "type": TOKEN_TYPE,
        "jti": jti,
        "iat": issued_at,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return IssuedToken(token=token, jti=jti, expires_at=expires_at)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            # A fixed list: tokens with "alg": "none" or any other algorithm are rejected.
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "jti", "iat", "exp", "type"]},
        )
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("token expired") from None
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError(str(exc)) from None

    if payload.get("type") != TOKEN_TYPE:
        raise TokenInvalidError("wrong token type")
    if not str(payload.get("sub", "")).isdigit():
        raise TokenInvalidError("bad subject")
    return payload
