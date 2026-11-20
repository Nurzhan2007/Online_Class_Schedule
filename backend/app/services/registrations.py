"""Student enrollment (database layer).

Every function works on ``user_id`` = the logged-in student taken from the
JWT, so a student can only ever see, create or cancel their own enrollments.

Enrolling is two steps:

1. a friendly pre-check that names the exact problem (already registered,
   no seats, which course clashes);
2. the atomic ``ENROLL_SQL`` insert, which re-checks role, seats and the
   timetable inside SQLite's write lock. If something changed between the
   two steps (another student took the last seat a millisecond earlier),
   nothing is inserted and the pre-check is repeated to report why.
"""

from __future__ import annotations

from typing import NoReturn, Optional

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Course, Registration, User, utcnow_naive
from app.roles import Role
from app.schemas import EnrollmentCheck, MyCourseOut, MyRegistrationsOut
from app.services.courses import get_course, seats_left, seats_taken, seats_taken_for, to_out
from app.services.enrollment import ENROLL_SQL, Problem, Slot, decide, sqlite_timestamp


def _slot(course: Course) -> Slot:
    return Slot(
        course_id=course.id,
        code=course.code,
        name={"en": course.name_en, "ru": course.name_ru, "kk": course.name_kk},
        day=course.day,
        start=course.start_time,
        end=course.end_time,
    )


def _my_rows(db: Session, user_id: int) -> list[tuple[Registration, Course]]:
    query = (
        select(Registration, Course)
        .join(Course, Course.id == Registration.course_id)
        .where(Registration.user_id == user_id)
        .order_by(Registration.id)  # registration order, like the original frontend
    )
    return [(row[0], row[1]) for row in db.execute(query)]


def _raise(problem: Problem) -> NoReturn:
    raise ApiError(problem.status, problem.code, problem.params)


def _require_student(db: Session, user_id: int) -> None:
    # The router already allows only students; this keeps the service safe on its own.
    user = db.get(User, user_id)
    if user is None or user.role is not Role.STUDENT:
        raise ApiError(403, "auth.denied")


def _problem(db: Session, user_id: int, course: Course) -> Optional[Problem]:
    rows = _my_rows(db, user_id)
    return decide(
        _slot(course),
        capacity=course.seats,
        seats_taken=seats_taken_for(db, course.id),
        already_registered=any(c.id == course.id for _, c in rows),
        registered=[_slot(c) for _, c in rows],
    )


# ---------------------------------------------------------------- reading

def _my_course(registration: Registration, course: Course, taken: int) -> MyCourseOut:
    return MyCourseOut(**to_out(course, taken).model_dump(), registeredAt=registration.created_at)


def list_my_registrations(db: Session, user_id: int) -> MyRegistrationsOut:
    taken = seats_taken(db)
    rows = sorted(_my_rows(db, user_id), key=lambda row: row[1].id)  # catalogue order, like myCourses()
    courses = [_my_course(reg, course, taken.get(course.id, 0)) for reg, course in rows]
    return MyRegistrationsOut(
        courses=courses,
        count=len(courses),
        totalCredits=sum(c.credits for c in courses),
    )


# ---------------------------------------------------------------- changes

def check_enrollment(db: Session, user_id: int, course_id: int) -> EnrollmentCheck:
    """Dry run: the same checks as enroll(), nothing is saved."""
    _require_student(db, user_id)
    course = get_course(db, course_id)
    problem = _problem(db, user_id, course)
    if problem is not None:
        _raise(problem)
    return EnrollmentCheck(ok=True, seatsLeft=seats_left(course.seats, seats_taken_for(db, course.id)))


def enroll(db: Session, user_id: int, course_id: int) -> MyCourseOut:
    _require_student(db, user_id)
    course = get_course(db, course_id)

    problem = _problem(db, user_id, course)
    if problem is not None:
        _raise(problem)

    try:
        result = db.execute(
            text(ENROLL_SQL),
            {"user_id": user_id, "course_id": course.id, "created_at": sqlite_timestamp(utcnow_naive())},
        )
    except IntegrityError:
        # UNIQUE (user_id, course_id): a parallel request enrolled this student first.
        db.rollback()
        raise ApiError(409, "err.alreadyRegistered") from None

    if result.rowcount != 1:
        # A rule failed at insert time (the state changed after the pre-check).
        db.rollback()
        _raise(_problem(db, user_id, get_course(db, course_id)) or Problem(409, "err.noSeats"))

    db.commit()

    registration = db.scalar(
        select(Registration).where(Registration.user_id == user_id, Registration.course_id == course.id)
    )
    return _my_course(registration, course, seats_taken_for(db, course.id))


def cancel_enrollment(db: Session, user_id: int, course_id: int) -> None:
    """Remove the student's own registration. Idempotent: cancelling a course
    you are not registered for changes nothing (like the original frontend)."""
    _require_student(db, user_id)
    get_course(db, course_id)  # unknown course -> 404 err.notFound
    db.execute(
        delete(Registration).where(Registration.user_id == user_id, Registration.course_id == course_id)
    )
    db.commit()
