"""
Knowledge base related Pydantic schemas.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import EntryType


class KnowledgeEntryBase(BaseModel):
    """Base knowledge entry schema."""
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    entry_type: EntryType
    tags: List[str] = Field(default_factory=list)
    section_reference: Optional[str] = None
    page_number: Optional[int] = None


class KnowledgeEntryCreate(KnowledgeEntryBase):
    """Create knowledge entry schema."""
    paper_id: Optional[UUID] = None


class KnowledgeEntryUpdate(BaseModel):
    """Update knowledge entry schema."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    entry_type: Optional[EntryType] = None
    tags: Optional[List[str]] = None
    section_reference: Optional[str] = None
    page_number: Optional[int] = None


class KnowledgeEntryResponse(KnowledgeEntryBase):
    """Knowledge entry response schema."""
    id: UUID
    user_id: UUID
    paper_id: Optional[UUID] = None
    summary: Optional[str] = None
    connections: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeSearchRequest(BaseModel):
    """Knowledge search request schema."""
    query: str = Field(..., min_length=2, max_length=500)
    entry_types: Optional[List[EntryType]] = None
    tags: Optional[List[str]] = None
    paper_id: Optional[UUID] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class KnowledgeSearchResponse(BaseModel):
    """Knowledge search response schema."""
    entries: List[KnowledgeEntryResponse]
    total: int
    query: str
    took_ms: int


class KnowledgeStats(BaseModel):
    """Knowledge base statistics."""
    total_entries: int
    entries_by_type: Dict[str, int]
    recent_entries: int
    total_tags: int
    most_used_tags: List[Dict[str, Any]]

    class Config:
        from_attributes = True