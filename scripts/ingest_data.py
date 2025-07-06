import asyncio
import os
import sys
import logging
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

#Setup Project Path
#Add the project root to the path so we can import the 'api' module
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))
from api import models

#Configuration
#Group all settings in one place for easy management
class Config:
    LOG_LEVEL = logging.INFO
    DOTENV_PATH = os.path.join(os.path.dirname(__file__), '..', '.env')
    DATABASE_URL = os.getenv("DATABASE_URL")
    CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'courses_with_fileids.csv')

    #Column names from the CSV file
    COURSE_CODE_COL = 'Course'
    COURSE_TITLE_COL = 'course title'
    INSTRUCTOR_COL = 'Instructor'
    YEAR_COL = 'Academic Year'
    SEMESTER_COL = 'Semester'
    FILE_ID_COL = 'telegram_file_id'
    
    #Grade columns used to find the range of all grade columns
    FIRST_GRADE_COL = 'D+'
    LAST_GRADE_COL = 'S^'

#Logging Setup
logging.basicConfig(level=Config.LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#Database Setup
load_dotenv(dotenv_path=Config.DOTENV_PATH)
if not Config.DATABASE_URL:
    logger.error("FATAL: DATABASE_URL environment variable not set.")
    exit(1)
engine = create_async_engine(Config.DATABASE_URL)
AsyncSessionFactory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


#Helper Functions for Data Cleaning

def parse_int(value: any, default: int = 0) -> int:
    """Safely converts a value from a DataFrame to an integer."""
    if pd.isna(value):
        return default
    try:

        #pd.to_numeric is great for handling various string/number formats
        numeric_val = pd.to_numeric(value, errors='coerce')
        return default if pd.isna(numeric_val) else int(numeric_val)
    except (ValueError, TypeError):
        return default


def normalize_name(name: any, default: str = "Unknown Instructor") -> str:
    """Cleans up an instructor's name."""
    if pd.isna(name) or not str(name).strip():
        return default
    return str(name).strip().title()


#Core Data Processing Functions

async def clear_existing_data(session: AsyncSession):
    """Clears out tables before ingesting new data."""
    logger.warning("Clearing existing grades, offering associations, and offerings...")
    await session.execute(delete(models.Grade))
    await session.execute(delete(models.offering_instructor_association))
    await session.execute(delete(models.Offering))
    logger.info("Dependent tables cleared.")


async def process_row(session: AsyncSession, row: pd.Series, grade_cols: list):
    """Processes a single row from the DataFrame to update the database."""
    
    # 1. Upsert Course
    course_code = str(row.get(Config.COURSE_CODE_COL, '')).strip().upper()

    if not course_code:
        logger.warning(f"Skipping row {row.name+2}: Course code is missing.")
        return False

    course_title_raw = row.get(Config.COURSE_TITLE_COL)

    course_title = str(course_title_raw).strip() if pd.notna(course_title_raw) else course_code
    
    course_stmt = pg_insert(models.Course).values(code=course_code, name=course_title)
    course_stmt = course_stmt.on_conflict_do_update(index_elements=['code'], set_={'name': course_stmt.excluded.name}).returning(models.Course)
    course = (await session.execute(course_stmt)).scalar_one()

    # 2. Upsert Instructors

    instructor_names_raw = row.get(Config.INSTRUCTOR_COL)

    raw_list = str(instructor_names_raw).split(',') if pd.notna(instructor_names_raw) else []
    instructor_names = sorted(list(set(normalize_name(name) for name in raw_list)))
    if not instructor_names:
        instructor_names.append("Unknown Instructor")
    
    instructors = []
    for name in instructor_names:

        instr_stmt = pg_insert(models.Instructor).values(name=name)
        instr_stmt = instr_stmt.on_conflict_do_nothing(index_elements=['name']).returning(models.Instructor)
        # We need to fetch in case the conflict was "do nothing"
        instructor = (await session.execute(instr_stmt)).scalar()
        if not instructor:
            instructor = (await session.execute(models.Instructor.__table__.select().where(models.Instructor.name == name))).scalar()
        instructors.append(instructor)

    # 3. Upsert Offering

    offering_data = {
        'course_code': course.code,
        'academic_year': str(row.get(Config.YEAR_COL, '0000-00')).strip(),
        'semester': str(row.get(Config.SEMESTER_COL, 'N/A')).strip(),
        'total_registered': parse_int(row.get('Total Registered')),
        'current_registered': parse_int(row.get('Current Registered')),
        'total_drop': parse_int(row.get('Total Drop')),
        'accepted_drop': parse_int(row.get('Accepted Drop')),
        'plot_file_id': str(row.get(Config.FILE_ID_COL)).strip() if pd.notna(row.get(Config.FILE_ID_COL)) else None
    }
    

    offering_stmt = pg_insert(models.Offering).values(**offering_data)
    update_cols = {k: v for k, v in offering_data.items() if k not in ['course_code', 'academic_year', 'semester']}
    offering_stmt = offering_stmt.on_conflict_do_update(index_elements=['course_code', 'academic_year', 'semester'], set_=update_cols).returning(models.Offering)
    offering = (await session.execute(offering_stmt)).scalar_one()
    

    # 4. Link Instructors to Offering and Insert Grades
    offering.instructors = instructors  # Update the relationship
    

    grades_to_insert = [
        {'offering_id': offering.id, 'grade_type': str(col).strip(), 'count': parse_int(row.get(col))}
        for col in grade_cols if parse_int(row.get(col)) > 0
    ]
    if grades_to_insert:
        await session.execute(pg_insert(models.Grade).values(grades_to_insert).on_conflict_do_nothing())
        
    return True


# --- Main Execution ---
async def main():
    """Main function to run the data ingestion process."""
    logger.info(f"Starting data ingestion from: {Config.CSV_PATH}")
    
    try:
        df = pd.read_csv(Config.CSV_PATH, na_values=['', 'NA', '#N/A', 'NaN', 'NULL'], keep_default_na=True)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')] # Drop unnamed columns
        logger.info(f"Loaded {len(df)} rows from CSV.")
    except FileNotFoundError:
        logger.error(f"FATAL: CSV file not found at {Config.CSV_PATH}.")
        return

    # Identify the grade columns dynamically
    try:
        cols = df.columns.tolist()
        start_idx = cols.index(Config.FIRST_GRADE_COL)
        end_idx = cols.index(Config.LAST_GRADE_COL)
        grade_cols = cols[start_idx : end_idx + 1]
        logger.info(f"Identified {len(grade_cols)} grade columns to process.")
    except ValueError:
        logger.error("FATAL: Could not find start/end grade columns in the CSV.")
        return

    successful_rows = 0
    async with AsyncSessionFactory() as session:
        async with session.begin(): # A single transaction for the whole process
            await clear_existing_data(session)
            
            for index, row in df.iterrows():
                if index % 100 == 0 and index > 0:
                    logger.info(f"Processing row {index}/{len(df)}...")
                
                success = await process_row(session, row, grade_cols)
                if success:
                    successful_rows += 1
    
    logger.info("--- Ingestion Complete ---")
    logger.info(f"Successfully processed and upserted {successful_rows}/{len(df)} rows.")

if __name__ == "__main__":
    asyncio.run(main())