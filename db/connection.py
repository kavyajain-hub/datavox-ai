from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from functools import lru_cache
from config.settings import get_settings


@lru_cache()
def get_engine() -> Engine:
    """Create and cache SQLAlchemy Engine, supporting both SQLite and PostgreSQL."""
    settings = get_settings()
    db_url = settings.database_url

    if db_url.startswith("sqlite"):
        return create_engine(db_url, connect_args={"check_same_thread": False})

    # If postgresql:// is provided without explicit driver, use psycopg 3 driver
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return create_engine(db_url)
