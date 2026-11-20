"""Enrollment rules as pure functions (no FastAPI or database needed)."""

from itertools import combinations

import pytest

from app.seed_data import COURSES
from app.services.enrollment import Slot, decide, find_conflict

ORIGINAL = {c["code"]: c for c in COURSES}


def slot(code="X100", *, course_id=None, day="mon", start="09:00", end="10:00"):
    if code in ORIGINAL:
        c = ORIGINAL[code]
        return Slot(c["id"], code, c["name"], c["day"], c["start"], c["end"])
    return Slot(course_id or 900, code, {"en": "X", "ru": "X", "kk": "X"}, day, start, end)


def ok(target, *, capacity=10, taken=0, already=False, registered=()):
    return decide(target, capacity=capacity, seats_taken=taken,
                  already_registered=already, registered=list(registered))


# ------------------------------------------------------------- adjacency

def test_class_ending_at_10_and_class_starting_at_10_do_not_overlap():
    first = slot("A100", course_id=1, start="09:00", end="10:00")
    second = slot("B100", course_id=2, start="10:00", end="11:00")

    assert find_conflict(second, [first]) is None
    assert find_conflict(first, [second]) is None
    assert ok(second, registered=[first]) is None


@pytest.mark.parametrize("start,end", [
    ("09:59", "11:00"),   # starts one minute before the other ends
    ("08:00", "09:01"),   # ends one minute after the other starts
    ("09:00", "10:00"),   # identical
    ("09:15", "09:45"),   # inside
    ("08:00", "11:00"),   # around
])
def test_any_real_overlap_is_a_conflict(start, end):
    existing = slot("A100", course_id=1, start="09:00", end="10:00")
    target = slot("B100", course_id=2, start=start, end=end)

    assert find_conflict(target, [existing]) == existing


def test_same_time_on_another_day_is_fine():
    monday = slot("A100", course_id=1, day="mon")
    tuesday = slot("B100", course_id=2, day="tue")

    assert find_conflict(tuesday, [monday]) is None


# ------------------------------------------------------------- rule order

def test_enrollment_allowed():
    assert ok(slot("CS101")) is None


def test_already_registered_wins_over_everything():
    problem = ok(slot("CS101"), capacity=1, taken=1, already=True)
    assert problem is not None
    assert (problem.status, problem.code) == (409, "err.alreadyRegistered")


def test_no_seats_is_checked_before_conflicts():
    problem = ok(slot("CS330"), capacity=16, taken=16, registered=[slot("STAT201")])
    assert problem is not None
    assert (problem.status, problem.code) == (409, "err.noSeats")


def test_last_free_seat_can_be_taken():
    assert ok(slot("CS101"), capacity=20, taken=19) is None


def test_conflict_names_the_other_course_in_all_languages():
    problem = ok(slot("CS330"), registered=[slot("CS101"), slot("STAT201")])
    assert problem is not None

    assert (problem.status, problem.code) == (409, "err.conflict")
    assert problem.params == {
        "name": ORIGINAL["STAT201"]["name"], "code": "STAT201", "courseId": ORIGINAL["STAT201"]["id"],
    }


# ------------------------------------------------------------- original timetable

def overlapping_pairs():
    return {
        tuple(sorted((a["code"], b["code"])))
        for a, b in combinations(COURSES, 2)
        if find_conflict(slot(a["code"]), [slot(b["code"])])
    }


def test_the_original_timetable_has_exactly_three_clashing_pairs():
    # mon STAT201 13:00-14:50 / CS330 14:00-15:50
    # tue MATH301 13:00-14:50 / UX201 14:00-15:50
    # fri CS250 15:00-16:50 / ECON101 16:00-17:50
    assert overlapping_pairs() == {("CS330", "STAT201"), ("MATH301", "UX201"), ("CS250", "ECON101")}


def test_a_student_can_take_every_course_except_one_of_each_clashing_pair():
    registered = []
    skipped = []
    for course in sorted(COURSES, key=lambda c: c["id"]):
        target = slot(course["code"])
        if ok(target, registered=registered) is None:
            registered.append(target)
        else:
            skipped.append(course["code"])

    assert len(registered) == 18
    # In id order the first course of each pair wins:
    # STAT201 (6) before CS330 (15), UX201 (11) before MATH301 (17), ECON101 (10) before CS250 (16).
    assert sorted(skipped) == ["CS250", "CS330", "MATH301"]
