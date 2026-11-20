"""The seed catalogue must be exactly the original 21 courses of the frontend.

Until Phase 5 the courses were hard-coded in online-class-schedule/js/api.js.
Phase 5 moved them to the database (the frontend now loads them from the API),
so tests/fixtures/original_courses.js keeps a verbatim copy of that original
array; a SHA-256 check proves the copy is unchanged.

Pure Python: no FastAPI or database needed.
"""

import hashlib
import json
import re
from itertools import combinations
from pathlib import Path

import pytest

from app.config import DEFAULT_FRONTEND_DIR
from app.schemas import CourseIn
from app.seed_data import COURSES, TEACHERS
from app.services.catalog import CATEGORIES, overlaps

ORIGINAL_JS = Path(__file__).resolve().parent / "fixtures" / "original_courses.js"
# sha256 of the "const COURSES = [ ... ];" text in api.js at GitHub commit 4c77989
ORIGINAL_SHA256 = "6a7aff9cb95ffb1893b24c8030582ca4f4f83c9a1dfac2edeffd00dac8231714"


def original_literal():
    source = ORIGINAL_JS.read_text(encoding="utf-8")
    start = source.index("const COURSES = [")
    return source[start: source.index("];", start) + 2]


def load_original_courses():
    """Parse the original COURSES array literal as JSON (keys get quoted)."""
    literal = original_literal()[len("const COURSES = "):-1]
    as_json = re.sub(r'([{,]\s*)([A-Za-z_]\w*)\s*:', r'\1"\2":', literal)
    return json.loads(as_json)


ORIGINAL = load_original_courses()


def test_the_original_copy_is_unchanged():
    digest = hashlib.sha256(original_literal().encode("utf-8")).hexdigest()
    assert digest == ORIGINAL_SHA256


def test_the_frontend_no_longer_hard_codes_courses():
    api_js = (DEFAULT_FRONTEND_DIR / "js" / "api.js").read_text(encoding="utf-8")
    assert "const COURSES" not in api_js
    assert "Introduction to Programming" not in api_js


def test_there_are_exactly_21_courses():
    assert len(ORIGINAL) == 21
    assert len(COURSES) == 21


def test_seed_data_is_identical_to_the_frontend_data():
    # Every field of every course: id, code, category, en/ru/kk name and
    # description, instructor, credits, day, start, end, room, seats.
    assert COURSES == ORIGINAL


@pytest.mark.parametrize("original", ORIGINAL, ids=lambda c: c["code"])
def test_each_course_keeps_all_three_languages(original):
    seeded = next(c for c in COURSES if c["id"] == original["id"])
    for field in ("name", "description"):
        assert set(seeded[field]) == {"en", "ru", "kk"}
        for lang in ("en", "ru", "kk"):
            assert seeded[field][lang] == original[field][lang]
            assert seeded[field][lang].strip()


def test_ids_and_codes_are_unique():
    assert len({c["id"] for c in COURSES}) == 21
    assert len({c["code"] for c in COURSES}) == 21
    assert [c["id"] for c in COURSES] == list(range(1, 22))


def test_every_instructor_has_exactly_one_teacher_account():
    instructors = {c["instructor"] for c in COURSES}
    teacher_names = [t["name"] for t in TEACHERS]

    assert sorted(teacher_names) == sorted(instructors)
    assert len(teacher_names) == len(set(teacher_names)) == 16
    assert len({t["email"] for t in TEACHERS}) == 16
    assert all(t["email"].endswith("@kbtu.kz") for t in TEACHERS)


def test_categories_are_the_known_ones():
    assert {c["category"] for c in COURSES} == set(CATEGORIES)


@pytest.mark.parametrize("course", COURSES, ids=lambda c: c["code"])
def test_every_original_course_passes_the_admin_validation(course):
    data = {k: v for k, v in course.items() if k not in ("id", "instructor")}
    CourseIn.model_validate({**data, "teacherId": 1})


def test_original_timetable_has_no_teacher_or_room_double_booking():
    for a, b in combinations(COURSES, 2):
        clash = overlaps(a["day"], a["start"], a["end"], b["day"], b["start"], b["end"])
        if clash:
            assert a["instructor"] != b["instructor"], (a["code"], b["code"])
            assert a["room"] != b["room"], (a["code"], b["code"])
