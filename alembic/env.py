import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

#  Path Setup 
# Add the project's root directory to the Python path.
# This is crucial so that Alembic can find your `api.models` module.
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

#  Model & Config Setup 
# Import your models' Base so Alembic knows about your tables.
from api.models import Base

# Load environment variables from the .env file
load_dotenv()

# This is the Alembic Config object, which provides
# access to the values within the .ini file.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from the environment variable.
# We replace the async driver 'asyncpg' with the sync driver 'psycopg2'
# because Alembic's migration runner is synchronous.
db_url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg", "postgresql")
if not db_url:
    raise ValueError("DATABASE_URL environment variable is not set.")
config.set_main_option("sqlalchemy.url", db_url)

# Set target metadata for 'autogenerate' support.
target_metadata = Base.metadata

#  Migration Functions 

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    This creates SQL scripts without connecting to a database.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    This connects to the database and applies the migrations.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()