"""Admin course input validation (pure Pydantic)."""

import copy
from typing import get_args

import pytest
from pydantic import ValidationError

from app.schemas import Category, CategoryFilter, CourseIn, Day, DayFilter, RoomKind, SortField
from app.services.catalog import CATEGORIES, DAY_ORDER, ROOM_KINDS, SORT_FIELDS

VALID = {
    "code": "CS499",
    "category": "cs",
    "name": {"en": "Machine Learning", "ru": "Машинное обучение", "kk": "Машиналық оқыту"},
    "description": {"en": "Models.", "ru": "Модели.", "kk": "Модельдер."},
    "teacherId": 5,
    "credits": 5,
    "day": "tue",
    "start": "16:00",
    "end": "17:50",
    "room": {"kind": "lab", "no": "5"},
    "seats": 20,
}


def with_change(path, value):
    data = copy.deepcopy(VALID)
    target = data
    *parents, last = path.split(".")
    for key in parents:
        target = target[key]
    if value is ...:
        del target[last]
    else:
        target[last] = value
    return data


def test_valid_course():
    course = CourseIn.model_validate(VALID)
    assert course.name.kk == "Машиналық оқыту"


def test_code_is_normalised():
    assert CourseIn.model_validate(with_change("code", "  cs499 ")).code == "CS499"


def test_literals_match_the_catalogue_constants():
    assert get_args(Category) == CATEGORIES
    assert get_args(Day) == DAY_ORDER
    assert get_args(RoomKind) == ROOM_KINDS
    assert get_args(CategoryFilter) == ("all",) + CATEGORIES
    assert get_args(DayFilter) == ("all",) + DAY_ORDER
    assert get_args(SortField) == SORT_FIELDS


@pytest.mark.parametrize("path,value", [
    ("code", "C1"), ("code", "CS 101"), ("code", "CS10"), ("code", "COMPUTER101"),
    ("category", "art"), ("category", "CS"),
    ("day", "sat"), ("day", "Monday"),
    ("start", "9:00"), ("start", "24:00"), ("end", "17:60"), ("start", "noon"),
    ("start", "18:00"),                 # after end
    ("end", "16:00"),                   # equal to start
    ("credits", 0), ("credits", 11),
    ("seats", 0), ("seats", 501), ("seats", -5),
    ("teacherId", 0),
    ("room.kind", "hall"), ("room.no", ""), ("room.no", "1 2"), ("room.no", "x" * 11),
    ("name.kk", "   "), ("name.ru", ""), ("name.en", "x" * 201),
    ("description.kk", ""),
])
def test_invalid_values_are_rejected(path, value):
    with pytest.raises(ValidationError):
        CourseIn.model_validate(with_change(path, value))


@pytest.mark.parametrize("path", [
    "code", "category", "name", "description", "teacherId", "credits",
    "day", "start", "end", "room", "seats", "name.kk", "description.ru", "room.no",
])
def test_every_field_and_every_language_is_required(path):
    with pytest.raises(ValidationError):
        CourseIn.model_validate(with_change(path, ...))


@pytest.mark.parametrize("path", ["id", "seatsLeft", "instructor", "name.de", "room.floor"])
def test_unknown_fields_are_rejected(path):
    with pytest.raises(ValidationError):
        CourseIn.model_validate(with_change(path, 1))
