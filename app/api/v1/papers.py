"""
Paper management API endpoints.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.database import get_db
from app.db.queries.paper_queries import (
    get_paper_by_id, get_user_paper, update_user_paper,
    get_user_papers, get_user_paper_stats
)
from app.schemas.paper import (
    PaperCreate, PaperDetailed, PaperPublic, PaperSearchRequest, PaperSearchResponse,
    UserPaperUpdate, PaperRecommendationsResponse, ProcessingTaskStatus,
    BulkPaperCreate, BulkOperationResponse
)
from app.schemas.user import UserInDB
from app.services.paper_service import paper_service
from app.services.pdf_processor import pdf_processor
from app.services.celery_tasks import process_paper_task, batch_process_papers_task
from app.core.app_logging import api_logger
from app.core.config import settings

router = APIRouter()


@router.post("/", response_model=PaperDetailed, status_code=status.HTTP_201_CREATED)
async def add_paper_from_url(
    paper_url: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Add a paper from URL for processing."""

    api_logger.info(f"Adding paper from URL for user {current_user.id}: {paper_url}")

    try:
        # Process paper from URL
        paper, is_new = await paper_service.process_paper_from_url(
            paper_url, str(current_user.id), db
        )

        if is_new:
            api_logger.info(f"New paper added: {paper.id}")
        else:
            api_logger.info(f"Existing paper added to user library: {paper.id}")

        # Get user-paper relationship for detailed response
        user_paper = await get_user_paper(db, str(current_user.id), str(paper.id))

        # Convert to detailed response
        paper_dict = paper.__dict__.copy()
        if user_paper:
            paper_dict.update({
                "user_status": user_paper.status,
                "user_rating": user_paper.rating,
                "user_tags": user_paper.tags or [],
                "user_notes": user_paper.notes,
                "reading_progress": user_paper.reading_progress,
                "time_spent": user_paper.time_spent
            })

        return PaperDetailed(**paper_dict)

    except Exception as e:
        api_logger.error(f"Failed to add paper from URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process paper: {str(e)}"
        )


@router.post("/upload", response_model=PaperDetailed, status_code=status.HTTP_201_CREATED)
async def upload_paper(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Upload a PDF paper for processing."""

    api_logger.info(f"Uploading paper for user {current_user.id}: {file.filename}")

    # Validate file
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )

    # Check file size
    file_content = await file.read()
    if len(file_content) > settings.upload_max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.upload_max_size} bytes"
        )

    try:
        # Process uploaded PDF
        pdf_data = await pdf_processor.process_uploaded_pdf(file_content)

        # Create paper record
        from app.db.queries.paper_queries import create_paper, create_user_paper
        from app.db.models import PaperSource, ProcessingStatus

        paper_data = {
            "title": title or pdf_data["metadata"].get("title", file.filename),
            "authors": pdf_data["metadata"].get("authors", []),
            "abstract": pdf_data["metadata"].get("abstract", ""),
            "full_text": pdf_data["text"],
            "source": PaperSource.PDF_UPLOAD,
            "processing_status": ProcessingStatus.PENDING
        }

        paper = await create_paper(db, paper_data)

        # Add to user's library
        await create_user_paper(db, str(current_user.id), str(paper.id))

        # Queue for AI processing
        process_paper_task.delay(str(paper.id))

        api_logger.info(f"Paper uploaded successfully: {paper.id}")

        # Return detailed response
        return PaperDetailed(**paper.__dict__)

    except Exception as e:
        api_logger.error(f"Failed to upload paper: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process uploaded file: {str(e)}"
        )


@router.get("/", response_model=List[PaperPublic])
async def get_user_papers(
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get papers for the current user."""

    try:
        from app.db.models import ReadingStatus

        # Parse status filter
        reading_status = None
        if status_filter:
            try:
                reading_status = ReadingStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter: {status_filter}"
                )

        # Get user papers
        papers = await get_user_papers(
            db, str(current_user.id), reading_status, limit, offset
        )

        api_logger.info(f"Retrieved {len(papers)} papers for user {current_user.id}")

        return [PaperPublic.from_orm(paper) for paper in papers]

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get user papers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve papers"
        )


@router.get("/{paper_id}", response_model=PaperDetailed)
async def get_paper(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get paper details."""

    try:
        # Get paper
        paper = await get_paper_by_id(db, str(paper_id))
        if not paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )

        # Check if user has access to this paper
        user_paper = await get_user_paper(db, str(current_user.id), str(paper_id))
        if not user_paper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this paper"
            )

        # Build detailed response
        paper_dict = paper.__dict__.copy()
        paper_dict.update({
            "user_status": user_paper.status,
            "user_rating": user_paper.rating,
            "user_tags": user_paper.tags or [],
            "user_notes": user_paper.notes,
            "reading_progress": user_paper.reading_progress,
            "time_spent": user_paper.time_spent
        })

        return PaperDetailed(**paper_dict)

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get paper {paper_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve paper"
        )


@router.put("/{paper_id}", response_model=PaperDetailed)
async def update_user_paper(
    paper_id: UUID,
    paper_update: UserPaperUpdate,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Update user's paper information (status, rating, notes, etc.)."""

    try:
        # Check if user has access to this paper
        user_paper = await get_user_paper(db, str(current_user.id), str(paper_id))
        if not user_paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found in user's library"
            )

        # Update user-paper relationship
        update_data = paper_update.dict(exclude_unset=True)
        updated_user_paper = await paper_service.update_reading_progress(
            str(current_user.id), str(paper_id), update_data, db
        )

        if not updated_user_paper:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update paper"
            )

        # Get updated paper for response
        paper = await get_paper_by_id(db, str(paper_id))

        # Build detailed response
        paper_dict = paper.__dict__.copy()
        paper_dict.update({
            "user_status": updated_user_paper.status,
            "user_rating": updated_user_paper.rating,
            "user_tags": updated_user_paper.tags or [],
            "user_notes": updated_user_paper.notes,
            "reading_progress": updated_user_paper.reading_progress,
            "time_spent": updated_user_paper.time_spent
        })

        api_logger.info(f"Updated paper {paper_id} for user {current_user.id}")

        return PaperDetailed(**paper_dict)

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to update paper {paper_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update paper"
        )


@router.post("/search", response_model=PaperSearchResponse)
async def search_papers(
    search_request: PaperSearchRequest,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Search papers in user's library."""

    try:
        # Perform search
        search_results = await paper_service.search_user_papers(
            str(current_user.id), search_request, db
        )

        # Convert papers to public format
        papers = [PaperPublic.from_orm(paper) for paper in search_results["papers"]]

        return PaperSearchResponse(
            papers=papers,
            total=search_results["total"],
            query=search_results["query"],
            filters=search_results["filters"],
            took_ms=search_results["took_ms"],
            page=search_results["page"],
            per_page=search_results["per_page"],
            has_next=search_results["has_next"],
            has_prev=search_results["has_prev"]
        )

    except Exception as e:
        api_logger.error(f"Search failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.get("/{paper_id}/summary")
async def get_paper_summary(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get AI-generated paper summary."""

    try:
        # Get paper
        paper = await get_paper_by_id(db, str(paper_id))
        if not paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )

        # Check user access
        user_paper = await get_user_paper(db, str(current_user.id), str(paper_id))
        if not user_paper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this paper"
            )

        # Check if summary is available
        if not paper.summary:
            if paper.processing_status.value == "pending":
                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail="Paper is being processed. Summary not ready yet."
                )
            elif paper.processing_status.value == "processing":
                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail="Paper is currently being processed. Please check back later."
                )
            elif paper.processing_status.value == "failed":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Paper processing failed. Summary not available."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Summary not available for this paper"
                )

        return {
            "paper_id": str(paper.id),
            "summary": paper.summary,
            "key_insights": paper.key_insights or [],
            "methodology": paper.methodology,
            "limitations": paper.limitations,
            "contributions": paper.contributions or [],
            "processing_status": paper.processing_status.value,
            "processed_at": paper.processed_at
        }

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get summary for paper {paper_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve summary"
        )


@router.get("/recommendations", response_model=PaperRecommendationsResponse)
async def get_recommendations(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get paper recommendations for the current user."""

    try:
        # Get recommendations
        recommendations = await paper_service.get_paper_recommendations(
            str(current_user.id), None, db, limit
        )

        # Convert to response format
        recommendation_items = []
        based_on_papers = []

        for rec in recommendations:
            recommendation_items.append({
                "paper": PaperPublic.from_orm(rec["paper"]),
                "relevance_score": rec["relevance_score"],
                "reason": rec["reason"],
                "recommendation_type": rec["recommendation_type"]
            })

        return PaperRecommendationsResponse(
            recommendations=recommendation_items,
            based_on_papers=based_on_papers,
            total=len(recommendation_items)
        )

    except Exception as e:
        api_logger.error(f"Failed to get recommendations for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recommendations"
        )


@router.post("/bulk", response_model=BulkOperationResponse)
async def bulk_add_papers(
    bulk_request: BulkPaperCreate,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Add multiple papers from URLs in bulk."""

    api_logger.info(f"Bulk adding {len(bulk_request.urls)} papers for user {current_user.id}")

    try:
        results = []
        errors = []
        successful = 0
        failed = 0

        # Process each URL
        for i, url in enumerate(bulk_request.urls):
            try:
                paper, is_new = await paper_service.process_paper_from_url(
                    str(url), str(current_user.id), db
                )

                results.append({
                    "url": str(url),
                    "paper_id": str(paper.id),
                    "status": "success",
                    "is_new": is_new
                })
                successful += 1

            except Exception as e:
                error_msg = f"Failed to process URL {url}: {str(e)}"
                api_logger.error(error_msg)

                errors.append({
                    "url": str(url),
                    "error": str(e),
                    "index": i
                })
                failed += 1

        api_logger.info(f"Bulk operation completed: {successful} successful, {failed} failed")

        return BulkOperationResponse(
            successful=successful,
            failed=failed,
            results=results,
            errors=errors
        )

    except Exception as e:
        api_logger.error(f"Bulk operation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk operation failed"
        )


@router.get("/stats/user")
async def get_user_paper_stats(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get paper statistics for the current user."""

    try:
        stats = await get_user_paper_stats(db, str(current_user.id))

        return {
            "user_id": str(current_user.id),
            "stats": stats,
            "generated_at": "2024-01-01T00:00:00Z"  # Replace with actual datetime
        }

    except Exception as e:
        api_logger.error(f"Failed to get user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.delete("/{paper_id}")
async def remove_paper_from_library(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Remove paper from user's library."""

    try:
        # Check if user has this paper
        user_paper = await get_user_paper(db, str(current_user.id), str(paper_id))
        if not user_paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found in user's library"
            )

        # Remove from user's library
        db.delete(user_paper)
        db.commit()

        api_logger.info(f"Removed paper {paper_id} from user {current_user.id} library")

        return {"message": "Paper removed from library successfully"}

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to remove paper {paper_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove paper"
        )