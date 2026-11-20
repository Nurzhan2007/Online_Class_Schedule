"""Search, filters and sorting (pure Python, same rules as CourseAPI.search)."""

import pytest

from app.schemas import CourseOut
from app.seed_data import COURSES
from app.services.catalog import (
    CourseFilters,
    collation_key,
    filter_and_sort,
    natural_code_key,
    overlaps,
    time_to_minutes,
)

TEACHER_IDS = {name: i for i, name in enumerate(sorted({c["instructor"] for c in COURSES}), 100)}


def catalogue(seats_left=None):
    seats_left = seats_left or {}
    return [
        CourseOut(**c, teacherId=TEACHER_IDS[c["instructor"]],
                  seatsLeft=seats_left.get(c["code"], c["seats"]))
        for c in COURSES
    ]


def codes(courses):
    return [c.code for c in courses]


def search(**kwargs):
    return codes(filter_and_sort(catalogue(kwargs.pop("seats_left", None)), CourseFilters(**kwargs)))


# ------------------------------------------------------------- helpers

def test_time_and_overlap():
    assert time_to_minutes("09:00") == 540
    assert overlaps("mon", "09:00", "10:50", "mon", "10:00", "11:50")
    assert not overlaps("mon", "09:00", "10:50", "tue", "09:00", "10:50")
    assert not overlaps("mon", "09:00", "10:50", "mon", "10:50", "12:00")  # touching is fine
    assert overlaps("fri", "13:00", "14:50", "fri", "13:00", "13:50")


def test_natural_code_order():
    assert sorted(["CS1000", "CS205", "cs101", "MATH101"], key=natural_code_key) == \
        ["cs101", "CS205", "CS1000", "MATH101"]


def test_kazakh_letters_sort_inside_the_alphabet():
    words = ["Бағдарламалау", "Әдебиет", "Ақпарат", "Ыдыс", "Іскерлік", "Қазақ", "Кітап"]
    assert sorted(words, key=lambda w: collation_key(w, "kk")) == \
        ["Ақпарат", "Әдебиет", "Бағдарламалау", "Кітап", "Қазақ", "Ыдыс", "Іскерлік"]


def test_russian_yo_sorts_after_ye():
    words = ["Ёлка", "Жук", "Ель"]
    assert sorted(words, key=lambda w: collation_key(w, "ru")) == ["Ель", "Ёлка", "Жук"]


# ------------------------------------------------------------- defaults

def test_default_is_all_21_courses_sorted_by_code():
    result = search()
    assert len(result) == 21
    assert result[:5] == ["CS101", "CS205", "CS220", "CS240", "CS250"]
    assert result[-1] == "UX201"


def test_code_descending():
    assert search(sort_dir="desc")[0] == "UX201"


# ------------------------------------------------------------- search term

@pytest.mark.parametrize("term,expected", [
    ("cs101", ["CS101"]),
    ("  CALCULUS ", ["MATH101"]),
    ("программ", ["CS101"]),                    # Russian name
    ("ҚАЗАҚ", ["KAZ101"]),                       # Kazakh, upper case
    ("бағдарламалау", ["CS101"]),
    ("sarah wilson", ["MATH101", "MATH202"]),   # instructor
    ("nothing-like-this", []),
])
def test_term_search(term, expected):
    assert search(term=term) == expected


def test_term_does_not_search_descriptions():
    # Same as the frontend: only code, instructor and names are searched.
    assert search(term="eigenvalues") == []


# ------------------------------------------------------------- filters

def test_category_filter():
    assert search(category="physics") == ["PHYS101", "PHYS201"]


def test_day_filter():
    assert search(day="fri") == ["CS250", "CS310", "ECON101", "INFT3107"]


def test_instructor_filter():
    assert search(instructor="Kamila Bekova") == ["DES101", "UX201"]


def test_teacher_id_filter():
    assert search(teacher_id=TEACHER_IDS["John Smith"]) == ["CS101", "CS250"]


def test_credits_filter():
    assert search(credits=3) == ["DES101", "ECON101", "ECON201", "ENG102", "INFT3107", "KAZ101", "RUS101"]


def test_all_means_no_filter():
    assert len(search(category="all", day="all", instructor="all", credits="all")) == 21


def test_filters_combine():
    assert search(category="cs", day="mon", credits=5) == ["CS101", "CS240", "CS330"]


def test_only_available_hides_full_courses():
    result = search(only_available=True, seats_left={"CS101": 0, "MATH101": 0})
    assert "CS101" not in result and "MATH101" not in result
    assert len(result) == 19


# ------------------------------------------------------------- sorting

def test_sort_by_credits_desc_breaks_ties_by_code_asc():
    result = search(sort_by="credits", sort_dir="desc")
    assert result[:7] == ["CS101", "CS205", "CS220", "CS240", "CS250", "CS310", "CS330"]
    assert result[-1] == "RUS101"


def test_sort_by_day_then_start_time():
    result = search(sort_by="day")
    assert result[:5] == ["CS101", "CS240", "STAT201", "CS330", "PHYS201"]  # Monday 09,11,13,14,16
    assert result[-1] == "ECON101"                                         # Friday 16:00


def test_sort_by_seats_left():
    result = search(sort_by="seats", sort_dir="desc", seats_left={"CS101": 0})
    assert result[0] == "INFT3107"   # 74 seats
    assert result[-1] == "CS101"     # 0 left


def test_sort_by_instructor():
    assert search(sort_by="instructor")[:2] == ["KAZ101", "CS310"]  # Aigerim, Alex


def test_sort_by_name_in_english():
    result = search(sort_by="name", lang="en")
    assert result[:3] == ["ENG102", "INFT3107", "MATH101"]  # Academic, Basics, Calculus
    assert result[-1] == "CS220"                            # Web Development


def test_sort_by_name_in_russian():
    result = search(sort_by="name", lang="ru")
    assert result[0] == "ENG102"                            # Академический английский
    assert result.index("CS101") < result.index("CS220")    # Введение < Веб-разработка


def test_sort_by_name_in_kazakh_respects_kazakh_letters():
    result = search(sort_by="name", lang="kk")
    assert result[0] == "ENG102"                            # Академиялық ағылшын тілі
    # Ақпараттық (ақ) must come before Бағдарламалау (б); in plain
    # code-point order "қ"/"ә"/"і" would be pushed after "я".
    assert result.index("INFT3107") < result.index("CS101")
    # Kazakh alphabet: ... к, қ, л, м ... -> "Компьютерлік" < "Қазақ тілі" < "Макроэкономика"
    assert result[result.index("KAZ101") - 1: result.index("KAZ101") + 2] == ["CS310", "KAZ101", "ECON201"]
    assert result[-1] == "UX201"                            # Latin "UI/UX" after Cyrillic


def test_descending_name_sort_reverses_order():
    asc = search(sort_by="name", lang="en")
    desc = search(sort_by="name", lang="en", sort_dir="desc")
    assert desc == list(reversed(asc))
