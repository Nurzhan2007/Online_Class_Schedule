"""Course catalogue: /api/courses (any logged-in user, like the frontend)."""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.schemas import CategoryFilter, CourseMeta, CourseOut, DayFilter, Lang, SortDir, SortField
from app.services import courses as course_service
from app.services.catalog import CourseFilters, filter_and_sort

router = APIRouter(prefix="/courses", tags=["courses"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CourseOut])
def list_courses(
    term: str = Query("", max_length=100, description="Searches code, instructor and en/ru/kk names"),
    category: CategoryFilter = "all",
    day: DayFilter = "all",
    instructor: Optional[str] = Query(None, max_length=100),
    teacher_id: Optional[int] = Query(None, alias="teacherId", gt=0),
    credits: Optional[int] = Query(None, ge=1, le=10),
    only_available: bool = Query(False, alias="onlyAvailable"),
    sort_by: SortField = Query("code", alias="sortBy"),
    sort_dir: SortDir = Query("asc", alias="sortDir"),
    lang: Lang = Query("en", description="Language used when sorting by name"),
    db: Session = Depends(get_db),
) -> list[CourseOut]:
    filters = CourseFilters(
        term=term,
        category=category,
        day=day,
        instructor=None if instructor in (None, "", "all") else instructor,
        teacher_id=teacher_id,
        credits=credits,
        only_available=only_available,
        sort_by=sort_by,
        sort_dir=sort_dir,
        lang=lang,
    )
    return filter_and_sort(course_service.list_courses(db), filters)


@router.get("/meta", response_model=CourseMeta)
def catalogue_meta(db: Session = Depends(get_db)) -> CourseMeta:
    """Options for the filter drop-downs (categories, instructors, credits, days)."""
    return course_service.catalogue_meta(course_service.list_courses(db))


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: int = Path(gt=0), db: Session = Depends(get_db)) -> CourseOut:
    return course_service.course_out(db, course_service.get_course(db, course_id))
