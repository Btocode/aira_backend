"""
Knowledge base management service.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.db.models import KnowledgeEntry, EntryType
from app.schemas.knowledge import KnowledgeEntryCreate, KnowledgeEntryUpdate, KnowledgeSearchRequest
from app.services.ai_service import ai_service
from app.core.app_logging import paper_logger, log_error


class KnowledgeService:
    """Service for knowledge base management."""

    async def get_user_knowledge_entries(
        self,
        user_id: str,
        entry_type: Optional[str] = None,
        paper_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        db: Session = None
    ) -> List[KnowledgeEntry]:
        """Get knowledge entries for a user."""

        try:
            query = db.query(KnowledgeEntry).filter(
                KnowledgeEntry.user_id == UUID(user_id)
            )

            # Filter by entry type
            if entry_type:
                try:
                    entry_type_enum = EntryType(entry_type)
                    query = query.filter(KnowledgeEntry.entry_type == entry_type_enum)
                except ValueError:
                    paper_logger.warning(f"Invalid entry type: {entry_type}")

            # Filter by paper
            if paper_id:
                query = query.filter(KnowledgeEntry.paper_id == UUID(paper_id))

            # Order by creation date (newest first)
            query = query.order_by(desc(KnowledgeEntry.created_at))

            # Apply pagination
            entries = query.offset(offset).limit(limit).all()

            paper_logger.info(f"Retrieved {len(entries)} knowledge entries for user {user_id}")
            return entries

        except Exception as e:
            paper_logger.error(f"Failed to get knowledge entries for user {user_id}: {e}")
            log_error(e, {"user_id": user_id})
            return []

    async def create_knowledge_entry(
        self,
        user_id: str,
        entry_data: KnowledgeEntryCreate,
        db: Session
    ) -> KnowledgeEntry:
        """Create a new knowledge entry."""

        try:
            # Create knowledge entry
            entry = KnowledgeEntry(
                user_id=UUID(user_id),
                paper_id=UUID(entry_data.paper_id) if entry_data.paper_id else None,
                title=entry_data.title,
                content=entry_data.content,
                entry_type=entry_data.entry_type,
                tags=entry_data.tags,
                section_reference=entry_data.section_reference,
                page_number=entry_data.page_number
            )

            db.add(entry)
            db.commit()
            db.refresh(entry)

            # Generate AI summary for longer entries
            if len(entry_data.content) > 500:
                try:
                    summary = await self._generate_entry_summary(entry_data.content)
                    entry.summary = summary
                    db.commit()
                    db.refresh(entry)
                except Exception as e:
                    paper_logger.warning(f"Failed to generate summary for entry {entry.id}: {e}")

            paper_logger.info(f"Created knowledge entry {entry.id} for user {user_id}")
            return entry

        except Exception as e:
            paper_logger.error(f"Failed to create knowledge entry for user {user_id}: {e}")
            log_error(e, {"user_id": user_id})
            db.rollback()
            raise

    async def get_knowledge_entry(
        self,
        entry_id: str,
        user_id: str,
        db: Session
    ) -> Optional[KnowledgeEntry]:
        """Get a specific knowledge entry."""

        try:
            entry = db.query(KnowledgeEntry).filter(
                and_(
                    KnowledgeEntry.id == UUID(entry_id),
                    KnowledgeEntry.user_id == UUID(user_id)
                )
            ).first()

            return entry

        except Exception as e:
            paper_logger.error(f"Failed to get knowledge entry {entry_id}: {e}")
            log_error(e, {"entry_id": entry_id, "user_id": user_id})
            return None

    async def update_knowledge_entry(
        self,
        entry_id: str,
        user_id: str,
        entry_update: KnowledgeEntryUpdate,
        db: Session
    ) -> Optional[KnowledgeEntry]:
        """Update a knowledge entry."""

        try:
            # Get entry
            entry = await self.get_knowledge_entry(entry_id, user_id, db)
            if not entry:
                return None

            # Update fields
            update_data = entry_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(entry, field):
                    setattr(entry, field, value)

            entry.updated_at = datetime.utcnow()

            # Regenerate summary if content was updated
            if "content" in update_data and len(entry.content) > 500:
                try:
                    summary = await self._generate_entry_summary(entry.content)
                    entry.summary = summary
                except Exception as e:
                    paper_logger.warning(f"Failed to update summary for entry {entry.id}: {e}")

            db.commit()
            db.refresh(entry)

            paper_logger.info(f"Updated knowledge entry {entry_id} for user {user_id}")
            return entry

        except Exception as e:
            paper_logger.error(f"Failed to update knowledge entry {entry_id}: {e}")
            log_error(e, {"entry_id": entry_id, "user_id": user_id})
            db.rollback()
            return None

    async def delete_knowledge_entry(
        self,
        entry_id: str,
        user_id: str,
        db: Session
    ) -> bool:
        """Delete a knowledge entry."""

        try:
            # Get entry
            entry = await self.get_knowledge_entry(entry_id, user_id, db)
            if not entry:
                return False

            # Delete entry
            db.delete(entry)
            db.commit()

            paper_logger.info(f"Deleted knowledge entry {entry_id} for user {user_id}")
            return True

        except Exception as e:
            paper_logger.error(f"Failed to delete knowledge entry {entry_id}: {e}")
            log_error(e, {"entry_id": entry_id, "user_id": user_id})
            db.rollback()
            return False

    async def search_knowledge_entries(
        self,
        user_id: str,
        search_request: KnowledgeSearchRequest,
        db: Session
    ) -> Dict[str, Any]:
        """Search knowledge entries using text and semantic search."""

        paper_logger.info(f"Searching knowledge for user {user_id}: {search_request.query}")
        start_time = datetime.now()

        try:
            # Build base query
            query = db.query(KnowledgeEntry).filter(
                KnowledgeEntry.user_id == UUID(user_id)
            )

            # Add text search
            if search_request.query:
                search_filter = or_(
                    KnowledgeEntry.title.ilike(f"%{search_request.query}%"),
                    KnowledgeEntry.content.ilike(f"%{search_request.query}%"),
                    KnowledgeEntry.summary.ilike(f"%{search_request.query}%")
                )
                query = query.filter(search_filter)

            # Filter by entry types
            if search_request.entry_types:
                query = query.filter(KnowledgeEntry.entry_type.in_(search_request.entry_types))

            # Filter by tags
            if search_request.tags:
                for tag in search_request.tags:
                    query = query.filter(KnowledgeEntry.tags.astext.ilike(f"%{tag}%"))

            # Filter by paper
            if search_request.paper_id:
                query = query.filter(KnowledgeEntry.paper_id == search_request.paper_id)

            # Order by relevance (simplified - you'd implement proper scoring)
            query = query.order_by(desc(KnowledgeEntry.updated_at))

            # Get total count
            total_count = query.count()

            # Apply pagination
            entries = query.offset(search_request.offset).limit(search_request.limit).all()

            search_time = (datetime.now() - start_time).total_seconds()

            paper_logger.info(
                f"Knowledge search completed: {len(entries)} results in {search_time:.2f}s"
            )

            return {
                "entries": entries,
                "total": total_count,
                "query": search_request.query,
                "took_ms": int(search_time * 1000)
            }

        except Exception as e:
            paper_logger.error(f"Knowledge search failed for user {user_id}: {e}")
            log_error(e, {"user_id": user_id, "query": search_request.query})
            return {
                "entries": [],
                "total": 0,
                "query": search_request.query,
                "took_ms": 0
            }

    async def get_knowledge_stats(
        self,
        user_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """Get knowledge base statistics for a user."""

        try:
            # Total entries
            total_entries = db.query(KnowledgeEntry).filter(
                KnowledgeEntry.user_id == UUID(user_id)
            ).count()

            # Entries by type
            entries_by_type = {}
            for entry_type in EntryType:
                count = db.query(KnowledgeEntry).filter(
                    and_(
                        KnowledgeEntry.user_id == UUID(user_id),
                        KnowledgeEntry.entry_type == entry_type
                    )
                ).count()
                entries_by_type[entry_type.value] = count

            # Recent entries (last 7 days)
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            recent_entries = db.query(KnowledgeEntry).filter(
                and_(
                    KnowledgeEntry.user_id == UUID(user_id),
                    KnowledgeEntry.created_at >= recent_cutoff
                )
            ).count()

            # Tag statistics
            all_entries = db.query(KnowledgeEntry).filter(
                KnowledgeEntry.user_id == UUID(user_id)
            ).all()

            tag_counts = {}
            for entry in all_entries:
                if entry.tags:
                    for tag in entry.tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1

            # Most used tags
            most_used_tags = [
                {"tag": tag, "count": count}
                for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]

            return {
                "total_entries": total_entries,
                "entries_by_type": entries_by_type,
                "recent_entries": recent_entries,
                "total_tags": len(tag_counts),
                "most_used_tags": most_used_tags
            }

        except Exception as e:
            paper_logger.error(f"Failed to get knowledge stats for user {user_id}: {e}")
            log_error(e, {"user_id": user_id})
            return {}

    async def find_related_entries(
        self,
        entry_id: str,
        user_id: str,
        db: Session,
        limit: int = 5
    ) -> List[KnowledgeEntry]:
        """Find entries related to a given entry."""

        try:
            # Get the source entry
            source_entry = await self.get_knowledge_entry(entry_id, user_id, db)
            if not source_entry:
                return []

            # Find related entries based on tags and content similarity
            query = db.query(KnowledgeEntry).filter(
                and_(
                    KnowledgeEntry.user_id == UUID(user_id),
                    KnowledgeEntry.id != UUID(entry_id)
                )
            )

            # Filter by shared tags
            if source_entry.tags:
                tag_filters = []
                for tag in source_entry.tags:
                    tag_filters.append(KnowledgeEntry.tags.astext.ilike(f"%{tag}%"))

                if tag_filters:
                    query = query.filter(or_(*tag_filters))

            # Order by creation date (you'd implement proper similarity scoring)
            related_entries = query.order_by(desc(KnowledgeEntry.created_at)).limit(limit).all()

            return related_entries

        except Exception as e:
            paper_logger.error(f"Failed to find related entries for {entry_id}: {e}")
            log_error(e, {"entry_id": entry_id, "user_id": user_id})
            return []

    async def _generate_entry_summary(self, content: str) -> str:
        """Generate AI summary for knowledge entry."""

        try:
            # Create prompt for summarization
            prompt = f"""
            Summarize this knowledge entry in 1-2 sentences, focusing on the key points:

            {content[:2000]}  # Limit content length

            Make the summary concise but informative.
            """

            # Use AI service to generate summary
            from openai import AsyncOpenAI
            from app.core.config import settings

            client = AsyncOpenAI(api_key=settings.openai_api_key)

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100
            )

            summary = response.choices[0].message.content.strip()

            paper_logger.info("Generated summary for knowledge entry")
            return summary

        except Exception as e:
            paper_logger.error(f"Failed to generate entry summary: {e}")
            return ""


# Global knowledge service instance
knowledge_service = KnowledgeService()