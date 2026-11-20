"""Enrollment rules (pure Python, no database or FastAPI).

Same order of checks as ``CourseAPI.canRegister`` in the original frontend:

1. the course must exist                    -> 404 err.notFound
2. the student must not be registered yet   -> 409 err.alreadyRegistered
3. there must be a free seat                -> 409 err.noSeats
4. no overlap with the student's courses    -> 409 err.conflict {name}

The old "section picker" (choosing instructor/day/time) is gone: every course
keeps its fixed university schedule, so err.wrongInstructor can no longer occur.

Two time ranges overlap only if one starts before the other ends:
09:00-10:00 and 10:00-11:00 are adjacent, NOT overlapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from app.services.catalog import overlaps


@dataclass(frozen=True)
class Slot:
    """The weekly meeting of one course."""

    course_id: int
    code: str
    name: dict  # {"en": ..., "ru": ..., "kk": ...}
    day: str
    start: str
    end: str


@dataclass(frozen=True)
class Problem:
    """Why an enrollment is refused (turned into an ApiError by the service)."""

    status: int
    code: str
    params: dict[str, Any] = field(default_factory=dict)


def find_conflict(target: Slot, registered: Sequence[Slot]) -> Optional[Slot]:
    """First already-registered course whose meeting overlaps ``target``."""
    for other in registered:
        if other.course_id == target.course_id:
            continue
        if overlaps(target.day, target.start, target.end, other.day, other.start, other.end):
            return other
    return None


def conflict_problem(other: Slot) -> Problem:
    # "name" carries all three languages; the frontend picks one with loc().
    return Problem(409, "err.conflict", {"name": other.name, "code": other.code, "courseId": other.course_id})


def decide(
    target: Slot,
    *,
    capacity: int,
    seats_taken: int,
    already_registered: bool,
    registered: Sequence[Slot],
) -> Optional[Problem]:
    """None if the student may enroll, otherwise the first rule that fails."""
    if already_registered:
        return Problem(409, "err.alreadyRegistered")
    if seats_taken >= capacity:
        return Problem(409, "err.noSeats")
    other = find_conflict(target, registered)
    if other is not None:
        return conflict_problem(other)
    return None


# The enrollment itself: ONE atomic statement. SQLite runs a write statement
# while holding the database's write lock, so the seat count and the
# schedule check below cannot change between "check" and "insert" - two
# concurrent requests can never both take the last seat.
# A duplicate (user_id, course_id) is stopped by the UNIQUE constraint.
# rowcount == 1 -> enrolled; rowcount == 0 -> a rule failed at insert time.
ENROLL_SQL = """
INSERT INTO registrations (user_id, course_id, created_at)
SELECT :user_id, c.id, :created_at
FROM courses AS c
WHERE c.id = :course_id
  AND EXISTS (
      SELECT 1 FROM users AS u
      WHERE u.id = :user_id AND u.role = 'student'
  )
  AND (SELECT COUNT(*) FROM registrations AS r WHERE r.course_id = c.id) < c.seats
  AND NOT EXISTS (
      SELECT 1
      FROM registrations AS r
      JOIN courses AS o ON o.id = r.course_id
      WHERE r.user_id = :user_id
        AND o.id <> c.id
        AND o.day = c.day
        AND o.start_time < c.end_time
        AND c.start_time < o.end_time
  )
"""

# Times are zero-padded "HH:MM" strings (enforced by a CHECK constraint),
# so comparing them as text gives the same result as comparing minutes.


def sqlite_timestamp(value) -> str:
    """A datetime in the exact text format SQLAlchemy uses for SQLite DateTime."""
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")
