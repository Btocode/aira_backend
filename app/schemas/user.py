"""
User schemas for request/response validation.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.db.models import SubscriptionTier


# Base User schema
class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    full_name: Optional[str] = None
    research_interests: List[str] = Field(default_factory=list)
    preferred_ai_model: str = "gpt-4"


# User creation schema
class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


# User update schema
class UserUpdate(BaseModel):
    """Schema for updating user information."""
    full_name: Optional[str] = None
    research_interests: Optional[List[str]] = None
    preferred_ai_model: Optional[str] = None


# User response schema
class UserResponse(UserBase):
    """Schema for user response data."""
    id: UUID
    is_active: bool
    is_verified: bool
    subscription_tier: SubscriptionTier
    subscription_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# User in database schema (alias for UserResponse)
class UserInDB(UserResponse):
    """Schema for user as stored in database."""
    pass


# User profile schema (with more details)
class UserProfile(UserResponse):
    """Extended user profile schema."""
    pass


# Password change schema
class PasswordChange(BaseModel):
    """Schema for changing user password."""
    current_password: str
    new_password: str = Field(..., min_length=8, description="New password must be at least 8 characters")


# Email verification schema
class EmailVerification(BaseModel):
    """Schema for email verification."""
    token: str


# User statistics schema
class UserStats(BaseModel):
    """Schema for user statistics."""
    papers_count: int = 0
    knowledge_entries_count: int = 0
    total_reading_time: int = 0  # in seconds
    papers_read: int = 0
    papers_saved: int = 0
    average_rating: Optional[float] = None
    most_frequent_tags: List[str] = Field(default_factory=list)
    recent_activity_count: int = 0