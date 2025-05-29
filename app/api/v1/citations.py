"""
Citation network API endpoints.
"""
from typing import List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.database import get_db
from app.schemas.user import UserInDB
from app.schemas.paper import CitationNetwork
from app.services.citation_service import citation_service
from app.core.app_logging import api_logger

router = APIRouter()


@router.get("/{paper_id}/network", response_model=CitationNetwork)
async def get_citation_network(
    paper_id: UUID,
    depth: int = 2,
    max_papers: int = 50,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get citation network for a paper."""

    try:
        # Check if user has access to the paper
        from app.db.queries.paper_queries import get_user_paper
        user_paper = await get_user_paper(db, str(current_user.id), str(paper_id))

        if not user_paper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this paper"
            )

        # Get citation network
        network = await citation_service.build_citation_network(
            str(paper_id), depth, max_papers, db
        )

        api_logger.info(f"Retrieved citation network for paper {paper_id}")

        return network

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get citation network for {paper_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve citation network"
        )


@router.get("/{paper_id}/citing", response_model=List[Dict[str, Any]])
async def get_citing_papers(
    paper_id: UUID,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get papers that cite this paper."""

    try:
        # Check user access
        from app.db.queries.paper_queries import get_user_paper
        user_paper = await get_user_paper(db, str(current_user.id), str(paper_id))

        if not user_paper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this paper"
            )

        # Get citing papers
        citing_papers = await citation_service.get_citing_papers(
            str(paper_id), limit, db
        )

        return citing_papers

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get citing papers for {paper_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve citing papers"
        )


@router.get("/{paper_id}/references", response_model=List[Dict[str, Any]])
async def get_referenced_papers(
    paper_id: UUID,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get papers referenced by this paper."""

    try:
        # Check user access
        from app.db.queries.paper_queries import get_user_paper
        user_paper = await get_user_paper(db, str(current_user.id), str(paper_id))

        if not user_paper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this paper"
            )

        # Get referenced papers
        referenced_papers = await citation_service.get_referenced_papers(
            str(paper_id), limit, db
        )

        return referenced_papers

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get referenced papers for {paper_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve referenced papers"
        )


@router.get("/{paper_id}/influence")
async def get_paper_influence(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get paper influence metrics."""

    try:
        # Check user access
        from app.db.queries.paper_queries import get_user_paper
        user_paper = await get_user_paper(db, str(current_user.id), str(paper_id))

        if not user_paper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this paper"
            )

        # Get influence metrics
        influence_metrics = await citation_service.calculate_paper_influence(
            str(paper_id), db
        )

        return influence_metrics

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get paper influence for {paper_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve paper influence"
        )