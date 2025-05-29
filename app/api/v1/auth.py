"""
Authentication API endpoints.
"""
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import SecurityUtils, get_current_active_user
from app.db.database import get_db
from app.db.queries.user_queries import (
    create_user, get_user_by_email, authenticate_user, update_user_last_login
)
from app.schemas.auth import Token, TokenData, UserLogin, UserRegister
from app.schemas.user import UserCreate, UserInDB
from app.core.app_logging import api_logger

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
) -> Any:
    """Register a new user."""

    api_logger.info(f"Registration attempt for email: {user_data.email}")

    # Check if user already exists
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    try:
        user_create = UserCreate(**user_data.dict())
        user = await create_user(db, user_create)

        # Generate tokens
        access_token = SecurityUtils.create_access_token(subject=str(user.id))
        refresh_token = SecurityUtils.create_refresh_token(subject=str(user.id))

        api_logger.info(f"User registered successfully: {user.id}")

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        )

    except Exception as e:
        api_logger.error(f"Registration failed for {user_data.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Any:
    """Login user with email and password."""

    api_logger.info(f"Login attempt for email: {form_data.username}")

    # Authenticate user
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        api_logger.warning(f"Failed login attempt for: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Update last login
    await update_user_last_login(db, user.id)

    # Generate tokens
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = SecurityUtils.create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )
    refresh_token = SecurityUtils.create_refresh_token(subject=str(user.id))

    api_logger.info(f"User logged in successfully: {user.id}")

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


@router.post("/login-json", response_model=Token)
async def login_json(
    user_login: UserLogin,
    db: Session = Depends(get_db)
) -> Any:
    """Login user with JSON payload."""

    api_logger.info(f"JSON login attempt for email: {user_login.email}")

    # Authenticate user
    user = await authenticate_user(db, user_login.email, user_login.password)
    if not user:
        api_logger.warning(f"Failed JSON login attempt for: {user_login.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Update last login
    await update_user_last_login(db, user.id)

    # Generate tokens
    access_token = SecurityUtils.create_access_token(subject=str(user.id))
    refresh_token = SecurityUtils.create_refresh_token(subject=str(user.id))

    api_logger.info(f"User logged in via JSON successfully: {user.id}")

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenData,
    db: Session = Depends(get_db)
) -> Any:
    """Refresh access token using refresh token."""

    # Verify refresh token
    user_id = SecurityUtils.verify_token(token_data.refresh_token, "refresh")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Check if user exists and is active
    from app.db.queries.user_queries import get_user_by_id
    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Generate new tokens
    access_token = SecurityUtils.create_access_token(subject=str(user.id))
    refresh_token = SecurityUtils.create_refresh_token(subject=str(user.id))

    api_logger.info(f"Token refreshed for user: {user.id}")

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


@router.get("/me", response_model=UserInDB)
async def get_current_user_info(
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """Get current user information."""
    return current_user


@router.post("/logout")
async def logout(
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """Logout user (invalidate tokens)."""

    # In a production system, you'd want to maintain a blacklist of tokens
    # For now, we'll just return a success message

    api_logger.info(f"User logged out: {current_user.id}")

    return {"message": "Successfully logged out"}


@router.post("/verify-email")
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
) -> Any:
    """Verify user email address."""

    # Verify email verification token
    user_id = SecurityUtils.verify_token(token, "email_verification")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )

    # Update user verification status
    from app.db.queries.user_queries import verify_user_email
    user = await verify_user_email(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    api_logger.info(f"Email verified for user: {user.id}")

    return {"message": "Email verified successfully"}


@router.post("/forgot-password")
async def forgot_password(
    email: str,
    db: Session = Depends(get_db)
) -> Any:
    """Request password reset."""

    user = await get_user_by_email(db, email)
    if not user:
        # Don't reveal if email exists or not
        return {"message": "If the email exists, a reset link has been sent"}

    # Generate password reset token
    reset_token = SecurityUtils.create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(hours=1)
    )

    # In a production system, you'd send an email with the reset link
    # For now, we'll just log it
    api_logger.info(f"Password reset requested for user: {user.id}")

    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(get_db)
) -> Any:
    """Reset user password."""

    # Verify reset token
    user_id = SecurityUtils.verify_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Update user password
    from app.db.queries.user_queries import update_user_password
    user = await update_user_password(db, user_id, new_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    api_logger.info(f"Password reset for user: {user.id}")

    return {"message": "Password reset successfully"}