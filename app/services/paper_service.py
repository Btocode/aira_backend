"""
Paper processing and management service.
"""
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import re

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.app_logging import paper_logger, log_paper_processed, log_error
from app.db.models import Paper, UserPaper, ProcessingStatus, PaperSource, ReadingStatus
from app.db.queries.paper_queries import (
    create_paper, get_paper_by_doi, get_paper_by_arxiv_id, get_paper_by_url,
    update_paper, update_paper_processing_status, create_user_paper,
    get_user_paper, search_papers, get_user_papers
)
from app.services.ai_service import ai_service
from app.services.pdf_processor import pdf_processor
from app.schemas.paper import PaperCreate, PaperInDB, PaperSearchRequest


class PaperService:
    """Service for paper processing and management."""

    def __init__(self):
        """Initialize paper service."""
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def process_paper_from_url(
        self,
        url: str,
        user_id: str,
        db: Session
    ) -> Tuple[Paper, bool]:
        """Process paper from URL and add to user's library."""

        paper_logger.info(f"Processing paper from URL: {url}")
        start_time = datetime.now()

        try:
            # 1. Extract paper metadata and determine source
            paper_data, source = await self._extract_paper_metadata(url)

            # 2. Check if paper already exists
            existing_paper = await self._find_existing_paper(db, paper_data, url)

            if existing_paper:
                paper_logger.info(f"Paper already exists: {existing_paper.id}")

                # Add to user's library if not already there
                user_paper = await get_user_paper(db, user_id, str(existing_paper.id))
                if not user_paper:
                    await create_user_paper(db, user_id, str(existing_paper.id))
                    paper_logger.info(f"Added existing paper to user library: {user_id}")

                return existing_paper, False  # Not newly created

            # 3. Create new paper record
            paper_data.update({
                "url": url,
                "source": source,
                "processing_status": ProcessingStatus.PENDING
            })

            paper = await create_paper(db, paper_data)

            # 4. Add to user's library
            await create_user_paper(db, user_id, str(paper.id))

            # 5. Queue for AI processing
            from app.services.celery_app import process_paper_task
            process_paper_task.delay(str(paper.id))

            processing_time = (datetime.now() - start_time).total_seconds()
            log_paper_processed(str(paper.id), processing_time, "queued")

            paper_logger.info(f"Paper queued for processing: {paper.id}")
            return paper, True  # Newly created

        except Exception as e:
            paper_logger.error(f"Failed to process paper from URL {url}: {e}")
            log_error(e, {"url": url, "user_id": user_id})
            raise

    async def process_paper_content(self, paper_id: str, db: Session) -> bool:
        """Process paper content with AI (called by background worker)."""

        paper_logger.info(f"Starting AI processing for paper: {paper_id}")
        start_time = datetime.now()

        try:
            # Get paper from database
            from app.db.queries.paper_queries import get_paper_by_id
            paper = await get_paper_by_id(db, paper_id)

            if not paper:
                raise ValueError(f"Paper not found: {paper_id}")

            # Update status to processing
            await update_paper_processing_status(
                db, paper_id, ProcessingStatus.PROCESSING
            )

            # Extract full text if needed
            if not paper.full_text and paper.pdf_url:
                paper_logger.info(f"Extracting text from PDF: {paper.pdf_url}")

                full_text = await pdf_processor.extract_text_from_url(paper.pdf_url)

                if full_text:
                    await update_paper(db, paper_id, {"full_text": full_text})
                    paper.full_text = full_text

            # Prepare content for AI processing
            content = self._prepare_content_for_ai(paper)

            if not content:
                raise ValueError("No content available for AI processing")

            # Generate AI analysis
            ai_results = await self._generate_ai_analysis(paper, content)

            # Update paper with AI results
            await update_paper(db, paper_id, ai_results)

            # Mark as completed
            await update_paper_processing_status(
                db, paper_id, ProcessingStatus.COMPLETED
            )

            processing_time = (datetime.now() - start_time).total_seconds()
            log_paper_processed(paper_id, processing_time, "completed")

            paper_logger.info(f"Paper processing completed: {paper_id}")
            return True

        except Exception as e:
            paper_logger.error(f"Failed to process paper {paper_id}: {e}")

            # Mark as failed
            await update_paper_processing_status(
                db, paper_id, ProcessingStatus.FAILED, str(e)
            )

            log_error(e, {"paper_id": paper_id})
            return False

    async def search_user_papers(
        self,
        user_id: str,
        search_request: PaperSearchRequest,
        db: Session
    ) -> Dict[str, Any]:
        """Search papers in user's library."""

        paper_logger.info(f"Searching papers for user {user_id}: {search_request.query}")

        try:
            start_time = datetime.now()

            # Perform search
            papers = await search_papers(
                db=db,
                query=search_request.query,
                user_id=user_id,
                filters=search_request.filters,
                sort_by=search_request.sort_by,
                sort_order=search_request.sort_order,
                limit=search_request.limit,
                offset=search_request.offset
            )

            # Get total count (for pagination)
            total_count = await self._count_search_results(
                db, search_request.query, user_id, search_request.filters
            )

            search_time = (datetime.now() - start_time).total_seconds()

            # Calculate pagination info
            page = (search_request.offset // search_request.limit) + 1
            has_next = search_request.offset + search_request.limit < total_count
            has_prev = search_request.offset > 0

            result = {
                "papers": papers,
                "total": total_count,
                "query": search_request.query,
                "filters": search_request.filters,
                "took_ms": int(search_time * 1000),
                "page": page,
                "per_page": search_request.limit,
                "has_next": has_next,
                "has_prev": has_prev
            }

            paper_logger.info(
                f"Search completed: {len(papers)} results in {search_time:.2f}s"
            )

            return result

        except Exception as e:
            paper_logger.error(f"Search failed for user {user_id}: {e}")
            log_error(e, {"user_id": user_id, "query": search_request.query})
            raise

    async def get_paper_recommendations(
        self,
        user_id: str,
        paper_id: Optional[str],
        db: Session,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get paper recommendations for user."""

        paper_logger.info(f"Getting recommendations for user {user_id}")

        try:
            recommendations = []

            # Get user's reading history
            user_papers = await get_user_papers(
                db, user_id, status=ReadingStatus.COMPLETED, limit=50
            )

            if not user_papers:
                # New user - return popular papers
                from app.db.queries.paper_queries import get_popular_papers
                popular_papers = await get_popular_papers(db, limit)

                recommendations = [
                    {
                        "paper": paper,
                        "relevance_score": 0.5,
                        "reason": "Popular paper in the community",
                        "recommendation_type": "popular"
                    }
                    for paper in popular_papers
                ]
            else:
                # Generate personalized recommendations
                recommendations = await self._generate_personalized_recommendations(
                    db, user_papers, limit
                )

            paper_logger.info(f"Generated {len(recommendations)} recommendations")
            return recommendations

        except Exception as e:
            paper_logger.error(f"Failed to get recommendations for user {user_id}: {e}")
            log_error(e, {"user_id": user_id})
            return []

    async def update_reading_progress(
        self,
        user_id: str,
        paper_id: str,
        progress_data: Dict[str, Any],
        db: Session
    ) -> Optional[UserPaper]:
        """Update user's reading progress for a paper."""

        try:
            from app.db.queries.paper_queries import update_user_paper

            # Update reading progress
            user_paper = await update_user_paper(
                db, user_id, paper_id, progress_data
            )

            if user_paper:
                paper_logger.info(
                    f"Reading progress updated: {user_id} -> {paper_id} "
                    f"({progress_data.get('reading_progress', 0)}%)"
                )

            return user_paper

        except Exception as e:
            paper_logger.error(f"Failed to update reading progress: {e}")
            log_error(e, {"user_id": user_id, "paper_id": paper_id})
            return None

    # Private helper methods
    async def _extract_paper_metadata(self, url: str) -> Tuple[Dict[str, Any], PaperSource]:
        """Extract paper metadata from URL."""

        if "arxiv.org" in url:
            return await self._extract_arxiv_metadata(url), PaperSource.ARXIV
        elif "pubmed.ncbi.nlm.nih.gov" in url:
            return await self._extract_pubmed_metadata(url), PaperSource.JOURNAL
        elif url.endswith('.pdf'):
            return await self._extract_pdf_metadata(url), PaperSource.PDF_UPLOAD
        else:
            return await self._extract_generic_metadata(url), PaperSource.URL

    async def _extract_arxiv_metadata(self, url: str) -> Dict[str, Any]:
        """Extract metadata from arXiv URL."""

        # Extract arXiv ID
        arxiv_id = re.search(r'arxiv\.org/abs/([^/?]+)', url)
        if not arxiv_id:
            raise ValueError(f"Invalid arXiv URL: {url}")

        arxiv_id = arxiv_id.group(1)

        # Fetch metadata from arXiv API
        api_url = f"{settings.arxiv_api_base}?id_list={arxiv_id}"

        async with self.http_client as client:
            response = await client.get(api_url)
            response.raise_for_status()

            xml_content = response.text

        # Parse XML response
        metadata = self._parse_arxiv_xml(xml_content)
        metadata.update({
            "arxiv_id": arxiv_id,
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        })

        return metadata

    def _parse_arxiv_xml(self, xml_content: str) -> Dict[str, Any]:
        """Parse arXiv API XML response."""

        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_content)

        # Find entry element
        entry = root.find(".//{http://www.w3.org/2005/Atom}entry")
        if entry is None:
            raise ValueError("No entry found in arXiv response")

        # Extract metadata
        title_elem = entry.find(".//{http://www.w3.org/2005/Atom}title")
        title = title_elem.text.strip() if title_elem is not None else ""

        summary_elem = entry.find(".//{http://www.w3.org/2005/Atom}summary")
        abstract = summary_elem.text.strip() if summary_elem is not None else ""

        # Extract authors
        authors = []
        for author_elem in entry.findall(".//{http://www.w3.org/2005/Atom}author"):
            name_elem = author_elem.find(".//{http://www.w3.org/2005/Atom}name")
            if name_elem is not None:
                authors.append({"name": name_elem.text.strip()})

        # Extract categories (keywords)
        keywords = []
        for category_elem in entry.findall(".//{http://arxiv.org/schemas/atom}category"):
            term = category_elem.get("term")
            if term:
                keywords.append(term)

        # Extract publication date
        published_elem = entry.find(".//{http://www.w3.org/2005/Atom}published")
        publication_date = None
        publication_year = None

        if published_elem is not None:
            try:
                publication_date = datetime.fromisoformat(
                    published_elem.text.replace('Z', '+00:00')
                )
                publication_year = publication_date.year
            except ValueError:
                pass

        return {
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "keywords": keywords,
            "publication_date": publication_date,
            "publication_year": publication_year
        }

    async def _extract_pubmed_metadata(self, url: str) -> Dict[str, Any]:
        """Extract metadata from PubMed URL."""

        # Extract PMID
        pmid_match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url)
        if not pmid_match:
            raise ValueError(f"Invalid PubMed URL: {url}")

        pmid = pmid_match.group(1)

        # Use NCBI E-utilities API
        api_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "json"
        }

        async with self.http_client as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()

            data = response.json()

        # Parse response
        result = data.get("result", {}).get(pmid, {})

        authors = []
        if "authors" in result:
            for author in result["authors"]:
                authors.append({"name": author.get("name", "")})

        return {
            "title": result.get("title", ""),
            "abstract": "",  # Abstract requires separate API call
            "authors": authors,
            "journal": result.get("source", ""),
            "publication_date": self._parse_pubmed_date(result.get("pubdate", "")),
            "pmid": pmid
        }

    def _parse_pubmed_date(self, date_str: str) -> Optional[datetime]:
        """Parse PubMed date string."""

        if not date_str:
            return None

        try:
            # Handle various PubMed date formats
            if len(date_str) == 4:  # Year only
                return datetime(int(date_str), 1, 1)
            elif "/" in date_str:  # MM/DD/YYYY or similar
                parts = date_str.split("/")
                if len(parts) >= 3:
                    return datetime(int(parts[2]), int(parts[0]), int(parts[1]))

            return None
        except (ValueError, IndexError):
            return None

    async def _extract_pdf_metadata(self, url: str) -> Dict[str, Any]:
        """Extract metadata from PDF URL."""

        try:
            # Download and process PDF
            metadata = await pdf_processor.extract_metadata_from_url(url)

            return {
                "title": metadata.get("title", "PDF Document"),
                "authors": metadata.get("authors", []),
                "abstract": metadata.get("abstract", ""),
                "pdf_url": url
            }

        except Exception as e:
            paper_logger.warning(f"Failed to extract PDF metadata: {e}")

            # Return minimal metadata
            return {
                "title": "PDF Document",
                "authors": [],
                "abstract": "",
                "pdf_url": url
            }

    async def _extract_generic_metadata(self, url: str) -> Dict[str, Any]:
        """Extract metadata from generic URL."""

        try:
            async with self.http_client as client:
                response = await client.get(url)
                response.raise_for_status()

                html_content = response.text

            # Extract basic metadata from HTML
            metadata = self._parse_html_metadata(html_content)

            return metadata

        except Exception as e:
            paper_logger.warning(f"Failed to extract generic metadata: {e}")

            return {
                "title": "Academic Paper",
                "authors": [],
                "abstract": ""
            }

    def _parse_html_metadata(self, html_content: str) -> Dict[str, Any]:
        """Parse metadata from HTML content."""

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract title
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()

        # Look for meta tags
        meta_title = soup.find('meta', {'name': 'citation_title'})
        if meta_title:
            title = meta_title.get('content', title)

        # Extract authors
        authors = []
        author_metas = soup.find_all('meta', {'name': 'citation_author'})
        for meta in author_metas:
            author_name = meta.get('content', '').strip()
            if author_name:
                authors.append({"name": author_name})

        # Extract abstract
        abstract = ""
        abstract_meta = soup.find('meta', {'name': 'citation_abstract'})
        if abstract_meta:
            abstract = abstract_meta.get('content', '')

        return {
            "title": title,
            "authors": authors,
            "abstract": abstract
        }

    async def _find_existing_paper(
        self,
        db: Session,
        paper_data: Dict[str, Any],
        url: str
    ) -> Optional[Paper]:
        """Find existing paper in database."""

        # Check by DOI
        if paper_data.get("doi"):
            paper = await get_paper_by_doi(db, paper_data["doi"])
            if paper:
                return paper

        # Check by arXiv ID
        if paper_data.get("arxiv_id"):
            paper = await get_paper_by_arxiv_id(db, paper_data["arxiv_id"])
            if paper:
                return paper

        # Check by URL
        paper = await get_paper_by_url(db, url)
        if paper:
            return paper

        return None

    def _prepare_content_for_ai(self, paper: Paper) -> str:
        """Prepare paper content for AI processing."""

        content_parts = []

        if paper.title:
            content_parts.append(f"Title: {paper.title}")

        if paper.abstract:
            content_parts.append(f"Abstract: {paper.abstract}")

        if paper.full_text:
            content_parts.append(f"Full Text: {paper.full_text}")
        elif paper.abstract:
            # Use abstract if no full text available
            content_parts.append(f"Content: {paper.abstract}")

        return "\n\n".join(content_parts)

    async def _generate_ai_analysis(
        self,
        paper: Paper,
        content: str
    ) -> Dict[str, Any]:
        """Generate AI analysis for paper."""

        # Get author names
        authors = [author.get("name", "") for author in paper.authors or []]

        # Generate summary
        summary = await ai_service.summarize_paper(
            content, paper.title, authors
        )

        # Extract insights
        insights = await ai_service.extract_key_insights(
            content, paper.title
        )

        # Analyze methodology
        methodology = await ai_service.analyze_methodology(
            content, paper.title
        )

        # Identify limitations
        limitations = await ai_service.identify_limitations(
            content, paper.title
        )

        # Extract contributions
        contributions = await ai_service.extract_contributions(
            content, paper.title
        )

        return {
            "summary": summary.dict(),
            "key_insights": [insight.dict() for insight in insights],
            "methodology": methodology,
            "limitations": limitations,
            "contributions": [contrib.dict() for contrib in contributions]
        }

    async def _count_search_results(
        self,
        db: Session,
        query: str,
        user_id: str,
        filters: Optional[Dict[str, Any]]
    ) -> int:
        """Count total search results for pagination."""

        # This would be implemented similar to search_papers but with count()
        # For now, return estimated count
        return 100  # Placeholder

    async def _generate_personalized_recommendations(
        self,
        db: Session,
        user_papers: List[Paper],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Generate personalized recommendations based on user's reading history."""

        recommendations = []

        # Extract keywords from user's papers
        user_keywords = set()
        for paper in user_papers:
            if paper.keywords:
                user_keywords.update(paper.keywords)

        # Find similar papers (simplified implementation)
        if user_keywords:
            # Search for papers with similar keywords
            similar_papers = await search_papers(
                db=db,
                query=" ".join(list(user_keywords)[:5]),  # Use top 5 keywords
                limit=limit * 2  # Get more to filter
            )

            # Filter out papers user already has
            user_paper_ids = {str(paper.id) for paper in user_papers}

            for paper in similar_papers:
                if str(paper.id) not in user_paper_ids:
                    recommendations.append({
                        "paper": paper,
                        "relevance_score": 0.7,
                        "reason": "Similar to your reading interests",
                        "recommendation_type": "similar_topic"
                    })

                if len(recommendations) >= limit:
                    break

        return recommendations


# Global paper service instance
paper_service = PaperService()