"""Course catalogue rules: search, filters, sorting, time overlaps.

Pure functions (no database, no FastAPI). They reproduce the behaviour of
``CourseAPI.search`` in the original frontend (js/api.js):

* search term matches code, instructor and the en/ru/kk names, case-insensitive;
* "all" (or nothing) means "no filter";
* sort by code / name / instructor / credits / seats / day, ascending or
  descending; ties are always broken by course code, ascending;
* course codes compare "naturally" (CS205 < CS1000), like
  ``localeCompare(..., {numeric: true})``.

Filtering is done in Python rather than SQL on purpose: SQLite's LOWER()
and LIKE are case-insensitive only for ASCII, so Cyrillic/Kazakh search
would silently fail in SQL. The catalogue is small (tens of courses).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional, Sequence, TypeVar, Union

DAY_ORDER = ("mon", "tue", "wed", "thu", "fri")
# Same order as the categories first appear in the original data / translations.
CATEGORIES = ("cs", "math", "languages", "physics", "economics", "design")
LANGUAGES = ("en", "ru", "kk")
ROOM_KINDS = ("room", "lab")
SORT_FIELDS = ("code", "name", "instructor", "credits", "seats", "day")

ALPHABETS = {
    "ru": "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    "kk": "аәбвгғдеёжзийкқлмнңоөпрстуұүфхһцчшщъыіьэюя",
}


# ------------------------------------------------------------------ time

def time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def overlaps(day_a: str, start_a: str, end_a: str,
             day_b: str, start_b: str, end_b: str) -> bool:
    """Same weekday and the time ranges intersect (touching ends do not count)."""
    return (
        day_a == day_b
        and time_to_minutes(start_a) < time_to_minutes(end_b)
        and time_to_minutes(start_b) < time_to_minutes(end_a)
    )


# ------------------------------------------------------------------ sort keys

def natural_code_key(code: str) -> tuple:
    """CS205 < CS1000 < MATH101 (digits compared as numbers, letters case-insensitively)."""
    parts = re.split(r"(\d+)", code)
    return tuple(int(part) if index % 2 else part.casefold()
                 for index, part in enumerate(parts))


def collation_key(text: str, lang: str) -> tuple:
    """Alphabetical sort key for en / ru / kk.

    Plain code-point order puts Kazakh letters (ә, ғ, қ, ң, ө, ұ, ү, һ, і)
    after "я"; this key places them where they belong in the alphabet.
    Cyrillic letters come before Latin ones for ru/kk, as in their locales.
    """
    alphabet = ALPHABETS.get(lang, "")
    key = []
    for char in unicodedata.normalize("NFC", text.casefold()):
        if char.isspace() or not char.isalnum():
            key.append((0, ord(char)))
        elif char.isdigit():
            key.append((1, ord(char)))
        elif char in alphabet:
            key.append((2, alphabet.index(char)))
        else:
            key.append((3, ord(char)))
    return tuple(key)


# ------------------------------------------------------------------ filtering

# Works on any objects with the attributes of schemas.CourseOut:
# id, code, category, name.en/.ru/.kk, instructor, teacherId, credits, day, start, seatsLeft.
CourseT = TypeVar("CourseT")


@dataclass(frozen=True)
class CourseFilters:
    term: str = ""
    category: Optional[str] = None
    day: Optional[str] = None
    instructor: Optional[str] = None
    teacher_id: Optional[int] = None
    credits: Optional[Union[int, str]] = None  # "all" = no filter
    only_available: bool = False
    sort_by: str = "code"
    sort_dir: str = "asc"
    lang: str = "en"


def _active(value):
    return value is not None and value != "all"


def _matches(course: Any, f: CourseFilters, term: str) -> bool:
    if term:
        haystack = " ".join(
            [course.code, course.instructor, course.name.en, course.name.ru, course.name.kk]
        ).lower()
        if term not in haystack:
            return False
    if _active(f.category) and course.category != f.category:
        return False
    if _active(f.day) and course.day != f.day:
        return False
    if _active(f.instructor) and course.instructor != f.instructor:
        return False
    if f.teacher_id is not None and getattr(course, "teacherId", None) != f.teacher_id:
        return False
    if f.credits is not None and f.credits != "all" and course.credits != int(f.credits):
        return False
    if f.only_available and course.seatsLeft <= 0:
        return False
    return True


def _sort_key(course: Any, f: CourseFilters):
    lang = f.lang if f.lang in LANGUAGES else "en"
    if f.sort_by == "name":
        return collation_key(getattr(course.name, lang) or course.name.en, lang)
    if f.sort_by == "instructor":
        return collation_key(course.instructor, "en")
    if f.sort_by == "credits":
        return course.credits
    if f.sort_by == "seats":
        return course.seatsLeft
    if f.sort_by == "day":
        return (DAY_ORDER.index(course.day), time_to_minutes(course.start))
    return natural_code_key(course.code)


def _code_key(course: Any) -> tuple:
    return natural_code_key(course.code)


def filter_and_sort(courses: Sequence[CourseT], filters: CourseFilters) -> list[CourseT]:
    term = (filters.term or "").strip().lower()
    result = [c for c in courses if _matches(c, filters, term)]
    # 1) tie-breaker first: code ascending; 2) then the stable main sort.
    result.sort(key=_code_key)
    if filters.sort_by != "code":
        result.sort(key=lambda c: _sort_key(c, filters), reverse=filters.sort_dir == "desc")
    elif filters.sort_dir == "desc":
        result.reverse()
    return result
