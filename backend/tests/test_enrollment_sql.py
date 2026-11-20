"""The atomic enrollment statement, run on real SQLite (Python's sqlite3).

No SQLAlchemy needed: the table layout below mirrors the columns of
app.models that ENROLL_SQL uses, so these tests run everywhere - including
the concurrency tests that prove capacity cannot be oversold.
"""

import sqlite3
import threading
from datetime import datetime

import pytest

from app.services.enrollment import ENROLL_SQL, sqlite_timestamp

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, role VARCHAR(20) NOT NULL);
CREATE TABLE courses (
    id INTEGER PRIMARY KEY, seats INTEGER NOT NULL, day VARCHAR(3) NOT NULL,
    start_time VARCHAR(5) NOT NULL, end_time VARCHAR(5) NOT NULL
);
CREATE TABLE registrations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    course_id INTEGER NOT NULL REFERENCES courses(id),
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_registrations_user_course UNIQUE (user_id, course_id)
);
"""


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "enroll.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO users (id, role) VALUES (?, ?)",
                         [(i, "student") for i in range(1, 101)]
                         + [(200, "teacher"), (201, "admin")])
        conn.executemany(
            "INSERT INTO courses (id, seats, day, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 2, "mon", "09:00", "10:00"),
                (2, 5, "mon", "10:00", "11:00"),    # adjacent to course 1
                (3, 5, "mon", "09:30", "10:30"),    # overlaps 1 and 2
                (4, 5, "tue", "09:00", "10:00"),    # other day
                (5, 10, "fri", "13:00", "14:50"),
            ],
        )
    conn.close()
    return path


def enroll(conn, user_id, course_id):
    cursor = conn.execute(ENROLL_SQL, {"user_id": user_id, "course_id": course_id,
                                       "created_at": sqlite_timestamp(datetime(2026, 11, 13, 12, 0))})
    conn.commit()
    return cursor.rowcount


@pytest.fixture()
def conn(db_path):
    connection = sqlite3.connect(db_path)
    yield connection
    connection.close()


def registered(conn, course_id=None, user_id=None):
    query, args = "SELECT COUNT(*) FROM registrations WHERE 1=1", []
    if course_id is not None:
        query, args = query + " AND course_id = ?", args + [course_id]
    if user_id is not None:
        query, args = query + " AND user_id = ?", args + [user_id]
    return conn.execute(query, args).fetchone()[0]


# ------------------------------------------------------------- single requests

def test_student_is_enrolled(conn):
    assert enroll(conn, 1, 1) == 1
    assert registered(conn, course_id=1, user_id=1) == 1


def test_timestamp_is_stored_in_sqlalchemy_format(conn):
    enroll(conn, 1, 1)
    assert conn.execute("SELECT created_at FROM registrations").fetchone()[0] == "2026-11-13 12:00:00.000000"


def test_capacity_is_respected(conn):
    assert [enroll(conn, user, 1) for user in (1, 2, 3)] == [1, 1, 0]   # 2 seats
    assert registered(conn, course_id=1) == 2


def test_duplicate_is_stopped_by_the_unique_constraint(conn):
    enroll(conn, 1, 4)
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        enroll(conn, 1, 4)
    conn.rollback()
    assert registered(conn, course_id=4) == 1


def test_adjacent_classes_are_allowed(conn):
    assert enroll(conn, 1, 1) == 1   # 09:00-10:00
    assert enroll(conn, 1, 2) == 1   # 10:00-11:00


def test_overlapping_class_is_refused(conn):
    enroll(conn, 1, 1)
    assert enroll(conn, 1, 3) == 0   # 09:30-10:30
    assert registered(conn, user_id=1) == 1


def test_overlap_check_is_per_student(conn):
    enroll(conn, 1, 1)
    assert enroll(conn, 2, 3) == 1   # another student may take the overlapping course


def test_same_time_other_day_is_allowed(conn):
    enroll(conn, 1, 1)
    assert enroll(conn, 1, 4) == 1


@pytest.mark.parametrize("user_id", [200, 201, 999])   # teacher, admin, missing
def test_only_existing_student_accounts_can_be_enrolled(conn, user_id):
    assert enroll(conn, user_id, 4) == 0
    assert registered(conn) == 0


def test_unknown_course_inserts_nothing(conn):
    assert enroll(conn, 1, 999) == 0


# ------------------------------------------------------------- concurrency

def run_in_parallel(db_path, jobs):
    """Run enroll(user, course) jobs at the same moment, one connection per thread."""
    barrier = threading.Barrier(len(jobs))
    results, errors = [], []

    def worker(user_id, course_id):
        connection = sqlite3.connect(db_path, timeout=30)
        try:
            # Like the real service: read first (pre-check), then the atomic insert.
            connection.execute("SELECT COUNT(*) FROM registrations WHERE course_id = ?",
                               (course_id,)).fetchone()
            barrier.wait()
            results.append(enroll(connection, user_id, course_id))
        except sqlite3.IntegrityError:
            results.append("duplicate")
        except Exception as exc:  # pragma: no cover - reported by the assertion below
            errors.append(repr(exc))
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=job) for job in jobs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    return results


def test_capacity_cannot_be_oversold_by_parallel_requests(db_path, conn):
    results = run_in_parallel(db_path, [(user, 5) for user in range(1, 61)])   # 60 students, 10 seats

    assert results.count(1) == 10
    assert results.count(0) == 50
    assert registered(conn, course_id=5) == 10


def test_parallel_requests_cannot_create_a_schedule_conflict(db_path, conn):
    # One student fires requests for two overlapping courses at the same time.
    results = run_in_parallel(db_path, [(7, 1), (7, 3)] * 5)

    assert registered(conn, user_id=7) == 1
    assert results.count(1) == 1


def test_parallel_duplicate_requests_create_one_registration(db_path, conn):
    results = run_in_parallel(db_path, [(8, 4)] * 10)

    assert registered(conn, user_id=8, course_id=4) == 1
    assert results.count(1) == 1
    assert results.count("duplicate") == 9
