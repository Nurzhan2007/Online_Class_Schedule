"""User roles (kept separate from the ORM so schemas can import it alone)."""

import enum


class Role(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"
