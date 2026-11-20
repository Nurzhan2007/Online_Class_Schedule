"""Password hashing and JWT (pure Python, no FastAPI or database needed)."""

import base64
import hashlib
from datetime import timedelta

import jwt
import pytest

from app.config import Settings
from app.security import (
    PBKDF2_ITERATIONS,
    SALT_BYTES,
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    decode_access_token,
    dummy_password_hash,
    hash_password,
    needs_rehash,
    utcnow,
    verify_password,
)


@pytest.fixture()
def settings(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s" * 64)
    return Settings.from_env()


# ------------------------------------------------------------- passwords

def test_hash_uses_pbkdf2_sha256_with_600000_iterations():
    stored = hash_password("student123")
    algorithm, iterations, salt_b64, hash_b64 = stored.split("$")

    assert PBKDF2_ITERATIONS == 600_000
    assert algorithm == "pbkdf2_sha256"
    assert iterations == "600000"
    assert len(base64.b64decode(salt_b64)) == SALT_BYTES == 16
    assert len(base64.b64decode(hash_b64)) == 32


def test_hash_matches_the_standard_pbkdf2_algorithm():
    stored = hash_password("student123")
    _, iterations, salt_b64, hash_b64 = stored.split("$")
    expected = hashlib.pbkdf2_hmac(
        "sha256", b"student123", base64.b64decode(salt_b64), int(iterations), dklen=32
    )
    assert base64.b64decode(hash_b64) == expected


def test_plain_password_is_not_in_the_hash():
    assert "student123" not in hash_password("student123")


def test_every_hash_gets_a_unique_salt():
    first, second = hash_password("same-password"), hash_password("same-password")

    assert first != second
    assert first.split("$")[2] != second.split("$")[2]
    assert verify_password("same-password", first)
    assert verify_password("same-password", second)


def test_verify_accepts_correct_and_rejects_wrong_password():
    stored = hash_password("student123")

    assert verify_password("student123", stored) is True
    assert verify_password("student124", stored) is False
    assert verify_password("Student123", stored) is False
    assert verify_password("", stored) is False


def test_unicode_passwords_work():
    stored = hash_password("Құпия-сөз-пароль")

    assert verify_password("Құпия-сөз-пароль", stored)
    assert not verify_password("Кұпия-сөз-пароль", stored)


@pytest.mark.parametrize("broken", [
    "", "plaintext", "student123", "md5$1$abc$def",
    "pbkdf2_sha256$notanumber$AAAA$AAAA", "pbkdf2_sha256$0$AAAA$AAAA",
    "pbkdf2_sha256$600000$!!!$AAAA", "pbkdf2_sha256$600000$AAAA",
])
def test_malformed_hashes_never_verify_and_never_crash(broken):
    assert verify_password("student123", broken) is False
    assert needs_rehash(broken) is True


def test_old_weaker_hashes_are_flagged_for_rehash():
    salt = b"0123456789abcdef"
    weak = "pbkdf2_sha256$1000$%s$%s" % (
        base64.b64encode(salt).decode(),
        base64.b64encode(hashlib.pbkdf2_hmac("sha256", b"pw", salt, 1000, dklen=32)).decode(),
    )
    assert verify_password("pw", weak)          # still works...
    assert needs_rehash(weak)                   # ...but will be upgraded on next login
    assert not needs_rehash(hash_password("pw"))


def test_dummy_hash_is_valid_and_stable():
    assert dummy_password_hash() == dummy_password_hash()
    assert dummy_password_hash().startswith("pbkdf2_sha256$600000$")
    assert not verify_password("", dummy_password_hash())


# ------------------------------------------------------------- JWT

def test_token_round_trip(settings):
    issued = create_access_token(7, "student", settings)
    payload = decode_access_token(issued.token, settings)

    assert payload["sub"] == "7"
    assert payload["role"] == "student"
    assert payload["type"] == "access"
    assert payload["jti"] == issued.jti


def test_token_expires_after_30_minutes(settings):
    now = utcnow().replace(microsecond=0)
    issued = create_access_token(1, "student", settings, now=now)
    payload = decode_access_token(issued.token, settings)

    assert issued.expires_at - now == timedelta(minutes=30)
    assert payload["exp"] - payload["iat"] == 30 * 60


def test_expired_token_is_rejected(settings):
    issued = create_access_token(1, "student", settings, now=utcnow() - timedelta(minutes=31))

    with pytest.raises(TokenExpiredError):
        decode_access_token(issued.token, settings)


def test_each_token_has_a_unique_id(settings):
    ids = {create_access_token(1, "student", settings).jti for _ in range(20)}
    assert len(ids) == 20


def test_token_signed_with_another_key_is_rejected(settings):
    forged = jwt.encode(
        {"sub": "1", "role": "admin", "type": "access", "jti": "x",
         "iat": utcnow(), "exp": utcnow() + timedelta(minutes=5)},
        "attacker-key-" + "a" * 40, algorithm="HS256",
    )
    with pytest.raises(TokenInvalidError):
        decode_access_token(forged, settings)


def test_tampered_payload_is_rejected(settings):
    token = create_access_token(1, "student", settings).token
    header, payload, signature = token.split(".")
    fake_payload = base64.urlsafe_b64encode(
        b'{"sub":"1","role":"admin","type":"access","jti":"x","iat":1,"exp":9999999999}'
    ).rstrip(b"=").decode()

    with pytest.raises(TokenInvalidError):
        decode_access_token(f"{header}.{fake_payload}.{signature}", settings)


def test_alg_none_token_is_rejected(settings):
    unsigned = jwt.encode(
        {"sub": "1", "role": "admin", "type": "access", "jti": "x",
         "iat": utcnow(), "exp": utcnow() + timedelta(minutes=5)},
        "", algorithm="none",
    )
    with pytest.raises(TokenInvalidError):
        decode_access_token(unsigned, settings)


@pytest.mark.parametrize("missing", ["sub", "jti", "iat", "exp", "type"])
def test_tokens_missing_required_claims_are_rejected(settings, missing):
    claims = {"sub": "1", "role": "student", "type": "access", "jti": "x",
              "iat": utcnow(), "exp": utcnow() + timedelta(minutes=5)}
    del claims[missing]
    token = jwt.encode(claims, settings.secret_key, algorithm="HS256")

    with pytest.raises(TokenInvalidError):
        decode_access_token(token, settings)


@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c", "Bearer x"])
def test_garbage_tokens_are_rejected(settings, garbage):
    with pytest.raises(TokenInvalidError):
        decode_access_token(garbage, settings)


def test_wrong_token_type_is_rejected(settings):
    token = jwt.encode(
        {"sub": "1", "role": "student", "type": "refresh", "jti": "x",
         "iat": utcnow(), "exp": utcnow() + timedelta(minutes=5)},
        settings.secret_key, algorithm="HS256",
    )
    with pytest.raises(TokenInvalidError):
        decode_access_token(token, settings)
