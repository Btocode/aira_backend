"""
User database queries.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.security_utils import SecurityUtils
from app.db.models import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.app_logging import db_logger


async def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Get user by ID."""
    try:
        return db.query(User).filter(User.id == UUID(user_id)).first()
    except Exception as e:
        db_logger.error(f"Error getting user by ID {user_id}: {e}")
        return None


async def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    try:
        return db.query(User).filter(User.email == email).first()
    except Exception as e:
        db_logger.error(f"Error getting user by email {email}: {e}")
        return None


async def create_user(db: Session, user_create: UserCreate) -> User:
    """Create a new user."""
    try:
        # Hash password
        hashed_password = SecurityUtils.get_password_hash(user_create.password)

        # Create user instance
        db_user = User(
            email=user_create.email,
            hashed_password=hashed_password,
            full_name=user_create.full_name,
            research_interests=user_create.research_interests,
            preferred_ai_model=user_create.preferred_ai_model,
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        db_logger.info(f"User created successfully: {db_user.id}")
        return db_user

    except Exception as e:
        db_logger.error(f"Error creating user {user_create.email}: {e}")
        db.rollback()
        raise


async def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password."""
    try:
        user = await get_user_by_email(db, email)
        if not user:
            return None

        if not SecurityUtils.verify_password(password, user.hashed_password):
            return None

        return user

    except Exception as e:
        db_logger.error(f"Error authenticating user {email}: {e}")
        return None


async def update_user(db: Session, user_id: str, user_update: UserUpdate) -> Optional[User]:
    """Update user information."""
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            return None

        # Update fields
        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        db_logger.info(f"User updated successfully: {user.id}")
        return user

    except Exception as e:
        db_logger.error(f"Error updating user {user_id}: {e}")
        db.rollback()
        raise


async def update_user_last_login(db: Session, user_id: str) -> Optional[User]:
    """Update user's last login timestamp."""
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            return None

        user.last_login_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        return user

    except Exception as e:
        db_logger.error(f"Error updating last login for user {user_id}: {e}")
        db.rollback()
        return None


async def verify_user_email(db: Session, user_id: str) -> Optional[User]:
    """Verify user's email address."""
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            return None

        user.is_verified = True
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        db_logger.info(f"Email verified for user: {user.id}")
        return user

    except Exception as e:
        db_logger.error(f"Error verifying email for user {user_id}: {e}")
        db.rollback()
        return None


async def update_user_password(db: Session, user_id: str, new_password: str) -> Optional[User]:
    """Update user's password."""
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            return None

        # Hash new password
        hashed_password = SecurityUtils.get_password_hash(new_password)
        user.hashed_password = hashed_password
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        db_logger.info(f"Password updated for user: {user.id}")
        return user

    except Exception as e:
        db_logger.error(f"Error updating password for user {user_id}: {e}")
        db.rollback()
        return None


async def deactivate_user(db: Session, user_id: str) -> Optional[User]:
    """Deactivate user account."""
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            return None

        user.is_active = False
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        db_logger.info(f"User deactivated: {user.id}")
        return user

    except Exception as e:
        db_logger.error(f"Error deactivating user {user_id}: {e}")
        db.rollback()
        return None


async def get_user_stats(db: Session, user_id: str) -> dict:
    """Get user statistics."""
    try:
        from app.db.models import UserPaper, KnowledgeEntry

        user = await get_user_by_id(db, user_id)
        if not user:
            return {}

        # Count papers
        papers_count = db.query(UserPaper).filter(UserPaper.user_id == user.id).count()

        # Count knowledge entries
        knowledge_count = db.query(KnowledgeEntry).filter(KnowledgeEntry.user_id == user.id).count()

        # Sum reading time
        total_time = db.query(UserPaper.time_spent).filter(UserPaper.user_id == user.id).all()
        total_reading_time = sum(time[0] or 0 for time in total_time)

        return {
            "papers_count": papers_count,
            "knowledge_entries_count": knowledge_count,
            "total_reading_time": total_reading_time
        }

    except Exception as e:
        db_logger.error(f"Error getting user stats for {user_id}: {e}")
        return {}