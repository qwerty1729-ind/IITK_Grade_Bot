from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas, models
from ..database import get_db

# This router handles all user-related operations like subscribing and unsubscribing.
router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

@router.post("/subscribe", response_model=schemas.User)
async def subscribe_or_update_user(
    user_data: schemas.UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new user or updates an existing user's details.
    This single endpoint handles both new and returning users seamlessly.
    """
    # We call our single, clean CRUD function that handles all the logic.
    user = await crud.get_or_create_user(db=db, user_data=user_data)
    return user

@router.post("/{telegram_user_id}/unsubscribe", response_model=schemas.User)
async def unsubscribe_user(
    telegram_user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Marks a specific user as unsubscribed in the database."""
    # Fetch the user by their primary key.
    user = await db.get(models.User, telegram_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update the user's status directly.
    user.is_subscribed = False
    await db.commit()
    await db.refresh(user)
    
    return user