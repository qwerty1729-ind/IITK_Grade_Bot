from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from .. import crud, schemas
from ..database import get_db

# This router handles all feedback submissions from users.
router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"],
)

@router.post("/", response_model=schemas.Feedback, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback_data: schemas.FeedbackCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts and stores a new feedback submission from a user.
    
    The request body should contain the user's ID, the feedback type,
    and the message text.
    """
    # The CRUD function handles all the database logic.
    # The foreign key constraint on the database will ensure the user exists.
    return await crud.create_feedback(db=db, feedback_data=feedback_data)