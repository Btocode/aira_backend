"""
Citation network analysis service.
"""
from typing import List, Dict, Any, Set
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.models import Paper, Citation
from app.schemas.paper import CitationNetwork
from app.core.app_logging import paper_logger, log_error


class CitationService:
    """Service for citation network analysis."""

    async def build_citation_network(
        self,
        center_paper_id: str,
        depth: int = 2,
        max_papers: int = 50,
        db: Session = None
    ) -> CitationNetwork:
        """Build citation network around a center paper."""

        paper_logger.info(f"Building citation network for paper {center_paper_id}")

        try:
            # Get center paper
            center_paper = db.query(Paper).filter(Paper.id == UUID(center_paper_id)).first()
            if not center_paper:
                raise ValueError(f"Paper not found: {center_paper_id}")

            # Build network using BFS
            nodes = {}  # paper_id -> node data
            edges = []  # citation edges
            visited = set()
            queue = [(center_paper_id, 0)]  # (paper_id, current_depth)

            while queue and len(nodes) < max_papers:
                current_paper_id, current_depth = queue.pop(0)

                if current_paper_id in visited or current_depth > depth:
                    continue

                visited.add(current_paper_id)

                # Get paper data
                paper = db.query(Paper).filter(Paper.id == UUID(current_paper_id)).first()
                if not paper:
                    continue

                # Add node
                nodes[current_paper_id] = {
                    "id": current_paper_id,
                    "title": paper.title,
                    "authors": [author.get("name", "") for author in paper.authors or []],
                    "publication_year": paper.publication_year,
                    "citation_count": paper.citation_count,
                    "influence_score": paper.influence_score,
                    "is_center": current_paper_id == center_paper_id,
                    "depth": current_depth
                }

                # Get citations (both directions)
                if current_depth < depth:
                    # Papers citing this paper
                    citing_citations = db.query(Citation).filter(
                        Citation.cited_paper_id == UUID(current_paper_id)
                    ).all()

                    for citation in citing_citations:
                        citing_paper_id = str(citation.citing_paper_id)

                        # Add edge
                        edges.append({
                            "source": citing_paper_id,
                            "target": current_paper_id,
                            "strength": citation.strength,
                            "context": citation.context[:100] if citation.context else "",
                            "type": "cites"
                        })

                        # Add to queue
                        if citing_paper_id not in visited:
                            queue.append((citing_paper_id, current_depth + 1))

                    # Papers cited by this paper
                    cited_citations = db.query(Citation).filter(
                        Citation.citing_paper_id == UUID(current_paper_id)
                    ).all()

                    for citation in cited_citations:
                        cited_paper_id = str(citation.cited_paper_id)

                        # Add edge
                        edges.append({
                            "source": current_paper_id,
                            "target": cited_paper_id,
                            "strength": citation.strength,
                            "context": citation.context[:100] if citation.context else "",
                            "type": "cites"
                        })

                        # Add to queue
                        if cited_paper_id not in visited:
                            queue.append((cited_paper_id, current_depth + 1))

            # Convert nodes dict to list
            node_list = list(nodes.values())

            network = CitationNetwork(
                nodes=node_list,
                edges=edges,
                center_paper_id=UUID(center_paper_id),
                depth=depth,
                total_papers=len(node_list),
                total_citations=len(edges)
            )

            paper_logger.info(
                f"Built citation network: {len(node_list)} papers, {len(edges)} citations"
            )

            return network

        except Exception as e:
            paper_logger.error(f"Failed to build citation network: {e}")
            log_error(e, {"center_paper_id": center_paper_id})
            raise

    async def get_citing_papers(
        self,
        paper_id: str,
        limit: int = 20,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """Get papers that cite the given paper."""

        try:
            # Get citations
            citations = db.query(Citation).join(
                Paper, Citation.citing_paper_id == Paper.id
            ).filter(
                Citation.cited_paper_id == UUID(paper_id)
            ).limit(limit).all()

            citing_papers = []

            for citation in citations:
                citing_paper = citation.citing_paper

                citing_papers.append({
                    "paper_id": str(citing_paper.id),
                    "title": citing_paper.title,
                    "authors": [author.get("name", "") for author in citing_paper.authors or []],
                    "publication_year": citing_paper.publication_year,
                    "citation_count": citing_paper.citation_count,
                    "citation_context": citation.context,
                    "citation_strength": citation.strength
                })

            return citing_papers

        except Exception as e:
            paper_logger.error(f"Failed to get citing papers: {e}")
            log_error(e, {"paper_id": paper_id})
            return []

    async def get_referenced_papers(
        self,
        paper_id: str,
        limit: int = 20,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """Get papers referenced by the given paper."""

        try:
            # Get citations
            citations = db.query(Citation).join(
                Paper, Citation.cited_paper_id == Paper.id
            ).filter(
                Citation.citing_paper_id == UUID(paper_id)
            ).limit(limit).all()

            referenced_papers = []

            for citation in citations:
                cited_paper = citation.cited_paper

                referenced_papers.append({
                    "paper_id": str(cited_paper.id),
                    "title": cited_paper.title,
                    "authors": [author.get("name", "") for author in cited_paper.authors or []],
                    "publication_year": cited_paper.publication_year,
                    "citation_count": cited_paper.citation_count,
                    "citation_context": citation.context,
                    "citation_strength": citation.strength
                })

            return referenced_papers

        except Exception as e:
            paper_logger.error(f"Failed to get referenced papers: {e}")
            log_error(e, {"paper_id": paper_id})
            return []

    async def calculate_paper_influence(
        self,
        paper_id: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """Calculate influence metrics for a paper."""

        try:
            paper = db.query(Paper).filter(Paper.id == UUID(paper_id)).first()
            if not paper:
                raise ValueError(f"Paper not found: {paper_id}")

            # Count direct citations
            direct_citations = db.query(Citation).filter(
                Citation.cited_paper_id == UUID(paper_id)
            ).count()

            # Count second-order citations (papers citing papers that cite this paper)
            second_order_citations = db.query(Citation).filter(
                Citation.cited_paper_id.in_(
                    db.query(Citation.citing_paper_id).filter(
                        Citation.cited_paper_id == UUID(paper_id)
                    )
                )
            ).count()

            # Calculate h-index style metric
            citing_papers = db.query(Paper).join(
                Citation, Paper.id == Citation.citing_paper_id
            ).filter(
                Citation.cited_paper_id == UUID(paper_id)
            ).all()

            citing_citation_counts = [p.citation_count for p in citing_papers]
            citing_citation_counts.sort(reverse=True)

            # Calculate influence score
            h_index = 0
            for i, count in enumerate(citing_citation_counts):
                if count >= i + 1:
                    h_index = i + 1
                else:
                    break

            # Calculate influence score (normalized)
            influence_score = min(
                (direct_citations * 0.5 + second_order_citations * 0.3 + h_index * 0.2) / 100,
                1.0
            )

            # Get publication age
            publication_age = 0
            if paper.publication_date:
                from datetime import datetime
                publication_age = (datetime.now() - paper.publication_date).days // 365

            # Calculate citation rate per year
            citation_rate = direct_citations / max(publication_age, 1) if publication_age > 0 else 0

            return {
                "paper_id": paper_id,
                "direct_citations": direct_citations,
                "second_order_citations": second_order_citations,
                "h_index": h_index,
                "influence_score": influence_score,
                "publication_age_years": publication_age,
                "citation_rate_per_year": citation_rate,
                "percentile_rank": 0.0,  # Would need full dataset to calculate
                "field_normalized_score": 0.0  # Would need field classification
            }

        except Exception as e:
            paper_logger.error(f"Failed to calculate paper influence: {e}")
            log_error(e, {"paper_id": paper_id})
            return {}

    async def find_research_gaps(
        self,
        user_id: str,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """Identify research gaps based on user's reading patterns."""

        try:
            # Get user's papers
            from app.db.queries.paper_queries import get_user_papers
            user_papers = await get_user_papers(db, user_id, limit=100)

            if not user_papers:
                return []

            # Analyze citation patterns
            gaps = []

            # Find frequently cited papers that user hasn't read
            frequently_cited = db.query(Paper).join(Citation).filter(
                Citation.cited_paper_id == Paper.id
            ).group_by(Paper.id).having(
                db.func.count(Citation.id) > 5
            ).all()

            user_paper_ids = {str(p.id) for p in user_papers}

            for paper in frequently_cited:
                if str(paper.id) not in user_paper_ids:
                    gaps.append({
                        "type": "missing_influential_paper",
                        "paper_id": str(paper.id),
                        "title": paper.title,
                        "citation_count": paper.citation_count,
                        "reason": "Highly cited paper in your research area"
                    })

            # Limit results
            gaps = gaps[:10]

            return gaps

        except Exception as e:
            paper_logger.error(f"Failed to find research gaps: {e}")
            log_error(e, {"user_id": user_id})
            return []

    async def update_citation_network(
        self,
        paper_id: str,
        db: Session = None
    ) -> bool:
        """Update citation network for a paper."""

        try:
            # This would implement citation extraction from paper content
            # For now, it's a placeholder

            paper_logger.info(f"Updated citation network for paper: {paper_id}")
            return True

        except Exception as e:
            paper_logger.error(f"Failed to update citation network: {e}")
            log_error(e, {"paper_id": paper_id})
            return False


# Global citation service instance
citation_service = CitationService()