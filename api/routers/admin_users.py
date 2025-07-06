import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..database import get_db
# from ..security import get_admin_api_key # TODO: Implement and enable API key security

# This router contains endpoints for administrative actions on users.
# All endpoints here should be protected by an admin-only API key.
router = APIRouter(
    prefix="/admin/users",
    tags=["Admin - User Management"],
    # dependencies=[Depends(get_admin_api_key)], # Uncomment once security is implemented
)

logger = logging.getLogger(__name__)

@router.get("/{user_identifier}", response_model=schemas.User)
async def get_user_by_admin(
    user_identifier: str, 
    db: AsyncSession = Depends(get_db)
):
    """Fetches a single user's complete profile by their Telegram ID or username."""
    db_user = await crud.get_user_by_identifier(db, identifier=user_identifier)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return db_user

@router.put("/{user_identifier}/block", response_model=schemas.User)
async def block_or_unblock_user(
    user_identifier: str,
    block_update: schemas.UserBlockUpdate, # Request body with block status
    db: AsyncSession = Depends(get_db)
):
    """Blocks or unblocks a user and records the reason if applicable."""
    logger.info(f"Admin action: Updating block status for '{user_identifier}' to {block_update.is_blocked}.")
    
    db_user = await crud.get_user_by_identifier(db, identifier=user_identifier)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    
    # This CRUD function now takes the user object and the schema directly
    updated_user = await crud.update_user_block_status(db, user=db_user, block_update=block_update)
    
    action = "blocked" if updated_user.is_blocked else "unblocked"
    logger.info(f"Admin action successful: User {updated_user.telegram_user_id} has been {action}.")
    
    return updated_user