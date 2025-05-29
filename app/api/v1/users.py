"""
User management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.database import get_db
from app.db.queries.user_queries import update_user, get_user_stats
from app.schemas.user import UserInDB, UserUpdate, UserProfile, UserStats, PasswordChange
from app.core.app_logging import api_logger

router = APIRouter()


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get current user's profile with statistics."""

    try:
        # Get user statistics
        stats = await get_user_stats(db, str(current_user.id))

        # Build profile response
        profile_data = current_user.__dict__.copy()
        profile_data.update(stats)

        return UserProfile(**profile_data)

    except Exception as e:
        api_logger.error(f"Failed to get user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )


@router.put("/me", response_model=UserInDB)
async def update_current_user(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Update current user's profile."""

    try:
        updated_user = await update_user(db, str(current_user.id), user_update)

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update user profile"
            )

        api_logger.info(f"User profile updated: {current_user.id}")

        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to update user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user profile"
        )


@router.post("/me/change-password")
async def change_password(
    password_change: PasswordChange,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Change user's password."""

    try:
        from app.core.security import SecurityUtils
        from app.db.queries.user_queries import update_user_password

        # Verify current password
        if not SecurityUtils.verify_password(
            password_change.current_password,
            current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )

        # Update password
        updated_user = await update_user_password(
            db, str(current_user.id), password_change.new_password
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update password"
            )

        api_logger.info(f"Password changed for user: {current_user.id}")

        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to change password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.get("/me/stats", response_model=UserStats)
async def get_current_user_stats(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get detailed statistics for current user."""

    try:
        from app.db.queries.paper_queries import get_user_paper_stats
        from app.services.knowledge_service import knowledge_service

        # Get paper stats
        paper_stats = await get_user_paper_stats(db, str(current_user.id))

        # Get knowledge stats
        knowledge_stats = await knowledge_service.get_knowledge_stats(
            str(current_user.id), db
        )

        # Combine stats
        stats = UserStats(
            papers_read=paper_stats.get("completed_papers", 0),
            papers_saved=paper_stats.get("total_papers", 0),
            knowledge_entries=knowledge_stats.get("total_entries", 0),
            total_reading_time=paper_stats.get("total_reading_time", 0),
            ai_summaries_generated=0,  # Would be tracked separately
            searches_performed=0,      # Would be tracked separately
            citations_explored=0       # Would be tracked separately
        )

        return stats

    except Exception as e:
        api_logger.error(f"Failed to get user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user statistics"
        )


@router.delete("/me")
async def delete_current_user_account(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Delete current user's account."""

    try:
        from app.db.queries.user_queries import deactivate_user

        # Deactivate user (soft delete)
        deactivated_user = await deactivate_user(db, str(current_user.id))

        if not deactivated_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete account"
            )

        api_logger.info(f"User account deleted: {current_user.id}")

        return {"message": "Account deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to delete user account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )