import logging
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload


from . import models, schemas

logger = logging.getLogger(__name__)

# Search Functions 

async def search_courses(db: AsyncSession, query: str) -> List[models.Course]:
    """Searches for courses by code or name (case-insensitive)."""
    search_term = f"%{query}%"
    stmt = select(models.Course).where(
        (models.Course.code.ilike(search_term)) |
        (models.Course.name.ilike(search_term))
    ).order_by(models.Course.code).limit(25)
    result = await db.execute(stmt)
    return result.scalars().all()

async def search_instructors(db: AsyncSession, query: str) -> List[models.Instructor]:
    """Searches for instructors by name, matching all words in the query."""
    query_words = [word.strip() for word in query.split() if word.strip()]
    if not query_words:
        return []

    conditions = [models.Instructor.name.ilike(f"%{word}%") for word in query_words]
    stmt = select(models.Instructor).where(and_(*conditions)).order_by(models.Instructor.name).limit(25)
    result = await db.execute(stmt)
    return result.scalars().all()

# Offering & Grade Functions

async def get_offering_by_details(db: AsyncSession, course_code: str, academic_year: str, semester: str) -> Optional[models.Offering]:
    """Gets a specific offering based on its course, year, and semester."""
    stmt = select(models.Offering).options(
        selectinload(models.Offering.instructors),
        selectinload(models.Offering.course)
    ).where(
        models.Offering.course_code == course_code,
        models.Offering.academic_year == academic_year,
        models.Offering.semester == semester
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_grades_for_offering(db: AsyncSession, offering_id: int) -> Tuple[Optional[models.Offering], List[models.Grade]]:
    """Gets an offering and its associated grade distribution."""
    # Fetch offering with its relationships eagerly loaded
    offering_stmt = select(models.Offering).options(
        selectinload(models.Offering.instructors),
        selectinload(models.Offering.course)
    ).where(models.Offering.id == offering_id)
    offering_result = await db.execute(offering_stmt)
    offering = offering_result.scalar_one_or_none()

    # Fetch grades separately
    grades_stmt = select(models.Grade).where(models.Grade.offering_id == offering_id)
    grades_result = await db.execute(grades_stmt)
    grades = grades_result.scalars().all()
    
    return offering, grades

# User Management Functions 

async def get_or_create_user(db: AsyncSession, user_data: schemas.UserCreate) -> models.User:
    """Gets a user by their ID, or creates them if they don't exist."""
    # .get() is the simplest way to fetch by primary key
    user = await db.get(models.User, user_data.telegram_user_id)
    if user:
        # Update user details on every interaction
        user.first_name = user_data.first_name
        user.username = user_data.username
        user.last_active_at = func.now()
    else:
        # Create a new user if not found
        user = models.User(**user_data.model_dump(), is_subscribed=True)
        db.add(user)
    
    await db.commit()
    await db.refresh(user)
    return user

async def get_user_by_identifier(db: AsyncSession, identifier: str) -> Optional[models.User]:
    """Finds a user by their Telegram ID or username."""
    if identifier.isdigit():
        return await db.get(models.User, int(identifier))
    
    stmt = select(models.User).where(models.User.username.ilike(identifier))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def update_user_block_status(db: AsyncSession, user: models.User, block_update: schemas.UserBlockUpdate) -> models.User:
    """Updates a user's blocked status."""
    user.is_blocked = block_update.is_blocked
    if block_update.is_blocked:
        user.block_reason = block_update.block_reason
        user.blocked_at = func.now()
    else:
        user.block_reason = None
        user.blocked_at = None
    
    await db.commit()
    await db.refresh(user)
    return user

# Feedback Functions 

async def create_feedback(db: AsyncSession, feedback_data: schemas.FeedbackCreate) -> models.Feedback:
    """Creates a new feedback entry in the database."""
    feedback = models.Feedback(**feedback_data.model_dump())
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback

async def get_all_feedback(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.Feedback]:
    """Retrieves a paginated list of all feedback entries."""
    stmt = select(models.Feedback).offset(skip).limit(limit).order_by(models.Feedback.submitted_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()