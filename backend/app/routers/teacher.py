"""Teacher area: /api/teacher/... (teacher role only)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_teacher
from app.models import User
from app.schemas import CourseOut
from app.services import courses as course_service

router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.get("/courses", response_model=list[CourseOut])
def my_courses(teacher: User = Depends(require_teacher), db: Session = Depends(get_db)) -> list[CourseOut]:
    """Courses assigned to the logged-in teacher account."""
    return course_service.teacher_courses(db, teacher)
