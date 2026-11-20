"""Admin-only management: /api/admin/users and /api/admin/courses"""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import User
from app.roles import Role
from app.schemas import AdminUserCreate, CourseIn, CourseOut, UserOut
from app.services import auth as auth_service
from app.services import courses as course_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------- users

@router.get("/users", response_model=list[UserOut])
def list_users(role: Optional[Role] = None, db: Session = Depends(get_db)) -> list[User]:
    """All accounts; ``?role=teacher`` lists the teachers a course can be assigned to."""
    query = select(User).order_by(User.id)
    if role is not None:
        query = query.where(User.role == role)
    return list(db.scalars(query))


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: AdminUserCreate, db: Session = Depends(get_db)) -> User:
    """Create an account with any role, e.g. a teacher."""
    return auth_service.create_user(
        db,
        name=data.name,
        email=data.email,
        password=data.password,
        role=data.role,
        student_id=data.student_id,
    )


# ---------------------------------------------------------------- courses

@router.post("/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(data: CourseIn, db: Session = Depends(get_db)) -> CourseOut:
    return course_service.create_course(db, data)


@router.put("/courses/{course_id}", response_model=CourseOut)
def update_course(data: CourseIn, course_id: int = Path(gt=0), db: Session = Depends(get_db)) -> CourseOut:
    """Full update: send the complete course (all languages), like for creation."""
    return course_service.update_course(db, course_id, data)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int = Path(gt=0), db: Session = Depends(get_db)) -> Response:
    course_service.delete_course(db, course_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
