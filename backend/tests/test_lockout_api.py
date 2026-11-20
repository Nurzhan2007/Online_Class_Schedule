"""Server-side account lockout through the HTTP API."""

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import LoginAttempt, utcnow_naive

EMAIL = "student@kbtu.kz"


def attempt(client, password, email=EMAIL):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture()
def student(make_user):
    return make_user("student", email=EMAIL)


def test_counter_counts_down_then_locks_on_third_failure(client, student):
    first, second, third = (attempt(client, "wrong") for _ in range(3))

    assert first.json()["detail"] == {"code": "auth.invalid", "params": {"n": 2}}
    assert second.json()["detail"] == {"code": "auth.invalid", "params": {"n": 1}}
    assert third.status_code == 429
    assert third.json()["detail"] == {"code": "auth.locked", "params": {"seconds": 300}}
    assert third.headers["retry-after"] == "300"


def test_locked_account_refuses_the_correct_password(client, student):
    for _ in range(3):
        attempt(client, "wrong")

    response = attempt(client, "password123")

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "auth.locked"
    assert 0 < response.json()["detail"]["params"]["seconds"] <= 300


def test_lock_is_stored_in_the_database(client, db, student):
    for _ in range(3):
        attempt(client, "wrong")

    record = db.get(LoginAttempt, EMAIL)
    assert record.failed_count == 3
    remaining = record.locked_until - utcnow_naive()
    assert timedelta(minutes=4) < remaining <= timedelta(minutes=5)


def test_success_resets_the_counter(client, db, student):
    attempt(client, "wrong")
    attempt(client, "wrong")
    assert attempt(client, "password123").status_code == 200
    assert db.get(LoginAttempt, EMAIL) is None

    # Not "consecutive" any more: two new failures do not lock.
    attempt(client, "wrong")
    response = attempt(client, "wrong")
    assert response.status_code == 401
    assert response.json()["detail"]["params"]["n"] == 1


def test_login_works_again_after_the_lock_expires(client, db, student):
    for _ in range(3):
        attempt(client, "wrong")
    record = db.get(LoginAttempt, EMAIL)
    record.locked_until = utcnow_naive() - timedelta(seconds=1)  # pretend 5 minutes passed
    db.commit()

    assert attempt(client, "password123").status_code == 200
    db.expire_all()
    assert db.scalar(select(LoginAttempt).where(LoginAttempt.email == EMAIL)) is None


def test_counter_restarts_after_the_lock_expires(client, db, student):
    for _ in range(3):
        attempt(client, "wrong")
    record = db.get(LoginAttempt, EMAIL)
    record.locked_until = utcnow_naive() - timedelta(seconds=1)
    db.commit()

    response = attempt(client, "wrong")

    assert response.status_code == 401
    assert response.json()["detail"]["params"]["n"] == 2


def test_lock_is_per_email(client, make_user, student):
    make_user("student", email="friend@kbtu.kz")
    for _ in range(3):
        attempt(client, "wrong")

    assert attempt(client, "password123", email="friend@kbtu.kz").status_code == 200


def test_email_case_does_not_bypass_the_lock(client, student):
    attempt(client, "wrong", email="student@kbtu.kz")
    attempt(client, "wrong", email="STUDENT@kbtu.kz")
    attempt(client, "wrong", email=" Student@Kbtu.Kz ")

    assert attempt(client, "password123").status_code == 429


def test_unknown_emails_lock_too_so_accounts_cannot_be_discovered(client):
    responses = [attempt(client, "wrong", email="ghost@kbtu.kz") for _ in range(3)]

    assert [r.status_code for r in responses] == [401, 401, 429]


def test_form_login_shares_the_same_counter(client, student):
    attempt(client, "wrong")
    attempt(client, "wrong")

    response = client.post("/api/auth/token", data={"username": EMAIL, "password": "wrong"})

    assert response.status_code == 429


def test_limits_come_from_configuration(client, student):
    custom = replace(get_settings(), max_login_attempts=5, lockout_minutes=10)
    client.app.dependency_overrides[get_settings] = lambda: custom

    statuses = [attempt(client, "wrong").status_code for _ in range(5)]

    assert statuses == [401, 401, 401, 401, 429]
    assert attempt(client, "wrong").json()["detail"]["params"]["seconds"] > 9 * 60
