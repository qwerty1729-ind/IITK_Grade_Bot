from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

# Base Config 
# By creating a base model with this config, we don't have to repeat it in every schema.
class OrmBaseModel(BaseModel):
    class Config:
        from_attributes = True

#  Instructor Schemas 
class Instructor(OrmBaseModel):
    id: int
    name: str

# Course Schemas 
class Course(OrmBaseModel):
    code: str
    name: Optional[str] = None

# Offering Schemas
# These describe a specific instance of a course in a given term.

class Offering(OrmBaseModel):
    """Detailed schema for a single course offering."""
    id: int
    academic_year: str
    semester: str
    course: Course
    instructors: List[Instructor] = []
    plot_file_id: Optional[str] = None

class OfferingForCourseResult(OrmBaseModel):
    """A simplified offering view for listing all terms of a single course."""
    academic_year: str
    semester: str
    instructors: List[Instructor] = []

# Grade Schemas
class Grade(OrmBaseModel):
    grade_type: str
    count: int

class GradeReport(OrmBaseModel):
    """The full grade report for a specific offering."""
    offering: Offering
    grades: List[Grade] = []
    total_graded_students: int

# User Schemas
class UserBase(OrmBaseModel):
    """Base user schema with fields common to creation and reading."""
    telegram_user_id: int
    first_name: Optional[str] = None
    username: Optional[str] = None

class UserCreate(UserBase):
    """Schema used when creating a new user. Currently same as base."""
    pass

class User(UserBase):
    """Detailed schema for reading user data, e.g., for an admin panel."""
    is_subscribed: bool
    is_blocked: bool
    subscribed_at: datetime.datetime
    last_active_at: datetime.datetime

class UserBlockUpdate(BaseModel):
    """Schema for the request body when an admin blocks or unblocks a user."""
    is_blocked: bool
    block_reason: Optional[str] = None

# Feedback Schemas
class FeedbackCreate(BaseModel):
    feedback_type: str = Field(..., examples=["bug", "suggestion"])
    message_text: str
    telegram_user_id: int

class Feedback(FeedbackCreate, OrmBaseModel):
    """Schema for reading feedback entries from the database."""
    id: int
    submitted_at: datetime.datetime
    status: str