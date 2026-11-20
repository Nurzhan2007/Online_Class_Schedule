"""Registration, login, /me, logout and token handling through the HTTP API."""

from datetime import timedelta

import jwt
from sqlalchemy import select

from app.config import get_settings
from app.models import RevokedToken, User, utcnow_naive
from app.security import create_access_token, utcnow

REGISTRATION = {"name": "Aruzhan Sadykova", "studentId": "24B031234",
                "email": "Aruzhan@KBTU.kz", "password": "secret123"}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def error_code(response):
    return response.json()["detail"]["code"]


# ------------------------------------------------------------- registration

def test_register_creates_a_student(client):
    response = client.post("/api/auth/register", json=REGISTRATION)

    assert response.status_code == 201
    body = response.json()
    assert body == {"id": body["id"], "name": "Aruzhan Sadykova", "studentId": "24B031234",
                    "email": "aruzhan@kbtu.kz", "role": "student"}


def test_password_is_stored_only_as_pbkdf2_hash(client, db):
    client.post("/api/auth/register", json=REGISTRATION)

    user = db.scalar(select(User).where(User.email == "aruzhan@kbtu.kz"))
    assert user.password_hash.startswith("pbkdf2_sha256$600000$")
    assert "secret123" not in user.password_hash


def test_response_never_contains_password_data(client):
    response = client.post("/api/auth/register", json=REGISTRATION)

    assert "password" not in response.text.lower()
    assert "pbkdf2" not in response.text


def test_duplicate_email_is_rejected_case_insensitively(client):
    client.post("/api/auth/register", json=REGISTRATION)
    response = client.post("/api/auth/register",
                           json={**REGISTRATION, "studentId": "24B000001", "email": "ARUZHAN@kbtu.kz"})

    assert response.status_code == 409
    assert error_code(response) == "auth.emailTaken"


def test_duplicate_student_id_is_rejected(client):
    client.post("/api/auth/register", json=REGISTRATION)
    response = client.post("/api/auth/register",
                           json={**REGISTRATION, "email": "other@kbtu.kz", "studentId": "24b031234"})

    assert response.status_code == 409
    assert error_code(response) == "auth.idTaken"


def test_registration_cannot_create_an_admin(client, db):
    response = client.post("/api/auth/register", json={**REGISTRATION, "role": "admin"})

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "err.validation", "params": {"fields": ["role"]}}}
    assert db.scalar(select(User.id)) is None


def test_validation_errors_name_fields_but_never_echo_values(client):
    response = client.post("/api/auth/register",
                           json={**REGISTRATION, "password": "12345", "email": "bad"})

    assert response.status_code == 422
    assert response.json()["detail"]["params"]["fields"] == ["email", "password"]
    assert "12345" not in response.text


# ------------------------------------------------------------- login

def test_login_returns_a_30_minute_bearer_token(client, make_user):
    make_user("student", email="student@kbtu.kz")

    response = client.post("/api/auth/login",
                           json={"email": "student@kbtu.kz", "password": "password123"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60
    assert body["user"]["email"] == "student@kbtu.kz"
    assert body["user"]["role"] == "student"
    assert "studentId" in body["user"]


def test_login_email_is_case_and_space_insensitive(client, make_user, login):
    make_user("student", email="student@kbtu.kz")

    assert login("  Student@KBTU.kz ")


def test_wrong_password_and_unknown_email_look_the_same(client, make_user):
    make_user("student", email="student@kbtu.kz")

    wrong_password = client.post("/api/auth/login",
                                 json={"email": "student@kbtu.kz", "password": "nope"})
    unknown_email = client.post("/api/auth/login",
                                json={"email": "ghost@kbtu.kz", "password": "nope"})

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {
        "detail": {"code": "auth.invalid", "params": {"n": 2}}
    }


def test_swagger_form_login_works(client, make_user):
    make_user("admin", email="admin@kbtu.kz")

    response = client.post("/api/auth/token",
                           data={"username": "admin@kbtu.kz", "password": "password123"})

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


def test_old_weak_hash_is_upgraded_on_login(client, db, make_user, login):
    import base64
    import hashlib

    user = make_user("student", email="student@kbtu.kz")
    salt = b"0123456789abcdef"
    weak = hashlib.pbkdf2_hmac("sha256", b"password123", salt, 1000, dklen=32)
    user.password_hash = "pbkdf2_sha256$1000$%s$%s" % (
        base64.b64encode(salt).decode(), base64.b64encode(weak).decode())
    db.commit()

    login("student@kbtu.kz")

    db.expire_all()
    assert db.get(User, user.id).password_hash.startswith("pbkdf2_sha256$600000$")


# ------------------------------------------------------------- /me and tokens

def test_me_returns_the_current_user(client, make_user, login):
    user = make_user("teacher", email="teacher@kbtu.kz")

    response = client.get("/api/auth/me", headers=bearer(login("teacher@kbtu.kz")))

    assert response.status_code == 200
    assert response.json()["id"] == user.id
    assert response.json()["role"] == "teacher"


def test_me_without_token_is_401(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert error_code(response) == "auth.loginFirst"
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_with_garbage_token_is_401(client):
    response = client.get("/api/auth/me", headers=bearer("not-a-jwt"))

    assert response.status_code == 401
    assert error_code(response) == "auth.loginFirst"


def test_expired_token_is_401_session_expired(client, make_user):
    user = make_user("student")
    expired = create_access_token(user.id, "student", get_settings(),
                                  now=utcnow() - timedelta(minutes=31)).token

    response = client.get("/api/auth/me", headers=bearer(expired))

    assert response.status_code == 401
    assert error_code(response) == "auth.sessionExpired"


def test_token_forged_with_another_key_is_401(client, make_user):
    user = make_user("student")
    forged = jwt.encode(
        {"sub": str(user.id), "role": "admin", "type": "access", "jti": "x",
         "iat": utcnow(), "exp": utcnow() + timedelta(minutes=5)},
        "attacker-" + "k" * 40, algorithm="HS256")

    assert client.get("/api/auth/me", headers=bearer(forged)).status_code == 401


def test_token_of_deleted_user_is_401(client, db, make_user, login):
    user = make_user("student", email="gone@kbtu.kz")
    token = login("gone@kbtu.kz")
    db.delete(user)
    db.commit()

    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_role_comes_from_database_not_from_token(client, db, make_user, login):
    from app.roles import Role

    user = make_user("admin", email="boss@kbtu.kz")
    token = login("boss@kbtu.kz")
    user.role = Role.STUDENT       # demoted after the token was issued
    db.commit()

    assert client.get("/api/auth/me", headers=bearer(token)).json()["role"] == "student"
    assert client.get("/api/admin/users", headers=bearer(token)).status_code == 403


# ------------------------------------------------------------- logout

def test_logout_revokes_the_token(client, make_user, login):
    make_user("student", email="student@kbtu.kz")
    token = login("student@kbtu.kz")

    assert client.post("/api/auth/logout", headers=bearer(token)).status_code == 204

    after = client.get("/api/auth/me", headers=bearer(token))
    assert after.status_code == 401
    assert error_code(after) == "auth.loginFirst"
    assert client.post("/api/auth/logout", headers=bearer(token)).status_code == 401


def test_logout_only_ends_that_session(client, make_user, login):
    make_user("student", email="student@kbtu.kz")
    laptop, phone = login("student@kbtu.kz"), login("student@kbtu.kz")

    client.post("/api/auth/logout", headers=bearer(laptop))

    assert client.get("/api/auth/me", headers=bearer(phone)).status_code == 200


def test_logout_without_token_is_401(client):
    assert client.post("/api/auth/logout").status_code == 401


def test_logout_cleans_up_expired_revocations(client, db, make_user, login):
    user = make_user("student", email="student@kbtu.kz")
    db.add(RevokedToken(jti="old", user_id=user.id, expires_at=utcnow_naive() - timedelta(minutes=1)))
    db.commit()

    client.post("/api/auth/logout", headers=bearer(login("student@kbtu.kz")))

    db.expire_all()
    remaining = list(db.scalars(select(RevokedToken.jti)))
    assert "old" not in remaining
    assert len(remaining) == 1
