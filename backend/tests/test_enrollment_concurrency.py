"""Parallel enrollment through the real service and SQLAlchemy sessions.

Each thread uses its own database session, like parallel HTTP requests.
(test_enrollment_sql.py proves the same for the raw SQL statement.)
"""

import threading

from sqlalchemy import func, select

from app.database import SessionLocal
from app.errors import ApiError
from app.models import Registration
from app.seed_data import COURSES
from app.services import registrations as registration_service

ID = {c["code"]: c["id"] for c in COURSES}


def run_in_parallel(jobs):
    """Run enroll(user_id, course_id) jobs at the same moment; return the outcomes."""
    barrier = threading.Barrier(len(jobs))
    outcomes = []
    lock = threading.Lock()

    def worker(user_id, course_id):
        with SessionLocal() as db:
            barrier.wait()
            try:
                registration_service.enroll(db, user_id, course_id)
                outcome = "ok"
            except ApiError as exc:
                outcome = exc.code
            except Exception as exc:  # anything else is a bug - reported below
                outcome = repr(exc)
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker, args=job) for job in jobs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return outcomes


def count(db, **where):
    query = select(func.count(Registration.id))
    for column, value in where.items():
        query = query.where(getattr(Registration, column) == value)
    db.expire_all()
    return db.scalar(query)


def test_parallel_students_cannot_oversell_a_course(seeded, make_student):
    students = [make_student().id for _ in range(30)]

    outcomes = run_in_parallel([(sid, ID["CS310"]) for sid in students])   # capacity 12

    assert outcomes.count("ok") == 12
    assert outcomes.count("err.noSeats") == 18
    assert count(seeded, course_id=ID["CS310"]) == 12


def test_parallel_requests_cannot_create_a_timetable_clash(seeded, make_student):
    student = make_student().id

    outcomes = run_in_parallel([(student, ID["STAT201"]), (student, ID["CS330"])] * 4)

    assert count(seeded, user_id=student) == 1
    assert outcomes.count("ok") == 1
    assert set(outcomes) <= {"ok", "err.conflict", "err.alreadyRegistered"}


def test_parallel_double_clicks_create_one_registration(seeded, make_student):
    student = make_student().id

    outcomes = run_in_parallel([(student, ID["CS101"])] * 8)

    assert count(seeded, user_id=student, course_id=ID["CS101"]) == 1
    assert outcomes.count("ok") == 1
    assert set(outcomes) == {"ok", "err.alreadyRegistered"}
