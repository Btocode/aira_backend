"""
Database connection and session management.
"""
from typing import AsyncGenerator

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.core.app_logging import db_logger


# Database engine and session
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Async database engine (for future async operations)
async_engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_recycle=300,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# SQLAlchemy Base
Base = declarative_base()

# Metadata for migrations
metadata = MetaData()


def get_db() -> Session:
    """Get database session dependency."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db_logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            db_logger.error(f"Async database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


class DatabaseManager:
    """Database management utilities."""

    @staticmethod
    def create_tables():
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=engine)
            db_logger.info("Database tables created successfully")
        except Exception as e:
            db_logger.error(f"Failed to create database tables: {e}")
            raise

    @staticmethod
    def drop_tables():
        """Drop all database tables."""
        try:
            Base.metadata.drop_all(bind=engine)
            db_logger.info("Database tables dropped successfully")
        except Exception as e:
            db_logger.error(f"Failed to drop database tables: {e}")
            raise

    @staticmethod
    def check_connection() -> bool:
        """Check database connection."""
        try:
            with engine.connect() as connection:
                connection.execute("SELECT 1")
            db_logger.info("Database connection successful")
            return True
        except Exception as e:
            db_logger.error(f"Database connection failed: {e}")
            return False

    @staticmethod
    async def check_async_connection() -> bool:
        """Check async database connection."""
        try:
            async with async_engine.connect() as connection:
                await connection.execute("SELECT 1")
            db_logger.info("Async database connection successful")
            return True
        except Exception as e:
            db_logger.error(f"Async database connection failed: {e}")
            return False


# Database initialization
def init_db():
    """Initialize database."""
    db_logger.info("Initializing database...")

    # Check connection
    if not DatabaseManager.check_connection():
        raise Exception("Could not connect to database")

    # Create tables
    DatabaseManager.create_tables()

    db_logger.info("Database initialized successfully")