import os
from typing import AsyncGenerator
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Database Configuration & Setup 

# Load environment variables from the .env file in the project root
load_dotenv()

# Get the database connection URL from the environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fail fast if the database URL isn't configured
    raise RuntimeError("DATABASE_URL environment variable is not set.")

# Create the core async database engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create a session factory to generate new database sessions
AsyncSessionFactory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Important for how FastAPI dependencies work
)

#  FastAPI Dependency 

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    A FastAPI dependency that provides a database session for a single request.
    
    This manages the session's lifecycle, ensuring it's always closed
    and that any transactions are rolled back if an error occurs.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise