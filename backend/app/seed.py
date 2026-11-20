"""Create the tables, the demo accounts, the teacher accounts and the
original 21 courses.

    python -m app.seed

Idempotent - safe to run any number of times:

* accounts are matched by email, courses by course code;
* only missing rows are created, nothing is duplicated;
* existing rows are never overwritten, so changes made by an admin survive;
* original course ids (1-21) are kept, as the frontend refers to them.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal, close_db, init_db
from app.models import Course, User
from app.roles import Role
from app.seed_data import COURSES, TEACHERS
from app.services.auth import create_user

DEMO_USERS = [
    {"name": "Student Demo", "student_id": "DEMO-ST-001", "email": "student@kbtu.kz",
     "password": "student123", "role": Role.STUDENT},
    {"name": "Teacher Demo", "student_id": "DEMO-TE-001", "email": "teacher@kbtu.kz",
     "password": "teacher123", "role": Role.TEACHER},
    {"name": "Admin Demo", "student_id": "DEMO-AD-001", "email": "admin@kbtu.kz",
     "password": "admin123", "role": Role.ADMIN},
]

# Demo password for the 16 instructor accounts (john.smith@kbtu.kz, ...).
TEACHER_DEMO_PASSWORD = "teacher123"


class SeedError(RuntimeError):
    pass


def seed_demo_users(db: Session) -> list[str]:
    """Create missing demo accounts; return the emails that were created."""
    created = []
    for demo in DEMO_USERS:
        exists = db.scalar(select(User.id).where(User.email == demo["email"]))
        if exists is None:
            create_user(db, **demo)
            created.append(demo["email"])
    return created


def seed_teachers(db: Session) -> list[str]:
    """One teacher account per instructor of the original courses."""
    created = []
    for teacher in TEACHERS:
        user = db.scalar(select(User).where(User.email == teacher["email"]))
        if user is None:
            create_user(db, name=teacher["name"], email=teacher["email"],
                        password=TEACHER_DEMO_PASSWORD, role=Role.TEACHER, student_id=None)
            created.append(teacher["email"])
        elif user.role is not Role.TEACHER:
            raise SeedError(
                f"{teacher['email']} already exists with role '{user.role.value}', "
                "so it cannot be used as the teacher of the original courses."
            )
    return created


def seed_courses(db: Session) -> list[str]:
    """Create the original courses that are missing (matched by code)."""
    email_by_name = {t["name"]: t["email"] for t in TEACHERS}
    created = []
    for data in COURSES:
        if db.scalar(select(Course.id).where(Course.code == data["code"])) is not None:
            continue

        email = email_by_name[data["instructor"]]
        teacher = db.scalar(select(User).where(User.email == email))
        if teacher is None or teacher.role is not Role.TEACHER:
            raise SeedError(f"Teacher account {email} for {data['code']} is missing; run seed_teachers first.")

        course = Course(
            # Keep the original id unless an admin-created course already uses it.
            id=data["id"] if db.get(Course, data["id"]) is None else None,
            code=data["code"],
            category=data["category"],
            name_en=data["name"]["en"],
            name_ru=data["name"]["ru"],
            name_kk=data["name"]["kk"],
            description_en=data["description"]["en"],
            description_ru=data["description"]["ru"],
            description_kk=data["description"]["kk"],
            teacher=teacher,
            credits=data["credits"],
            day=data["day"],
            start_time=data["start"],
            end_time=data["end"],
            room_kind=data["room"]["kind"],
            room_no=data["room"]["no"],
            seats=data["seats"],
        )
        db.add(course)
        db.flush()  # makes the new id/code visible to the checks of the next course
        created.append(data["code"])
    db.commit()
    return created


def seed_all(db: Session) -> dict[str, list[str]]:
    return {
        "demo_users": seed_demo_users(db),
        "teachers": seed_teachers(db),
        "courses": seed_courses(db),
    }


def main() -> None:
    init_db()
    try:
        with SessionLocal() as db:
            result = seed_all(db)
            users = db.scalar(select(func.count(User.id)))
            courses = db.scalar(select(func.count(Course.id)))
    finally:
        close_db()

    print(f"Created: {len(result['demo_users'])} demo accounts, "
          f"{len(result['teachers'])} teacher accounts, {len(result['courses'])} courses.")
    print(f"In database: {users} users, {courses} courses.")


if __name__ == "__main__":
    main()
