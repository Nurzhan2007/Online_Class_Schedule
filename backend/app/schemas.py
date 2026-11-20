"""Request and response models.

JSON field names follow the existing frontend (``studentId``, not
``student_id``), so the frontend can use the responses without mapping.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.roles import Role

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STUDENT_ID_RE = re.compile(r"^[A-Z0-9-]{3,20}$")

PASSWORD_MIN = 6    # same as minlength="6" on the frontend registration form
PASSWORD_MAX = 128  # bounds the work an attacker can force on the server


def normalize_email(value: str) -> str:
    return value.strip().lower()


def _check_email(value: str) -> str:
    email = normalize_email(value)
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise ValueError("invalid email address")
    return email


def _check_name(value: str) -> str:
    name = " ".join(value.split())  # trim and collapse inner whitespace
    if not 1 <= len(name) <= 100:
        raise ValueError("name must be 1-100 characters")
    return name


def _check_student_id(value: str) -> str:
    student_id = value.strip().upper()
    if not STUDENT_ID_RE.match(student_id):
        raise ValueError("student ID must be 3-20 letters, digits or '-'")
    return student_id


def _check_optional_student_id(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    return _check_student_id(value)


Email = Annotated[str, AfterValidator(_check_email)]
Name = Annotated[str, AfterValidator(_check_name)]
StudentId = Annotated[str, AfterValidator(_check_student_id)]
OptionalStudentId = Annotated[Optional[str], AfterValidator(_check_optional_student_id)]
NewPassword = Annotated[str, Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)]


class _StrictInput(BaseModel):
    # Unknown fields are an error: e.g. {"role": "admin"} in a registration
    # request is rejected instead of being silently ignored.
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(_StrictInput):
    """Public self-registration. Always creates a *student*."""

    name: Name
    student_id: StudentId = Field(alias="studentId")
    email: Email
    password: NewPassword


class LoginRequest(_StrictInput):
    email: Email
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


class AdminUserCreate(_StrictInput):
    """Admin-only: create an account with any role (e.g. a teacher)."""

    name: Name
    email: Email
    password: NewPassword
    role: Role
    student_id: OptionalStudentId = Field(default=None, alias="studentId")

    @model_validator(mode="after")
    def _students_need_an_id(self) -> "AdminUserCreate":
        if self.role is Role.STUDENT and self.student_id is None:
            raise ValueError("studentId is required for students")
        return self


class UserOut(BaseModel):
    """Public user data - the same shape the frontend kept in its session."""

    # populate_by_name: read ``student_id`` from ORM objects, and also accept
    # ``studentId`` - FastAPI re-validates nested models after dumping them by alias.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    student_id: Optional[str] = Field(alias="studentId")
    email: str
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut


# ====================================================================== courses
#
# Field names are camelCase on purpose (teacherId, seatsLeft): they are the
# exact JSON keys the frontend uses, and no aliases means no alias pitfalls.

COURSE_CODE_RE = r"^[A-Z]{2,6}[0-9]{3,4}$"   # CS101, MATH202, INFT3107
TIME_RE = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"  # 24-hour HH:MM
ROOM_NO_RE = r"^[A-Za-z0-9-]{1,10}$"

Category = Literal["cs", "math", "languages", "physics", "economics", "design"]
Day = Literal["mon", "tue", "wed", "thu", "fri"]
RoomKind = Literal["room", "lab"]
Lang = Literal["en", "ru", "kk"]
SortField = Literal["code", "name", "instructor", "credits", "seats", "day"]
SortDir = Literal["asc", "desc"]
# Query-string filters also accept "all", exactly like the frontend's <select> values.
CategoryFilter = Literal["all", "cs", "math", "languages", "physics", "economics", "design"]
DayFilter = Literal["all", "mon", "tue", "wed", "thu", "fri"]


def _text_checker(max_length: int):
    def check(value: str) -> str:
        text = value.strip()
        if not 1 <= len(text) <= max_length:
            raise ValueError(f"must be 1-{max_length} characters")
        return text
    return check


def _check_course_code(value: str) -> str:
    code = value.strip().upper()
    if not re.match(COURSE_CODE_RE, code):
        raise ValueError("course code must look like CS101 or INFT3107")
    return code


ShortText = Annotated[str, AfterValidator(_text_checker(200))]
LongText = Annotated[str, AfterValidator(_text_checker(2000))]
CourseCode = Annotated[str, AfterValidator(_check_course_code)]
TimeOfDay = Annotated[str, Field(pattern=TIME_RE)]


class LocalizedNameIn(_StrictInput):
    en: ShortText
    ru: ShortText
    kk: ShortText


class LocalizedDescriptionIn(_StrictInput):
    en: LongText
    ru: LongText
    kk: LongText


class RoomIn(_StrictInput):
    kind: RoomKind
    no: Annotated[str, Field(pattern=ROOM_NO_RE)]


class CourseIn(_StrictInput):
    """Admin create / full update of a course. All three languages are required."""

    code: CourseCode
    category: Category
    name: LocalizedNameIn
    description: LocalizedDescriptionIn
    teacherId: int = Field(gt=0)
    credits: int = Field(ge=1, le=10)
    day: Day
    start: TimeOfDay
    end: TimeOfDay
    room: RoomIn
    seats: int = Field(ge=1, le=500)

    @model_validator(mode="after")
    def _start_before_end(self) -> "CourseIn":
        if self.start >= self.end:  # zero-padded HH:MM compares correctly as text
            raise ValueError("start must be earlier than end")
        return self


class LocalizedText(BaseModel):
    en: str
    ru: str
    kk: str


class Room(BaseModel):
    kind: str
    no: str


class CourseOut(BaseModel):
    """The same object shape as a course in the original js/api.js, plus
    ``teacherId`` (link to the teacher account) and ``seatsLeft``."""

    id: int
    code: str
    category: str
    name: LocalizedText
    description: LocalizedText
    instructor: str
    teacherId: int
    credits: int
    day: str
    start: str
    end: str
    room: Room
    seats: int
    seatsLeft: int


class EnrollmentRequest(_StrictInput):
    """Only the course is chosen. Day, time, room and instructor are the
    course's fixed university schedule and cannot be sent (extra fields -> 422).
    The student is always the logged-in user, never a field of the request."""

    courseId: int = Field(gt=0)


class MyCourseOut(CourseOut):
    registeredAt: datetime  # UTC


class MyRegistrationsOut(BaseModel):
    """What the frontend derives from getRegisteredIds / myCourses / getTotalCredits."""

    courses: list[MyCourseOut]
    count: int
    totalCredits: int


class EnrollmentCheck(BaseModel):
    ok: bool = True
    seatsLeft: int


class CourseMeta(BaseModel):
    """Options for the catalogue filters (CourseAPI.getCategories/Instructors/CreditOptions)."""

    categories: list[str]
    instructors: list[str]
    credits: list[int]
    days: list[str]
