from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from .. import crud, schemas
from ..database import get_db
from ..utils.limiter import limiter

# This router handles all search-related endpoints.
router = APIRouter(
    prefix="/search",
    tags=["Search"],
)

@router.get("/course", response_model=List[schemas.Course])
@limiter.limit("15/minute")
async def search_for_courses(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query for course code or name."),
    db: AsyncSession = Depends(get_db),
):
    """
    Searches for courses by their code or title based on a query string.
    """
    courses = await crud.search_courses(db, query=q)
    if not courses:
        raise HTTPException(status_code=404, detail="No courses found matching the query.")
    
    # FastAPI automatically converts the list of database objects to a list of Pydantic schemas.
    return courses

@router.get("/prof", response_model=List[schemas.Instructor])
@limiter.limit("15/minute")
async def search_for_instructors(
    request: Request,
    q: str = Query(..., min_length=3, description="Search query for an instructor's name."),
    db: AsyncSession = Depends(get_db),
):
    """
    Searches for instructors by their name.
    """
    instructors = await crud.search_instructors(db, query=q)
    if not instructors:
        raise HTTPException(status_code=404, detail="No instructors found matching the query.")

    return instructors