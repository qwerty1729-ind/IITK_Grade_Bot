from sqlalchemy import (
    Column, Integer, String, VARCHAR, ForeignKey, UniqueConstraint,
    BIGINT, BOOLEAN, TIMESTAMP, Float, Table
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

# Many-to-many association table for Offerings and Instructors
offering_instructor_association = Table(
    'offering_instructors', Base.metadata,
    Column('offering_id', Integer, ForeignKey('offerings.id', ondelete='CASCADE'), primary_key=True),
    Column('instructor_id', Integer, ForeignKey('instructors.id', ondelete='CASCADE'), primary_key=True)
)

class Course(Base):
    """Represents a course in the academic catalog."""
    __tablename__ = 'courses'
    code = Column(VARCHAR(20), primary_key=True, index=True)
    name = Column(VARCHAR(255), nullable=True, index=True)
    offerings = relationship("Offering", back_populates="course")

    def __repr__(self):
        return f"<Course(code='{self.code}', name='{self.name}')>"

class Instructor(Base):
    """Represents an instructor."""
    __tablename__ = 'instructors'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(VARCHAR(255), unique=True, index=True, nullable=False)
    offerings = relationship("Offering", secondary=offering_instructor_association, back_populates="instructors")

    def __repr__(self):
        return f"<Instructor(id={self.id}, name='{self.name}')>"

class Offering(Base):
    """Represents a specific instance of a course taught in a particular term."""
    __tablename__ = 'offerings'
    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(VARCHAR(20), ForeignKey('courses.code', ondelete='CASCADE'), nullable=False, index=True)
    academic_year = Column(VARCHAR(10), nullable=False, index=True)
    semester = Column(VARCHAR(10), nullable=False, index=True)
    total_registered = Column(Integer, nullable=True)
    current_registered = Column(Integer, nullable=True)
    total_drop = Column(Integer, nullable=True)
    accepted_drop = Column(Integer, nullable=True)
    plot_file_id = Column(VARCHAR(255), nullable=True, index=True)

    __table_args__ = (UniqueConstraint('course_code', 'academic_year', 'semester', name='uq_offering'),)
    
    course = relationship("Course", back_populates="offerings")
    instructors = relationship("Instructor", secondary=offering_instructor_association, back_populates="offerings")
    grades = relationship("Grade", back_populates="offering")

    def __repr__(self):
        return f"<Offering(id={self.id}, course='{self.course_code}', term='{self.semester} {self.academic_year}')>"

class Grade(Base):
    """Represents the count for a single grade type (e.g., 'A', 'B+') for an offering."""
    __tablename__ = 'grades'
    id = Column(Integer, primary_key=True, index=True)
    offering_id = Column(Integer, ForeignKey('offerings.id', ondelete='CASCADE'), nullable=False, index=True)
    grade_type = Column(VARCHAR(10), nullable=False)
    count = Column(Float, nullable=False) # Reverted to Float to match your live code
    __table_args__ = (UniqueConstraint('offering_id', 'grade_type', name='uq_grade'),)
    
    offering = relationship("Offering", back_populates="grades")

    def __repr__(self):
        return f"<Grade(offering_id={self.offering_id}, grade='{self.grade_type}', count={self.count})>"

class User(Base):
    """Represents a Telegram user interacting with the bot."""
    __tablename__ = 'users'
    telegram_user_id = Column(BIGINT, primary_key=True, index=True)
    first_name = Column(VARCHAR(255), nullable=True)
    last_name = Column(VARCHAR(255), nullable=True)
    username = Column(VARCHAR(255), nullable=True)
    is_subscribed = Column(BOOLEAN, default=True, nullable=False)
    subscribed_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_active_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    is_blocked = Column(BOOLEAN, default=False, nullable=False)
    block_reason = Column(VARCHAR(255), nullable=True)
    blocked_at = Column(TIMESTAMP(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User(id={self.telegram_user_id}, username='{self.username}')>"

class Feedback(Base):
    """Represents a piece of feedback submitted by a user."""
    __tablename__ = 'feedback'
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(BIGINT, ForeignKey('users.telegram_user_id'), nullable=False, index=True)
    feedback_type = Column(VARCHAR(50), nullable=False)
    message_text = Column(VARCHAR, nullable=False)
    status = Column(VARCHAR(20), default='new', nullable=False)
    submitted_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User")

    def __repr__(self):
        return f"<Feedback(id={self.id}, type='{self.feedback_type}', status='{self.status}')>"