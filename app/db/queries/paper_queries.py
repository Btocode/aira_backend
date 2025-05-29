"""
Paper database queries.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func

from app.db.models import Paper, UserPaper, User, ProcessingStatus, ReadingStatus, PaperSource
from app.schemas.paper import PaperCreate, PaperUpdate, UserPaperCreate, UserPaperUpdate
from app.core.app_logging import db_logger


# Paper CRUD Operations
async def create_paper(db: Session, paper_data: dict) -> Paper:
    """Create a new paper."""
    try:
        db_paper = Paper(**paper_data)
        db.add(db_paper)
        db.commit()
        db.refresh(db_paper)

        db_logger.info(f"Paper created successfully: {db_paper.id}")
        return db_paper

    except Exception as e:
        db_logger.error(f"Error creating paper: {e}")
        db.rollback()
        raise


async def get_paper_by_id(db: Session, paper_id: str) -> Optional[Paper]:
    """Get paper by ID."""
    try:
        return db.query(Paper).filter(Paper.id == UUID(paper_id)).first()
    except Exception as e:
        db_logger.error(f"Error getting paper by ID {paper_id}: {e}")
        return None


async def get_paper_by_doi(db: Session, doi: str) -> Optional[Paper]:
    """Get paper by DOI."""
    try:
        return db.query(Paper).filter(Paper.doi == doi).first()
    except Exception as e:
        db_logger.error(f"Error getting paper by DOI {doi}: {e}")
        return None


async def get_paper_by_arxiv_id(db: Session, arxiv_id: str) -> Optional[Paper]:
    """Get paper by arXiv ID."""
    try:
        return db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
    except Exception as e:
        db_logger.error(f"Error getting paper by arXiv ID {arxiv_id}: {e}")
        return None


async def get_paper_by_url(db: Session, url: str) -> Optional[Paper]:
    """Get paper by URL."""
    try:
        return db.query(Paper).filter(Paper.url == url).first()
    except Exception as e:
        db_logger.error(f"Error getting paper by URL {url}: {e}")
        return None


async def update_paper(db: Session, paper_id: str, paper_update: dict) -> Optional[Paper]:
    """Update paper information."""
    try:
        paper = await get_paper_by_id(db, paper_id)
        if not paper:
            return None

        # Update fields
        for field, value in paper_update.items():
            if hasattr(paper, field):
                setattr(paper, field, value)

        paper.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(paper)

        db_logger.info(f"Paper updated successfully: {paper.id}")
        return paper

    except Exception as e:
        db_logger.error(f"Error updating paper {paper_id}: {e}")
        db.rollback()
        raise


async def update_paper_processing_status(
    db: Session,
    paper_id: str,
    status: ProcessingStatus,
    error_message: Optional[str] = None
) -> Optional[Paper]:
    """Update paper processing status."""
    try:
        paper = await get_paper_by_id(db, paper_id)
        if not paper:
            return None

        paper.processing_status = status
        paper.updated_at = datetime.utcnow()

        if status == ProcessingStatus.COMPLETED:
            paper.processed_at = datetime.utcnow()
        elif status == ProcessingStatus.FAILED:
            paper.processing_error = error_message

        db.commit()
        db.refresh(paper)

        db_logger.info(f"Paper processing status updated: {paper.id} -> {status}")
        return paper

    except Exception as e:
        db_logger.error(f"Error updating paper processing status {paper_id}: {e}")
        db.rollback()
        return None


# User-Paper Relationship Operations
async def create_user_paper(db: Session, user_id: str, paper_id: str, **kwargs) -> UserPaper:
    """Create user-paper relationship."""
    try:
        db_user_paper = UserPaper(
            user_id=UUID(user_id),
            paper_id=UUID(paper_id),
            **kwargs
        )
        db.add(db_user_paper)
        db.commit()
        db.refresh(db_user_paper)

        db_logger.info(f"User-paper relationship created: {user_id} -> {paper_id}")
        return db_user_paper

    except Exception as e:
        db_logger.error(f"Error creating user-paper relationship: {e}")
        db.rollback()
        raise


async def get_user_paper(db: Session, user_id: str, paper_id: str) -> Optional[UserPaper]:
    """Get user-paper relationship."""
    try:
        return db.query(UserPaper).filter(
            and_(
                UserPaper.user_id == UUID(user_id),
                UserPaper.paper_id == UUID(paper_id)
            )
        ).first()
    except Exception as e:
        db_logger.error(f"Error getting user-paper relationship: {e}")
        return None


async def update_user_paper(
    db: Session,
    user_id: str,
    paper_id: str,
    update_data: dict
) -> Optional[UserPaper]:
    """Update user-paper relationship."""
    try:
        user_paper = await get_user_paper(db, user_id, paper_id)
        if not user_paper:
            return None

        # Update fields
        for field, value in update_data.items():
            if hasattr(user_paper, field):
                setattr(user_paper, field, value)

        user_paper.updated_at = datetime.utcnow()
        user_paper.last_accessed_at = datetime.utcnow()

        db.commit()
        db.refresh(user_paper)

        db_logger.info(f"User-paper relationship updated: {user_id} -> {paper_id}")
        return user_paper

    except Exception as e:
        db_logger.error(f"Error updating user-paper relationship: {e}")
        db.rollback()
        return None


# Paper Search and Discovery
async def search_papers(
    db: Session,
    query: str,
    user_id: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: str = "relevance",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0
) -> List[Paper]:
    """Search papers with filters and sorting."""
    try:
        # Build base query
        base_query = db.query(Paper)

        # Add user filter if provided
        if user_id:
            base_query = base_query.join(UserPaper).filter(
                UserPaper.user_id == UUID(user_id)
            )

        # Add text search
        if query:
            search_filter = or_(
                Paper.title.ilike(f"%{query}%"),
                Paper.abstract.ilike(f"%{query}%"),
                Paper.keywords.astext.ilike(f"%{query}%")
            )
            base_query = base_query.filter(search_filter)

        # Apply filters
        if filters:
            if "publication_year" in filters:
                base_query = base_query.filter(Paper.publication_year == filters["publication_year"])

            if "source" in filters:
                base_query = base_query.filter(Paper.source == filters["source"])

            if "journal" in filters:
                base_query = base_query.filter(Paper.journal.ilike(f"%{filters['journal']}%"))

            if "authors" in filters:
                author_filter = filters["authors"]
                base_query = base_query.filter(
                    Paper.authors.astext.ilike(f"%{author_filter}%")
                )

            if "has_pdf" in filters and filters["has_pdf"]:
                base_query = base_query.filter(Paper.pdf_url.isnot(None))

            if "citation_count_min" in filters:
                base_query = base_query.filter(Paper.citation_count >= filters["citation_count_min"])

            if "citation_count_max" in filters:
                base_query = base_query.filter(Paper.citation_count <= filters["citation_count_max"])

        # Apply sorting
        if sort_by == "date":
            sort_field = Paper.publication_date
        elif sort_by == "citations":
            sort_field = Paper.citation_count
        elif sort_by == "title":
            sort_field = Paper.title
        else:  # relevance (default)
            sort_field = Paper.influence_score

        if sort_order == "asc":
            base_query = base_query.order_by(asc(sort_field))
        else:
            base_query = base_query.order_by(desc(sort_field))

        # Apply pagination
        papers = base_query.offset(offset).limit(limit).all()

        db_logger.info(f"Paper search completed: {len(papers)} results")
        return papers

    except Exception as e:
        db_logger.error(f"Error searching papers: {e}")
        return []


async def get_user_papers(
    db: Session,
    user_id: str,
    status: Optional[ReadingStatus] = None,
    limit: int = 20,
    offset: int = 0
) -> List[Paper]:
    """Get papers for a specific user."""
    try:
        query = db.query(Paper).join(UserPaper).filter(
            UserPaper.user_id == UUID(user_id)
        )

        if status:
            query = query.filter(UserPaper.status == status)

        papers = query.order_by(desc(UserPaper.created_at)).offset(offset).limit(limit).all()

        db_logger.info(f"Retrieved {len(papers)} papers for user {user_id}")
        return papers

    except Exception as e:
        db_logger.error(f"Error getting user papers: {e}")
        return []


async def get_recent_papers(db: Session, limit: int = 10) -> List[Paper]:
    """Get recently added papers."""
    try:
        papers = db.query(Paper).order_by(desc(Paper.created_at)).limit(limit).all()
        return papers
    except Exception as e:
        db_logger.error(f"Error getting recent papers: {e}")
        return []


async def get_popular_papers(db: Session, limit: int = 10) -> List[Paper]:
    """Get popular papers by citation count."""
    try:
        papers = db.query(Paper).order_by(desc(Paper.citation_count)).limit(limit).all()
        return papers
    except Exception as e:
        db_logger.error(f"Error getting popular papers: {e}")
        return []


async def get_papers_by_processing_status(
    db: Session,
    status: ProcessingStatus,
    limit: int = 50
) -> List[Paper]:
    """Get papers by processing status."""
    try:
        papers = db.query(Paper).filter(
            Paper.processing_status == status
        ).order_by(Paper.created_at).limit(limit).all()

        return papers
    except Exception as e:
        db_logger.error(f"Error getting papers by processing status: {e}")
        return []


# Paper Statistics
async def get_paper_stats(db: Session) -> Dict[str, int]:
    """Get overall paper statistics."""
    try:
        total_papers = db.query(Paper).count()

        processed_papers = db.query(Paper).filter(
            Paper.processing_status == ProcessingStatus.COMPLETED
        ).count()

        pending_papers = db.query(Paper).filter(
            Paper.processing_status == ProcessingStatus.PENDING
        ).count()

        failed_papers = db.query(Paper).filter(
            Paper.processing_status == ProcessingStatus.FAILED
        ).count()

        return {
            "total_papers": total_papers,
            "processed_papers": processed_papers,
            "pending_papers": pending_papers,
            "failed_papers": failed_papers
        }

    except Exception as e:
        db_logger.error(f"Error getting paper stats: {e}")
        return {}


async def get_user_paper_stats(db: Session, user_id: str) -> Dict[str, int]:
    """Get paper statistics for a specific user."""
    try:
        total_papers = db.query(UserPaper).filter(
            UserPaper.user_id == UUID(user_id)
        ).count()

        reading_papers = db.query(UserPaper).filter(
            and_(
                UserPaper.user_id == UUID(user_id),
                UserPaper.status == ReadingStatus.READING
            )
        ).count()

        completed_papers = db.query(UserPaper).filter(
            and_(
                UserPaper.user_id == UUID(user_id),
                UserPaper.status == ReadingStatus.COMPLETED
            )
        ).count()

        # Calculate total reading time
        total_time_result = db.query(func.sum(UserPaper.time_spent)).filter(
            UserPaper.user_id == UUID(user_id)
        ).scalar()

        total_reading_time = total_time_result or 0

        return {
            "total_papers": total_papers,
            "reading_papers": reading_papers,
            "completed_papers": completed_papers,
            "total_reading_time": total_reading_time
        }

    except Exception as e:
        db_logger.error(f"Error getting user paper stats: {e}")
        return {}