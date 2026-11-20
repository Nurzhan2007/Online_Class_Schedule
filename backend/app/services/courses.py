"""Course queries and admin changes (database layer).

Business rules checked here, on top of the database constraints:

* a course's teacher must be an existing account with the *teacher* role;
* course codes are unique;
* a teacher cannot teach two courses at overlapping times;
* a room cannot host two courses at overlapping times;
* capacity cannot drop below the number of registered students;
* a course cannot be moved to a time that clashes with another course of
  any student already registered in it;
* a course with registered students cannot be deleted.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.errors import ApiError
from app.models import Course, Registration, User
from app.roles import Role
from app.schemas import CourseIn, CourseMeta, CourseOut, LocalizedText, Room
from app.services.catalog import DAY_ORDER, natural_code_key, overlaps


# ---------------------------------------------------------------- seats

def seats_taken(db: Session) -> dict[int, int]:
    """Number of registered students per course id (courses without any are absent)."""
    rows = db.execute(
        select(Registration.course_id, func.count(Registration.id)).group_by(Registration.course_id)
    )
    return {course_id: count for course_id, count in rows}


def seats_taken_for(db: Session, course_id: int) -> int:
    return db.scalar(
        select(func.count(Registration.id)).where(Registration.course_id == course_id)
    ) or 0


def seats_left(capacity: int, taken: int) -> int:
    return max(0, capacity - taken)


# ---------------------------------------------------------------- reading

def to_out(course: Course, taken: int) -> CourseOut:
    return CourseOut(
        id=course.id,
        code=course.code,
        category=course.category,
        name=LocalizedText(en=course.name_en, ru=course.name_ru, kk=course.name_kk),
        description=LocalizedText(
            en=course.description_en, ru=course.description_ru, kk=course.description_kk
        ),
        instructor=course.teacher.name,
        teacherId=course.teacher_id,
        credits=course.credits,
        day=course.day,
        start=course.start_time,
        end=course.end_time,
        room=Room(kind=course.room_kind, no=course.room_no),
        seats=course.seats,
        seatsLeft=seats_left(course.seats, taken),
    )


def list_courses(db: Session, teacher_id: Optional[int] = None) -> list[CourseOut]:
    query = select(Course).options(selectinload(Course.teacher)).order_by(Course.id)
    if teacher_id is not None:
        query = query.where(Course.teacher_id == teacher_id)
    taken = seats_taken(db)
    return [to_out(course, taken.get(course.id, 0)) for course in db.scalars(query)]


def get_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise ApiError(404, "err.notFound", {"id": course_id})
    return course


def course_out(db: Session, course: Course) -> CourseOut:
    return to_out(course, seats_taken_for(db, course.id))


def catalogue_meta(courses: list[CourseOut]) -> CourseMeta:
    """Filter options, built like CourseAPI.getCategories/getInstructors/getCreditOptions."""
    by_id = sorted(courses, key=lambda c: c.id)
    return CourseMeta(
        # categories in order of first appearance, like [...new Set(...)] in api.js
        categories=list(dict.fromkeys(c.category for c in by_id)),
        instructors=sorted({c.instructor for c in courses}),
        credits=sorted({c.credits for c in courses}),
        days=list(DAY_ORDER),
    )


def teacher_courses(db: Session, teacher: User) -> list[CourseOut]:
    return sorted(list_courses(db, teacher_id=teacher.id), key=lambda c: natural_code_key(c.code))


# ---------------------------------------------------------------- admin changes

def _validated_teacher(db: Session, teacher_id: int) -> User:
    teacher = db.get(User, teacher_id)
    if teacher is None or teacher.role is not Role.TEACHER:
        raise ApiError(422, "err.teacherNotFound", {"teacherId": teacher_id})
    return teacher


def _check_conflicts(db: Session, data: CourseIn, exclude_id: Optional[int]) -> None:
    same_code = select(Course.id).where(Course.code == data.code)
    if exclude_id is not None:
        same_code = same_code.where(Course.id != exclude_id)
    if db.scalar(same_code) is not None:
        raise ApiError(409, "err.codeTaken", {"code": data.code})

    same_day = select(Course).where(Course.day == data.day)
    if exclude_id is not None:
        same_day = same_day.where(Course.id != exclude_id)
    for other in db.scalars(same_day.order_by(Course.code)):
        if not overlaps(data.day, data.start, data.end, other.day, other.start_time, other.end_time):
            continue
        if other.teacher_id == data.teacherId:
            raise ApiError(409, "err.teacherConflict", {"code": other.code})
        if (other.room_kind, other.room_no) == (data.room.kind, data.room.no):
            raise ApiError(409, "err.roomConflict", {"code": other.code})


def _check_registered_students(db: Session, course: Course, data: CourseIn) -> None:
    """Moving a course must not create a timetable clash for students already in it."""
    if (data.day, data.start, data.end) == (course.day, course.start_time, course.end_time):
        return
    students_of_course = select(Registration.user_id).where(Registration.course_id == course.id)
    rows = db.execute(
        select(Registration.user_id, Course.day, Course.start_time, Course.end_time)
        .join(Course, Course.id == Registration.course_id)
        .where(Registration.user_id.in_(students_of_course), Registration.course_id != course.id)
    )
    clashing = {
        user_id
        for user_id, day, start, end in rows
        if overlaps(data.day, data.start, data.end, day, start, end)
    }
    if clashing:
        raise ApiError(409, "err.studentScheduleConflict", {"count": len(clashing)})


def _apply(course: Course, data: CourseIn, teacher: User) -> None:
    course.code = data.code
    course.category = data.category
    course.name_en, course.name_ru, course.name_kk = data.name.en, data.name.ru, data.name.kk
    course.description_en = data.description.en
    course.description_ru = data.description.ru
    course.description_kk = data.description.kk
    course.teacher = teacher  # sets teacher_id and keeps the relationship in sync
    course.credits = data.credits
    course.day = data.day
    course.start_time, course.end_time = data.start, data.end
    course.room_kind, course.room_no = data.room.kind, data.room.no
    course.seats = data.seats


def _commit(db: Session, code: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        # Only reachable through a race (e.g. the same code created twice at once).
        db.rollback()
        raise ApiError(409, "err.codeTaken", {"code": code}) from None


def create_course(db: Session, data: CourseIn) -> CourseOut:
    teacher = _validated_teacher(db, data.teacherId)
    _check_conflicts(db, data, exclude_id=None)
    course = Course()
    _apply(course, data, teacher)
    db.add(course)
    _commit(db, data.code)
    return course_out(db, course)


def update_course(db: Session, course_id: int, data: CourseIn) -> CourseOut:
    course = get_course(db, course_id)
    teacher = _validated_teacher(db, data.teacherId)
    _check_conflicts(db, data, exclude_id=course.id)
    taken = seats_taken_for(db, course.id)
    if data.seats < taken:
        raise ApiError(409, "err.seatsBelowRegistered", {"registered": taken})
    _check_registered_students(db, course, data)
    _apply(course, data, teacher)
    _commit(db, data.code)
    return course_out(db, course)


def delete_course(db: Session, course_id: int) -> None:
    course = get_course(db, course_id)
    taken = seats_taken_for(db, course.id)
    if taken:
        raise ApiError(409, "err.courseHasRegistrations", {"count": taken})
    db.delete(course)
    db.commit()
