"""The full seed: teachers + 21 courses, idempotent and non-destructive."""

import pytest
from sqlalchemy import func, select

from app.models import Course, User
from app.roles import Role
from app.seed import TEACHER_DEMO_PASSWORD, SeedError, seed_all
from app.seed_data import COURSES, TEACHERS
from app.services.auth import create_user


def counts(db):
    return (db.scalar(select(func.count(User.id))), db.scalar(select(func.count(Course.id))))


def test_first_run_creates_everything(db):
    result = seed_all(db)

    assert len(result["demo_users"]) == 3
    assert len(result["teachers"]) == 16
    assert result["courses"] == [c["code"] for c in COURSES]
    assert counts(db) == (19, 21)


def test_running_the_seed_again_creates_nothing(db):
    seed_all(db)

    for _ in range(2):
        assert seed_all(db) == {"demo_users": [], "teachers": [], "courses": []}
    assert counts(db) == (19, 21)


def test_original_ids_are_kept(db):
    seed_all(db)

    # .all() returns a list of Row tuples (code, id). dict(result) directly does not work:
    # an SQLAlchemy 2.x Result has .keys() (column names), so dict() treats it as a mapping.
    stored = dict(db.execute(select(Course.code, Course.id)).all())
    assert stored == {c["code"]: c["id"] for c in COURSES}


def test_seed_does_not_overwrite_admin_changes(db):
    seed_all(db)
    course = db.scalar(select(Course).where(Course.code == "CS101"))
    course.seats = 99
    course.name_kk = "Өзгертілген"
    db.commit()

    seed_all(db)

    db.expire_all()
    course = db.scalar(select(Course).where(Course.code == "CS101"))
    assert (course.seats, course.name_kk) == (99, "Өзгертілген")


def test_seed_restores_a_missing_original_course(db):
    seed_all(db)
    db.delete(db.scalar(select(Course).where(Course.code == "DES101")))
    db.commit()

    assert seed_all(db)["courses"] == ["DES101"]
    assert counts(db) == (19, 21)


def test_teacher_accounts_are_real_hashed_logins(client, db):
    seed_all(db)

    for teacher in TEACHERS:
        user = db.scalar(select(User).where(User.email == teacher["email"]))
        assert user.role is Role.TEACHER and user.name == teacher["name"]
        assert user.password_hash.startswith("pbkdf2_sha256$600000$")

    response = client.post("/api/auth/login",
                           json={"email": "issabek.a@kbtu.kz", "password": TEACHER_DEMO_PASSWORD})
    assert response.json()["user"] == {
        "id": response.json()["user"]["id"], "name": "Issabek A.", "studentId": None,
        "email": "issabek.a@kbtu.kz", "role": "teacher",
    }


def test_seed_refuses_to_use_a_non_teacher_account_as_instructor(db):
    create_user(db, name="Impostor", email="john.smith@kbtu.kz", password="password123",
                role=Role.STUDENT, student_id="IMP001")

    with pytest.raises(SeedError, match="john.smith@kbtu.kz"):
        seed_all(db)
