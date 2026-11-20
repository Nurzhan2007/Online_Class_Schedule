"""Database models.

Datetimes are stored as naive UTC (SQLite has no time-zone type);
always create them with ``utcnow_naive()``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.roles import Role
from app.services.catalog import CATEGORIES, DAY_ORDER, ROOM_KINDS


def _sql_in(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # University ID. Required for students; optional for teachers/admins.
    # NULLs do not collide with the UNIQUE constraint in SQLite.
    student_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)  # stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255))  # never the plain password
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="user_role",
            native_enum=False,
            create_constraint=True,  # CHECK (role IN ('student', 'teacher', 'admin'))
            values_callable=lambda roles: [r.value for r in roles],
            length=20,
        ),
        default=Role.STUDENT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    # Courses taught by this user (only teachers have any).
    # passive_deletes="all": the ORM never silently detaches courses when a
    # user is deleted - the database's ON DELETE RESTRICT refuses instead.
    courses: Mapped[list[Course]] = relationship(
        back_populates="teacher", passive_deletes="all", order_by="Course.code"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r}, role={self.role.value!r})"


class LoginAttempt(Base):
    """Consecutive failed logins per email (also for emails without an account)."""

    __tablename__ = "login_attempts"

    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class Course(Base):
    """A course with one fixed weekly meeting, taught by one teacher account."""

    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint("length(code) BETWEEN 5 AND 10", name="ck_courses_code_length"),
        CheckConstraint(_sql_in("category", CATEGORIES), name="ck_courses_category"),
        CheckConstraint(
            "length(trim(name_en)) > 0 AND length(trim(name_ru)) > 0 AND length(trim(name_kk)) > 0",
            name="ck_courses_names_present",
        ),
        CheckConstraint(
            "length(trim(description_en)) > 0 AND length(trim(description_ru)) > 0 "
            "AND length(trim(description_kk)) > 0",
            name="ck_courses_descriptions_present",
        ),
        CheckConstraint("credits BETWEEN 1 AND 10", name="ck_courses_credits"),
        CheckConstraint(_sql_in("day", DAY_ORDER), name="ck_courses_day"),
        CheckConstraint(
            "start_time GLOB '[0-2][0-9]:[0-5][0-9]' AND end_time GLOB '[0-2][0-9]:[0-5][0-9]'",
            name="ck_courses_time_format",
        ),
        CheckConstraint("start_time < end_time", name="ck_courses_time_order"),
        CheckConstraint(_sql_in("room_kind", ROOM_KINDS), name="ck_courses_room_kind"),
        CheckConstraint("length(room_no) BETWEEN 1 AND 10", name="ck_courses_room_no"),
        CheckConstraint("seats BETWEEN 1 AND 500", name="ck_courses_seats"),
        # Never reuse the id of a deleted course (ids are referenced by the frontend).
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(20))

    name_en: Mapped[str] = mapped_column(String(200))
    name_ru: Mapped[str] = mapped_column(String(200))
    name_kk: Mapped[str] = mapped_column(String(200))
    description_en: Mapped[str] = mapped_column(Text)
    description_ru: Mapped[str] = mapped_column(Text)
    description_kk: Mapped[str] = mapped_column(Text)

    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    credits: Mapped[int] = mapped_column(Integer)
    day: Mapped[str] = mapped_column(String(3))
    start_time: Mapped[str] = mapped_column(String(5))  # "HH:MM", as in the frontend
    end_time: Mapped[str] = mapped_column(String(5))
    room_kind: Mapped[str] = mapped_column(String(10))
    room_no: Mapped[str] = mapped_column(String(10))
    seats: Mapped[int] = mapped_column(Integer)          # capacity

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    teacher: Mapped[User] = relationship(back_populates="courses")

    def __repr__(self) -> str:
        return f"Course(id={self.id}, code={self.code!r})"


class Registration(Base):
    """A student taking a course. Only the table exists in Phase 3 (used for
    seat counting); registering and unregistering arrive in Phase 4."""

    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_registrations_user_course"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # RESTRICT: a course with registered students cannot be deleted.
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class RevokedToken(Base):
    """JWTs invalidated by logout. Rows are deleted once the token would have expired anyway."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
