"""
Authentication and security utilities.
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security_utils import SecurityUtils
from app.db.database import get_db
from app.db.queries.user_queries import get_user_by_id


# JWT Security
security = HTTPBearer()


# Dependency functions
async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Get current authenticated user ID from JWT token."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user_id = SecurityUtils.verify_token(credentials.credentials)
        if user_id is None:
            raise credentials_exception

        return user_id

    except JWTError:
        raise credentials_exception


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Get current authenticated user from database."""

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


async def get_current_active_user(
    current_user = Depends(get_current_user)
):
    """Get current active user (must be active)."""

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return current_user


# Optional authentication (for public endpoints that benefit from user context)
async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Get current user if authenticated, None otherwise."""

    if not credentials:
        return None

    try:
        user_id = SecurityUtils.verify_token(credentials.credentials)
        if user_id is None:
            return None

        user = await get_user_by_id(db, user_id)
        return user if user and user.is_active else None

    except (JWTError, HTTPException):
        return None


# Permission decorators
def require_subscription_tier(required_tier: str):
    """Decorator to require specific subscription tier."""

    def decorator(current_user = Depends(get_current_active_user)):
        tier_levels = {
            "free": 0,
            "researcher": 1,
            "institution": 2
        }

        user_level = tier_levels.get(current_user.subscription_tier, 0)
        required_level = tier_levels.get(required_tier, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_tier} subscription or higher"
            )

        return current_user

    return decorator


# Rate limiting decorator
def rate_limit(requests_per_minute: int = None):
    """Decorator for rate limiting endpoints."""

    def decorator(func):
        # Implementation would use Redis to track request counts
        # This is a placeholder for the actual rate limiting logic
        return func

    return decorator


# API Key authentication (for webhook endpoints)
async def verify_api_key(api_key: str = Depends(HTTPBearer())):
    """Verify API key for webhook endpoints."""
    # Placeholder for API key verification
    # In production, this would check against stored API keys
    if api_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return True