"""The logged-in student's own enrollments: /api/me/registrations

Students only. The student is always taken from the JWT - there is no
user id anywhere in these URLs or request bodies, so nobody can create,
see or cancel another student's enrollment.
"""

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_student
from app.models import User
from app.schemas import EnrollmentCheck, EnrollmentRequest, MyCourseOut, MyRegistrationsOut
from app.services import registrations as registration_service

router = APIRouter(prefix="/me/registrations", tags=["my registrations"])


@router.get("", response_model=MyRegistrationsOut)
def my_registrations(
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> MyRegistrationsOut:
    """My courses (catalogue order), their count and my total credits."""
    return registration_service.list_my_registrations(db, student.id)


@router.post("", response_model=MyCourseOut, status_code=status.HTTP_201_CREATED)
def enroll(
    data: EnrollmentRequest,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> MyCourseOut:
    """Enroll in a course at its fixed schedule.

    409 err.alreadyRegistered / err.noSeats / err.conflict {name, code, courseId},
    404 err.notFound.
    """
    return registration_service.enroll(db, student.id, data.courseId)


@router.post("/check", response_model=EnrollmentCheck)
def check_enrollment(
    data: EnrollmentRequest,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> EnrollmentCheck:
    """Dry run of POST /api/me/registrations: same errors, nothing is saved."""
    return registration_service.check_enrollment(db, student.id, data.courseId)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel(
    course_id: int = Path(gt=0),
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> Response:
    """Cancel my enrollment. 204 also if I was not registered; 404 if the course does not exist."""
    registration_service.cancel_enrollment(db, student.id, course_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
