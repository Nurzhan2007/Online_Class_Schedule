"""Demo accounts from the original frontend (js/auth.js)."""

import pytest
from sqlalchemy import select

from app.models import User
from app.seed import DEMO_USERS, seed_demo_users


def test_seed_creates_the_three_demo_accounts_with_hashed_passwords(db):
    created = seed_demo_users(db)

    assert created == ["student@kbtu.kz", "teacher@kbtu.kz", "admin@kbtu.kz"]
    users = list(db.scalars(select(User).order_by(User.id)))
    assert [u.role.value for u in users] == ["student", "teacher", "admin"]
    for user, demo in zip(users, DEMO_USERS):
        assert user.password_hash.startswith("pbkdf2_sha256$600000$")
        assert demo["password"] not in user.password_hash


def test_seed_is_safe_to_run_twice(db):
    seed_demo_users(db)

    assert seed_demo_users(db) == []
    assert len(list(db.scalars(select(User.id)))) == 3


@pytest.mark.parametrize("demo", DEMO_USERS, ids=lambda d: d["email"])
def test_demo_accounts_can_log_in_with_the_original_passwords(client, db, demo):
    seed_demo_users(db)

    response = client.post("/api/auth/login",
                           json={"email": demo["email"], "password": demo["password"]})

    assert response.status_code == 200
    assert response.json()["user"]["role"] == demo["role"].value
    assert response.json()["user"]["name"] == demo["name"]
