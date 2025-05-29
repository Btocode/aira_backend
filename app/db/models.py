"""
SQLAlchemy database models.
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.sql import func

from app.db.database import Base


class SubscriptionTier(str, PyEnum):
    """User subscription tiers."""
    FREE = "free"
    RESEARCHER = "researcher"
    INSTITUTION = "institution"


class ProcessingStatus(str, PyEnum):
    """Paper processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PaperSource(str, PyEnum):
    """Source of the paper."""
    ARXIV = "arxiv"
    JOURNAL = "journal"
    PDF_UPLOAD = "pdf_upload"
    URL = "url"


class ReadingStatus(str, PyEnum):
    """User's reading status for a paper."""
    SAVED = "saved"
    READING = "reading"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class EntryType(str, PyEnum):
    """Knowledge entry types."""
    SUMMARY = "summary"
    NOTE = "note"
    HIGHLIGHT = "highlight"
    INSIGHT = "insight"
    QUESTION = "question"


# User Models
class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))

    # User status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Subscription
    subscription_tier = Column(
        Enum(SubscriptionTier),
        default=SubscriptionTier.FREE,
        nullable=False
    )
    subscription_expires_at = Column(DateTime, nullable=True)

    # Research preferences
    research_interests = Column(JSON, default=list)  # List of research areas
    preferred_ai_model = Column(String(50), default="gpt-4")

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    papers: Mapped[List["UserPaper"]] = relationship("UserPaper", back_populates="user")
    knowledge_entries: Mapped[List["KnowledgeEntry"]] = relationship(
        "KnowledgeEntry", back_populates="user"
    )


# Paper Models
class Paper(Base):
    """Academic paper model."""

    __tablename__ = "papers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Paper identifiers
    doi = Column(String(255), unique=True, index=True, nullable=True)
    arxiv_id = Column(String(50), unique=True, index=True, nullable=True)
    pmid = Column(String(50), unique=True, index=True, nullable=True)  # PubMed ID

    # Paper metadata
    title = Column(Text, nullable=False, index=True)
    authors = Column(JSON, default=list)  # List of author objects
    abstract = Column(Text)
    keywords = Column(JSON, default=list)  # List of keywords

    # Publication info
    journal = Column(String(255))
    volume = Column(String(50))
    issue = Column(String(50))
    pages = Column(String(50))
    publication_date = Column(DateTime)
    publication_year = Column(Integer, index=True)

    # URLs and files
    url = Column(String(500))
    pdf_url = Column(String(500))
    source = Column(Enum(PaperSource), nullable=False)

    # Content
    full_text = Column(Text)  # Extracted full text

    # AI-generated content
    summary = Column(JSON, nullable=True)  # Structured summary
    key_insights = Column(JSON, default=list)  # List of key insights
    methodology = Column(Text)
    limitations = Column(Text)
    contributions = Column(JSON, default=list)  # List of contributions

    # Processing status
    processing_status = Column(
        Enum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        nullable=False
    )
    processed_at = Column(DateTime, nullable=True)
    processing_error = Column(Text, nullable=True)

    # Metrics
    citation_count = Column(Integer, default=0)
    influence_score = Column(Float, default=0.0)  # Our calculated influence score

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user_interactions: Mapped[List["UserPaper"]] = relationship(
        "UserPaper", back_populates="paper"
    )
    citations_as_citing: Mapped[List["Citation"]] = relationship(
        "Citation", foreign_keys="Citation.citing_paper_id", back_populates="citing_paper"
    )
    citations_as_cited: Mapped[List["Citation"]] = relationship(
        "Citation", foreign_keys="Citation.cited_paper_id", back_populates="cited_paper"
    )
    knowledge_entries: Mapped[List["KnowledgeEntry"]] = relationship(
        "KnowledgeEntry", back_populates="paper"
    )


class UserPaper(Base):
    """User-Paper relationship model."""

    __tablename__ = "user_papers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=False)

    # Reading status
    status = Column(Enum(ReadingStatus), default=ReadingStatus.SAVED, nullable=False)
    reading_progress = Column(Integer, default=0)  # Percentage 0-100
    time_spent = Column(Integer, default=0)  # Time in seconds

    # User annotations
    rating = Column(Integer, nullable=True)  # 1-5 stars
    tags = Column(JSON, default=list)  # User-defined tags
    notes = Column(Text)  # User notes

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_accessed_at = Column(DateTime, default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="papers")
    paper: Mapped["Paper"] = relationship("Paper", back_populates="user_interactions")

    # Unique constraint
    __table_args__ = (UniqueConstraint("user_id", "paper_id", name="unique_user_paper"),)


# Citation Network
class Citation(Base):
    """Citation relationship between papers."""

    __tablename__ = "citations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    citing_paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=False)
    cited_paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=False)

    # Citation details
    context = Column(Text)  # Context where citation appears
    section = Column(String(100))  # Section where citation appears
    sentiment = Column(String(20))  # positive, negative, neutral

    # Citation strength/importance
    strength = Column(Float, default=1.0)  # 0.0 to 1.0

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    citing_paper: Mapped["Paper"] = relationship(
        "Paper", foreign_keys=[citing_paper_id], back_populates="citations_as_citing"
    )
    cited_paper: Mapped["Paper"] = relationship(
        "Paper", foreign_keys=[cited_paper_id], back_populates="citations_as_cited"
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("citing_paper_id", "cited_paper_id", name="unique_citation"),
    )


# Knowledge Base
class KnowledgeEntry(Base):
    """User's knowledge base entries."""

    __tablename__ = "knowledge_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=True)

    # Entry content
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    entry_type = Column(Enum(EntryType), nullable=False)

    # Entry metadata
    tags = Column(JSON, default=list)
    section_reference = Column(String(100))  # Paper section if applicable
    page_number = Column(Integer, nullable=True)

    # AI-generated fields
    summary = Column(Text)  # AI-generated summary
    connections = Column(JSON, default=list)  # Connections to other entries

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="knowledge_entries")
    paper: Mapped[Optional["Paper"]] = relationship("Paper", back_populates="knowledge_entries")


# Background Tasks
class ProcessingTask(Base):
    """Background processing tasks."""

    __tablename__ = "processing_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id = Column(String(255), unique=True, index=True)  # Celery task ID

    # Task details
    task_type = Column(String(100), nullable=False)  # paper_processing, ai_analysis, etc.
    task_data = Column(JSON, default=dict)  # Task parameters

    # Status
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # Progress percentage
    result = Column(JSON, nullable=True)  # Task result
    error_message = Column(Text, nullable=True)

    # Related entities
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


# Analytics and Usage
class UserActivity(Base):
    """User activity tracking."""

    __tablename__ = "user_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Activity details
    activity_type = Column(String(100), nullable=False)  # paper_read, search, etc.
    activity_data = Column(JSON, default=dict)  # Activity parameters

    # Context
    session_id = Column(String(255))
    ip_address = Column(String(45))
    user_agent = Column(String(500))

    # Timestamp
    created_at = Column(DateTime, default=func.now(), nullable=False)


# API Usage Tracking
class APIUsage(Base):
    """API usage tracking for rate limiting and analytics."""

    __tablename__ = "api_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Request details
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time = Column(Float)  # Response time in seconds

    # AI usage
    ai_service = Column(String(50))  # openai, anthropic, etc.
    tokens_used = Column(Integer, default=0)
    cost = Column(Float, default=0.0)

    # Timestamp
    created_at = Column(DateTime, default=func.now(), nullable=False)