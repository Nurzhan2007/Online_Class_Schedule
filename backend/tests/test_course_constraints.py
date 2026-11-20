"""Database-level constraints: they hold even if the API checks are bypassed."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Course, Registration, User


@pytest.fixture()
def john(seeded):
    return seeded.scalar(select(User).where(User.email == "john.smith@kbtu.kz"))


def make_course(teacher_id, **overrides):
    values = dict(
        code="TEST101", category="cs",
        name_en="Test", name_ru="Тест", name_kk="Тест",
        description_en="d", description_ru="d", description_kk="d",
        teacher_id=teacher_id, credits=3, day="tue",
        start_time="18:00", end_time="18:50", room_kind="room", room_no="999", seats=10,
    )
    values.update(overrides)
    return Course(**values)


def test_valid_course_can_be_inserted(seeded, john):
    seeded.add(make_course(john.id))
    seeded.commit()


@pytest.mark.parametrize("overrides", [
    {"credits": 0}, {"credits": 11},
    {"seats": 0}, {"seats": 501},
    {"day": "sat"},
    {"category": "art"},
    {"start_time": "19:00"},                    # after end
    {"start_time": "18:50"},                    # equal to end
    {"start_time": "9:00"}, {"end_time": "1850"},
    {"room_kind": "hall"}, {"room_no": ""},
    {"name_kk": "   "}, {"description_ru": ""},
    {"code": "CS1"},
    {"teacher_id": 99999},                      # foreign key
], ids=lambda o: ",".join(f"{k}={v!r}" for k, v in o.items()))
def test_invalid_rows_are_rejected_by_the_database(seeded, john, overrides):
    # John's id is only the default: an override (e.g. teacher_id=99999) replaces it.
    # Passing john.id positionally as well would bind teacher_id twice (TypeError).
    seeded.add(make_course(**{"teacher_id": john.id, **overrides}))

    with pytest.raises(IntegrityError) as rejected:
        seeded.commit()
    seeded.rollback()

    if "teacher_id" in overrides:
        # The row must be refused by the FOREIGN KEY itself, for a teacher that really does not exist.
        assert "FOREIGN KEY constraint failed" in str(rejected.value)
        assert seeded.get(User, overrides["teacher_id"]) is None


def test_course_codes_are_unique(seeded, john):
    seeded.add(make_course(john.id, code="CS101"))

    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()


def test_teacher_with_courses_cannot_be_deleted(seeded, john):
    seeded.delete(john)

    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()
    assert seeded.scalar(select(Course.id).where(Course.code == "CS101")) is not None


def test_a_student_cannot_register_twice_for_the_same_course(seeded, add_registrations):
    course = add_registrations("CS101", 1)
    student_id = seeded.scalar(select(Registration.user_id).where(Registration.course_id == course.id))

    seeded.add(Registration(user_id=student_id, course_id=course.id))
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()


def test_course_with_registrations_cannot_be_deleted_in_the_database(seeded, add_registrations):
    course = add_registrations("CS101", 1)

    seeded.delete(course)
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()


def test_deleting_a_student_removes_their_registrations(seeded, add_registrations):
    course = add_registrations("CS101", 1)
    student = seeded.get(User, seeded.scalar(select(Registration.user_id)))

    seeded.delete(student)
    seeded.commit()

    assert seeded.scalar(select(Registration.id).where(Registration.course_id == course.id)) is None
