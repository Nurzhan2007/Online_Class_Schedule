"""Shared test setup.

The environment is configured BEFORE the app is imported, so tests always use
a throw-away SQLite file and never touch the real backend/kbtu.db.
FastAPI/SQLAlchemy are imported lazily inside fixtures, so the pure-Python
tests (config, security, schemas, lockout rules) run even without them.
"""

import itertools
import os
import tempfile
from pathlib import Path

import pytest

_TEST_DIR = Path(tempfile.mkdtemp(prefix="kbtu-tests-"))
os.environ["DATABASE_URL"] = "sqlite:///" + (_TEST_DIR / "test.db").as_posix()
os.environ["SECRET_KEY"] = "test-only-secret-key-" + "0123456789abcdef" * 3

DEFAULT_PASSWORD = "password123"


@pytest.fixture(scope="session", autouse=True)
def _close_database_connections():
    """Close pooled SQLite connections once all tests are done (no ResourceWarning)."""
    yield
    try:
        from app.database import close_db
    except ModuleNotFoundError:  # SQLAlchemy not installed: only pure tests ran
        return
    close_db()


@pytest.fixture()
def client():
    """A test client on a fresh, empty database."""
    from fastapi.testclient import TestClient

    import app.models  # noqa: F401
    from app.database import Base, engine
    from app.main import create_app

    Base.metadata.drop_all(engine)
    # "with" runs the lifespan: tables are created on start, connections closed on exit.
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def db(client):
    """A database session for arranging and checking data directly."""
    from app.database import SessionLocal

    with SessionLocal() as session:
        yield session


@pytest.fixture()
def make_user(db):
    """Create a user directly in the database: make_user("teacher", email=...)."""
    from app.roles import Role
    from app.services.auth import create_user

    counter = itertools.count(1)

    def _make(role="student", email=None, password=DEFAULT_PASSWORD, name=None):
        number = next(counter)
        role = Role(role)
        return create_user(
            db,
            name=name or f"{role.value.title()} {number}",
            email=email or f"{role.value}{number}@kbtu.kz",
            password=password,
            role=role,
            student_id=f"TEST{number:04d}" if role is Role.STUDENT else None,
        )

    return _make


@pytest.fixture()
def seeded(db):
    """Database filled exactly like `python -m app.seed` (3 demo + 16 teachers + 21 courses)."""
    from app.seed import seed_all

    seed_all(db)
    return db


@pytest.fixture()
def add_registrations(seeded):
    """add_registrations("CS101", 3): put new students into a course directly.

    The enrollment API arrives in Phase 4. These students never log in, so
    they get a placeholder hash instead of spending 0.1 s per PBKDF2 hash.
    """
    from sqlalchemy import select

    from app.models import Course, Registration, User
    from app.roles import Role

    def _add(course_code, count):
        course = seeded.scalar(select(Course).where(Course.code == course_code))
        start = (seeded.scalar(select(User.id).order_by(User.id.desc())) or 0) + 1
        for n in range(start, start + count):
            student = User(name=f"Seat Taker {n}", email=f"taker{n}@kbtu.kz",
                           student_id=f"SEAT{n:05d}", password_hash="not-a-login-account",
                           role=Role.STUDENT)
            seeded.add(student)
            seeded.flush()
            seeded.add(Registration(user_id=student.id, course_id=course.id))
        seeded.commit()
        return course

    return _add


@pytest.fixture()
def make_student(db):
    """make_student() -> a new student account (placeholder hash: used with headers_for)."""
    from app.models import User
    from app.roles import Role

    counter = itertools.count(1)

    def _make():
        n = next(counter)
        user = User(name=f"Extra Student {n}", email=f"extra{n}@kbtu.kz",
                    student_id=f"EXTRA{n:04d}", password_hash="not-a-login-account",
                    role=Role.STUDENT)
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture()
def user_by_email(db):
    from sqlalchemy import select

    from app.models import User

    def _get(email):
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None, email
        return user

    return _get


@pytest.fixture()
def headers_for():
    """Authorization header for a user, without spending time on a password login."""
    from app.config import get_settings
    from app.security import create_access_token

    def _headers(user):
        token = create_access_token(user.id, user.role.value, get_settings()).token
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture()
def as_role(seeded, user_by_email, headers_for):
    """as_role("student") -> headers of the seeded demo account with that role."""

    def _headers(role):
        return headers_for(user_by_email(f"{role}@kbtu.kz"))

    return _headers


@pytest.fixture()
def login(client):
    """Log in through the API and return the access token."""

    def _login(email, password=DEFAULT_PASSWORD):
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return response.json()["access_token"]

    return _login
