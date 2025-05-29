"""
Knowledge base management API endpoints.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.database import get_db
from app.schemas.user import UserInDB
from app.schemas.knowledge import (
    KnowledgeEntryCreate, KnowledgeEntryUpdate, KnowledgeEntryResponse,
    KnowledgeSearchRequest, KnowledgeSearchResponse
)
from app.services.knowledge_service import knowledge_service
from app.core.app_logging import api_logger

router = APIRouter()


@router.get("/", response_model=List[KnowledgeEntryResponse])
async def get_knowledge_entries(
    entry_type: Optional[str] = None,
    paper_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get knowledge entries for the current user."""

    try:
        entries = await knowledge_service.get_user_knowledge_entries(
            str(current_user.id), entry_type, str(paper_id) if paper_id else None,
            limit, offset, db
        )

        api_logger.info(f"Retrieved {len(entries)} knowledge entries for user {current_user.id}")

        return [KnowledgeEntryResponse.from_orm(entry) for entry in entries]

    except Exception as e:
        api_logger.error(f"Failed to get knowledge entries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge entries"
        )


@router.post("/", response_model=KnowledgeEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_entry(
    entry_data: KnowledgeEntryCreate,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Create a new knowledge entry."""

    try:
        entry = await knowledge_service.create_knowledge_entry(
            str(current_user.id), entry_data, db
        )

        api_logger.info(f"Created knowledge entry {entry.id} for user {current_user.id}")

        return KnowledgeEntryResponse.from_orm(entry)

    except Exception as e:
        api_logger.error(f"Failed to create knowledge entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create knowledge entry"
        )


@router.get("/{entry_id}", response_model=KnowledgeEntryResponse)
async def get_knowledge_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get a specific knowledge entry."""

    try:
        entry = await knowledge_service.get_knowledge_entry(
            str(entry_id), str(current_user.id), db
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge entry not found"
            )

        return KnowledgeEntryResponse.from_orm(entry)

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get knowledge entry {entry_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge entry"
        )


@router.put("/{entry_id}", response_model=KnowledgeEntryResponse)
async def update_knowledge_entry(
    entry_id: UUID,
    entry_update: KnowledgeEntryUpdate,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Update a knowledge entry."""

    try:
        entry = await knowledge_service.update_knowledge_entry(
            str(entry_id), str(current_user.id), entry_update, db
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge entry not found"
            )

        api_logger.info(f"Updated knowledge entry {entry_id} for user {current_user.id}")

        return KnowledgeEntryResponse.from_orm(entry)

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to update knowledge entry {entry_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update knowledge entry"
        )


@router.delete("/{entry_id}")
async def delete_knowledge_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Delete a knowledge entry."""

    try:
        success = await knowledge_service.delete_knowledge_entry(
            str(entry_id), str(current_user.id), db
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge entry not found"
            )

        api_logger.info(f"Deleted knowledge entry {entry_id} for user {current_user.id}")

        return {"message": "Knowledge entry deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to delete knowledge entry {entry_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete knowledge entry"
        )


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    search_request: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Search knowledge entries using semantic search."""

    try:
        results = await knowledge_service.search_knowledge_entries(
            str(current_user.id), search_request, db
        )

        entries = [KnowledgeEntryResponse.from_orm(entry) for entry in results["entries"]]

        return KnowledgeSearchResponse(
            entries=entries,
            total=results["total"],
            query=results["query"],
            took_ms=results["took_ms"]
        )

    except Exception as e:
        api_logger.error(f"Knowledge search failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )