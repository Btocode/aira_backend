"""
Paper schemas for request/response validation.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.db.models import ProcessingStatus, PaperSource, ReadingStatus


# Paper schemas
class PaperBase(BaseModel):
    """Base paper schema with common fields."""
    title: str
    authors: List[Dict[str, Any]] = Field(default_factory=list)
    abstract: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publication_date: Optional[datetime] = None
    publication_year: Optional[int] = None


class PaperCreate(PaperBase):
    """Schema for creating a new paper."""
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pmid: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    source: PaperSource
    full_text: Optional[str] = None


class PaperUpdate(BaseModel):
    """Schema for updating paper information."""
    title: Optional[str] = None
    authors: Optional[List[Dict[str, Any]]] = None
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publication_date: Optional[datetime] = None
    publication_year: Optional[int] = None
    full_text: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    key_insights: Optional[List[str]] = None
    methodology: Optional[str] = None
    limitations: Optional[str] = None
    contributions: Optional[List[str]] = None


class PaperResponse(PaperBase):
    """Schema for paper response data."""
    id: UUID
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pmid: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    source: PaperSource
    processing_status: ProcessingStatus
    processed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    citation_count: int = 0
    influence_score: float = 0.0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Paper in database schema (alias for PaperResponse)
class PaperInDB(PaperResponse):
    """Schema for paper as stored in database."""
    pass


class PaperDetailed(PaperResponse):
    """Detailed paper schema with AI-generated content."""
    full_text: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    key_insights: List[str] = Field(default_factory=list)
    methodology: Optional[str] = None
    limitations: Optional[str] = None
    contributions: List[str] = Field(default_factory=list)


# UserPaper schemas
class UserPaperBase(BaseModel):
    """Base user-paper relationship schema."""
    status: ReadingStatus = ReadingStatus.SAVED
    reading_progress: int = Field(default=0, ge=0, le=100)
    time_spent: int = Field(default=0, ge=0)  # seconds
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class UserPaperCreate(UserPaperBase):
    """Schema for creating user-paper relationship."""
    pass


class UserPaperUpdate(BaseModel):
    """Schema for updating user-paper relationship."""
    status: Optional[ReadingStatus] = None
    reading_progress: Optional[int] = Field(default=None, ge=0, le=100)
    time_spent: Optional[int] = Field(default=None, ge=0)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class UserPaperResponse(UserPaperBase):
    """Schema for user-paper relationship response."""
    id: UUID
    user_id: UUID
    paper_id: UUID
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime

    class Config:
        from_attributes = True


class UserPaperWithPaper(UserPaperResponse):
    """User-paper relationship with paper details."""
    paper: PaperResponse


# Search and filter schemas
class PaperSearchQuery(BaseModel):
    """Schema for paper search queries."""
    query: str = Field(..., min_length=3, description="Search query")
    filters: Optional[Dict[str, Any]] = None
    sort_by: str = Field(default="relevance", description="Sort by field")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PaperSearchResults(BaseModel):
    """Schema for paper search results."""
    papers: List[PaperResponse]
    total: int
    offset: int
    limit: int


# Paper processing schemas
class PaperProcessingStatus(BaseModel):
    """Schema for paper processing status."""
    paper_id: UUID
    status: ProcessingStatus
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None


# Paper URL submission schema
class PaperURLSubmission(BaseModel):
    """Schema for submitting a paper URL for processing."""
    url: str = Field(..., description="URL of the paper")
    tags: List[str] = Field(default_factory=list, description="Initial tags")
    notes: Optional[str] = Field(default=None, description="Initial notes")


# Public paper schema (limited information)
class PaperPublic(BaseModel):
    """Public paper schema with limited information."""
    id: UUID
    title: str
    authors: List[Dict[str, Any]] = Field(default_factory=list)
    abstract: Optional[str] = None
    journal: Optional[str] = None
    publication_year: Optional[int] = None
    source: PaperSource
    processing_status: ProcessingStatus
    citation_count: int = 0
    influence_score: float = 0.0
    created_at: datetime

    class Config:
        from_attributes = True


# Search request schema
class PaperSearchRequest(BaseModel):
    """Schema for paper search requests."""
    query: str = Field(..., min_length=1, description="Search query")
    filters: Optional[Dict[str, Any]] = None
    sort_by: str = Field(default="relevance", description="Sort by field")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# Search response schema
class PaperSearchResponse(BaseModel):
    """Schema for paper search responses."""
    papers: List[PaperPublic]
    total: int
    offset: int
    limit: int
    query: str
    processing_time: Optional[float] = None


# Recommendations response schema
class PaperRecommendationsResponse(BaseModel):
    """Schema for paper recommendations."""
    recommendations: List[PaperPublic]
    total: int
    algorithm: str = "collaborative_filtering"
    generated_at: datetime


# Processing task status schema
class ProcessingTaskStatus(BaseModel):
    """Schema for processing task status."""
    task_id: str
    status: str
    progress: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Bulk operations schemas
class BulkPaperCreate(BaseModel):
    """Schema for bulk paper creation."""
    urls: List[str] = Field(..., min_items=1, max_items=50, description="List of paper URLs")
    tags: List[str] = Field(default_factory=list, description="Tags to apply to all papers")
    notes: Optional[str] = Field(default=None, description="Notes to apply to all papers")


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation responses."""
    total_submitted: int
    successful: int
    failed: int
    task_ids: List[str]
    errors: List[Dict[str, str]] = Field(default_factory=list)


# AI-related schemas
class KeyInsight(BaseModel):
    """Schema for key insights extracted from papers."""
    insight: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    section: Optional[str] = None
    page_number: Optional[int] = None


class PaperContribution(BaseModel):
    """Schema for paper contributions."""
    contribution: str
    type: str  # "theoretical", "methodological", "empirical", "practical"
    significance: float = Field(ge=0.0, le=1.0)
    description: Optional[str] = None


class PaperSummary(BaseModel):
    """Schema for AI-generated paper summaries."""
    executive_summary: str
    key_findings: List[str]
    methodology_overview: str
    contributions: List[PaperContribution]
    limitations: List[str]
    future_work: List[str]
    relevance_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)


# Citation-related schemas
class CitationNode(BaseModel):
    """Schema for citation network nodes."""
    paper_id: UUID
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    citation_count: int = 0
    influence_score: float = 0.0


class CitationEdge(BaseModel):
    """Schema for citation network edges."""
    source_id: UUID
    target_id: UUID
    context: Optional[str] = None
    sentiment: Optional[str] = None
    strength: float = 1.0


class CitationNetwork(BaseModel):
    """Schema for citation network visualization."""
    nodes: List[CitationNode]
    edges: List[CitationEdge]
    total_nodes: int
    total_edges: int
    center_paper_id: UUID
    depth: int = 1