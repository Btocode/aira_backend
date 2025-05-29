"""
Search API endpoints for papers and knowledge.
"""
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.database import get_db
from app.schemas.user import UserInDB
from app.schemas.paper import PaperSearchRequest, PaperSearchResponse
from app.schemas.knowledge import KnowledgeSearchRequest, KnowledgeSearchResponse
from app.services.paper_service import paper_service
from app.services.knowledge_service import knowledge_service
from app.core.app_logging import api_logger

router = APIRouter()


@router.post("/papers", response_model=PaperSearchResponse)
async def search_papers(
    search_request: PaperSearchRequest,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Search papers in user's library."""

    try:
        results = await paper_service.search_user_papers(
            str(current_user.id), search_request, db
        )

        from app.schemas.paper import PaperPublic
        papers = [PaperPublic.from_orm(paper) for paper in results["papers"]]

        return PaperSearchResponse(
            papers=papers,
            total=results["total"],
            query=results["query"],
            filters=results["filters"],
            took_ms=results["took_ms"],
            page=results["page"],
            per_page=results["per_page"],
            has_next=results["has_next"],
            has_prev=results["has_prev"]
        )

    except Exception as e:
        api_logger.error(f"Paper search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paper search failed"
        )


@router.post("/knowledge", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    search_request: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Search knowledge entries."""

    try:
        results = await knowledge_service.search_knowledge_entries(
            str(current_user.id), search_request, db
        )

        from app.schemas.knowledge import KnowledgeEntryResponse
        entries = [KnowledgeEntryResponse.from_orm(entry) for entry in results["entries"]]

        return KnowledgeSearchResponse(
            entries=entries,
            total=results["total"],
            query=results["query"],
            took_ms=results["took_ms"]
        )

    except Exception as e:
        api_logger.error(f"Knowledge search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Knowledge search failed"
        )


@router.get("/global", response_model=Dict[str, Any])
async def global_search(
    query: str,
    include_papers: bool = True,
    include_knowledge: bool = True,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Global search across papers and knowledge."""

    try:
        results = {
            "query": query,
            "results": {
                "papers": [],
                "knowledge": []
            },
            "total": 0
        }

        # Search papers
        if include_papers:
            from app.schemas.paper import PaperSearchRequest
            paper_search = PaperSearchRequest(
                query=query,
                limit=limit
            )
            paper_results = await paper_service.search_user_papers(
                str(current_user.id), paper_search, db
            )

            from app.schemas.paper import PaperPublic
            results["results"]["papers"] = [
                PaperPublic.from_orm(paper) for paper in paper_results["papers"]
            ]

        # Search knowledge
        if include_knowledge:
            knowledge_search = KnowledgeSearchRequest(
                query=query,
                limit=limit
            )
            knowledge_results = await knowledge_service.search_knowledge_entries(
                str(current_user.id), knowledge_search, db
            )

            from app.schemas.knowledge import KnowledgeEntryResponse
            results["results"]["knowledge"] = [
                KnowledgeEntryResponse.from_orm(entry)
                for entry in knowledge_results["entries"]
            ]

        # Calculate total
        results["total"] = (
            len(results["results"]["papers"]) +
            len(results["results"]["knowledge"])
        )

        api_logger.info(f"Global search completed: {results['total']} results")

        return results

    except Exception as e:
        api_logger.error(f"Global search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Global search failed"
        )


@router.get("/suggestions")
async def get_search_suggestions(
    query: str,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get search suggestions based on user's data."""

    try:
        suggestions = []

        if len(query) < 2:
            return {"suggestions": suggestions}

        # Get paper title suggestions
        from app.db.queries.paper_queries import search_papers
        papers = await search_papers(
            db, query, str(current_user.id), limit=5
        )

        for paper in papers:
            if paper.title.lower().startswith(query.lower()):
                suggestions.append({
                    "text": paper.title,
                    "type": "paper_title",
                    "paper_id": str(paper.id)
                })

        # Get knowledge entry suggestions
        knowledge_entries = await knowledge_service.search_knowledge_entries(
            str(current_user.id),
            KnowledgeSearchRequest(query=query, limit=5),
            db
        )

        for entry in knowledge_entries["entries"]:
            if entry.title.lower().startswith(query.lower()):
                suggestions.append({
                    "text": entry.title,
                    "type": "knowledge_title",
                    "entry_id": str(entry.id)
                })

        # Limit total suggestions
        suggestions = suggestions[:10]

        return {"suggestions": suggestions}

    except Exception as e:
        api_logger.error(f"Failed to get search suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get search suggestions"
        )