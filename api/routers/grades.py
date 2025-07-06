import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas, models
from ..database import get_db

# This router handles fetching course offerings and grade distributions.
router = APIRouter(
    prefix="/grades",
    tags=["Grades & Offerings"],
)

logger = logging.getLogger(__name__)

#  Helper Function for Grade Processing 

def _prepare_grade_report(offering: models.Offering, grades: List[models.Grade]) -> schemas.GradeReport:
    """Takes raw DB models and calculates percentages and sorts grades for the final response."""
    total_graded = sum(g.count for g in grades)

    # Use the number of currently registered students as the base for percentages if available.
    # Otherwise, fall back to the total number of grades submitted.
    percentage_base = offering.current_registered if offering.current_registered and offering.current_registered > 0 else total_graded
    
    processed_grades = []
    if percentage_base > 0:
        for grade in grades:
            processed_grades.append(schemas.Grade(
                grade_type=grade.grade_type,
                count=grade.count,
                percentage=round((grade.count / percentage_base) * 100, 1)
            ))
    else: # Avoid division by zero if no students are registered and no grades exist.
        processed_grades = [schemas.Grade(grade_type=g.grade_type, count=g.count, percentage=0.0) for g in grades]

    # Sort grades into a preferred, logical order.
    preferred_order = ['A*', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F', 'E', 'S', 'X', 'W']
    sort_map = {grade: i for i, grade in enumerate(preferred_order)}
    processed_grades.sort(key=lambda g: sort_map.get(g.grade_type, len(preferred_order)))

    return schemas.GradeReport(
        offering=offering,
        grades=processed_grades,
        total_graded_students=total_graded
    )


# API Endpoints

@router.get("/offering/details", response_model=schemas.Offering)
async def get_offering_details(
    course_code: str = Query(..., description="Full course code, e.g., MTH101A"),
    academic_year: str = Query(..., description="Academic year, e.g., 2024-2025"),
    semester: str = Query(..., description="Semester, e.g., Odd or Even"),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the detailed information for a single course offering."""
    offering = await crud.get_offering_by_details(db, course_code, academic_year, semester)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found.")
    return offering

@router.get("/offering/by_course/{course_code}", response_model=List[schemas.OfferingForCourseResult])
async def list_offerings_for_course(
    course_code: str = Path(..., description="Course code, e.g., CS201A"),
    db: AsyncSession = Depends(get_db)
):
    """Lists all available terms (offerings) for a given course."""
    offerings = await crud.get_terms_for_course(db=db, course_code=course_code)
    if not offerings:
        raise HTTPException(status_code=404, detail=f"No offerings found for course {course_code}")
    return offerings

@router.get("/offering/{offering_id}", response_model=schemas.GradeReport)
async def get_grade_distribution(
    offering_id: int = Path(..., gt=0, description="The unique ID of the course offering"),
    db: AsyncSession = Depends(get_db)
):
    """
    Gets the full grade distribution for a specific offering, including calculated percentages.
    """
    offering, grades = await crud.get_grades_for_offering(db=db, offering_id=offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail=f"Offering with ID {offering_id} not found.")

    
    return _prepare_grade_report(offering, grades)