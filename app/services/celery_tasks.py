"""
Celery task definitions for background processing.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

from celery import current_task
from sqlalchemy.orm import Session

from app.services.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.models import Paper, ProcessingStatus, ProcessingTask
from app.core.app_logging import paper_logger, log_paper_processed, log_error


def run_async(coro):
    """Helper to run async functions in Celery tasks."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(coro)
    finally:
        # Don't close the loop as it might be reused
        pass


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_paper_task(self, paper_id: str):
    """Background task to process a paper with AI."""

    paper_logger.info(f"Starting paper processing task for: {paper_id}")
    task_id = self.request.id

    try:
        # Create database session
        db = SessionLocal()

        try:
            # Update task status
            update_task_status(db, task_id, "running", paper_id=paper_id)

            # Import here to avoid circular imports
            from app.services.paper_service import paper_service

            # Process paper (convert async to sync)
            success = run_async(paper_service.process_paper_content(paper_id, db))

            if success:
                paper_logger.info(f"Paper processing completed successfully: {paper_id}")
                update_task_status(
                    db, task_id, "completed",
                    result={"status": "completed", "paper_id": paper_id},
                    paper_id=paper_id
                )
                return {"status": "completed", "paper_id": paper_id}
            else:
                paper_logger.error(f"Paper processing failed: {paper_id}")
                update_task_status(
                    db, task_id, "failed",
                    error="Processing failed",
                    paper_id=paper_id
                )
                return {"status": "failed", "paper_id": paper_id}

        finally:
            db.close()

    except Exception as exc:
        paper_logger.error(f"Paper processing task failed for {paper_id}: {exc}")
        log_error(exc, {"paper_id": paper_id, "task_id": task_id})

        # Update task status
        try:
            db = SessionLocal()
            update_task_status(db, task_id, "failed", error=str(exc), paper_id=paper_id)
            db.close()
        except Exception:
            pass

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries * 60  # Exponential backoff
            paper_logger.info(f"Retrying paper processing in {countdown} seconds")
            raise self.retry(countdown=countdown)

        # Max retries reached - update paper status to failed
        try:
            db = SessionLocal()
            from app.db.queries.paper_queries import update_paper_processing_status

            run_async(update_paper_processing_status(
                db, paper_id, ProcessingStatus.FAILED, str(exc)
            ))
            db.close()

        except Exception as update_exc:
            paper_logger.error(f"Failed to update paper status: {update_exc}")

        raise exc


@celery_app.task(bind=True)
def generate_embeddings_task(self, paper_id: str, content: str):
    """Generate embeddings for a paper."""

    paper_logger.info(f"Generating embeddings for paper: {paper_id}")

    try:
        from app.services.ai_service import ai_service

        # Generate embeddings
        embeddings = run_async(ai_service.generate_embeddings(content))

        # Store embeddings (you'd implement vector storage here)
        # For now, just log success
        paper_logger.info(f"Generated embeddings for paper {paper_id}: {len(embeddings)} dimensions")

        return {"status": "completed", "paper_id": paper_id, "embedding_size": len(embeddings)}

    except Exception as exc:
        paper_logger.error(f"Embedding generation failed for {paper_id}: {exc}")
        raise


@celery_app.task
def process_pending_papers_task():
    """Process papers with pending status."""

    paper_logger.info("Processing pending papers...")

    try:
        db = SessionLocal()

        try:
            from app.db.queries.paper_queries import get_papers_by_processing_status

            # Get pending papers
            pending_papers = run_async(get_papers_by_processing_status(
                db, ProcessingStatus.PENDING, limit=10
            ))

            processed_count = 0

            for paper in pending_papers:
                try:
                    # Queue paper for processing
                    process_paper_task.delay(str(paper.id))
                    processed_count += 1

                except Exception as e:
                    paper_logger.error(f"Failed to queue paper {paper.id}: {e}")

            paper_logger.info(f"Queued {processed_count} pending papers for processing")
            return {"queued_papers": processed_count}

        finally:
            db.close()

    except Exception as exc:
        paper_logger.error(f"Failed to process pending papers: {exc}")
        raise


@celery_app.task
def update_citations_task(paper_id: str):
    """Update citation network for a paper."""

    paper_logger.info(f"Updating citations for paper: {paper_id}")

    try:
        db = SessionLocal()

        try:
            # This would implement citation network analysis
            # For now, just a placeholder

            paper_logger.info(f"Citation update completed for paper: {paper_id}")
            return {"status": "completed", "paper_id": paper_id}

        finally:
            db.close()

    except Exception as exc:
        paper_logger.error(f"Citation update failed for {paper_id}: {exc}")
        raise


@celery_app.task
def cleanup_failed_tasks():
    """Clean up old failed tasks."""

    paper_logger.info("Cleaning up failed tasks...")

    try:
        db = SessionLocal()

        try:
            # Delete tasks older than 7 days
            cutoff_date = datetime.utcnow() - timedelta(days=7)

            deleted_count = db.query(ProcessingTask).filter(
                ProcessingTask.status == "failed",
                ProcessingTask.created_at < cutoff_date
            ).delete()

            db.commit()

            paper_logger.info(f"Cleaned up {deleted_count} old failed tasks")
            return {"deleted_tasks": deleted_count}

        finally:
            db.close()

    except Exception as exc:
        paper_logger.error(f"Failed to clean up tasks: {exc}")
        raise


@celery_app.task
def update_paper_metrics_task():
    """Update paper metrics (citation counts, influence scores, etc.)."""

    paper_logger.info("Updating paper metrics...")

    try:
        db = SessionLocal()

        try:
            # Get papers that need metric updates
            papers = db.query(Paper).filter(
                Paper.processing_status == ProcessingStatus.COMPLETED
            ).limit(100).all()

            updated_count = 0

            for paper in papers:
                try:
                    # Update citation count
                    from app.db.models import Citation
                    citation_count = db.query(Citation).filter(
                        Citation.cited_paper_id == paper.id
                    ).count()

                    # Update influence score (simplified calculation)
                    influence_score = min(citation_count * 0.1, 1.0)

                    # Update paper
                    paper.citation_count = citation_count
                    paper.influence_score = influence_score

                    updated_count += 1

                except Exception as e:
                    paper_logger.error(f"Failed to update metrics for paper {paper.id}: {e}")

            db.commit()

            paper_logger.info(f"Updated metrics for {updated_count} papers")
            return {"updated_papers": updated_count}

        finally:
            db.close()

    except Exception as exc:
        paper_logger.error(f"Failed to update paper metrics: {exc}")
        raise


@celery_app.task(bind=True)
def batch_process_papers_task(self, paper_ids: List[str]):
    """Process multiple papers in batch."""

    paper_logger.info(f"Starting batch processing for {len(paper_ids)} papers")

    results = []

    for paper_id in paper_ids:
        try:
            # Process each paper
            result = process_paper_task.delay(paper_id)
            results.append({
                "paper_id": paper_id,
                "task_id": result.id,
                "status": "queued"
            })

        except Exception as e:
            paper_logger.error(f"Failed to queue paper {paper_id}: {e}")
            results.append({
                "paper_id": paper_id,
                "status": "failed",
                "error": str(e)
            })

    paper_logger.info(f"Batch processing queued: {len(results)} tasks")
    return {"results": results, "total_papers": len(paper_ids)}


@celery_app.task
def generate_user_recommendations_task(user_id: str):
    """Generate paper recommendations for a user."""

    paper_logger.info(f"Generating recommendations for user: {user_id}")

    try:
        db = SessionLocal()

        try:
            from app.services.paper_service import paper_service

            # Generate recommendations
            recommendations = run_async(paper_service.get_paper_recommendations(
                user_id, None, db, limit=20
            ))

            paper_logger.info(f"Generated {len(recommendations)} recommendations for user {user_id}")

            # Store recommendations (you'd implement caching here)

            return {
                "status": "completed",
                "user_id": user_id,
                "recommendation_count": len(recommendations)
            }

        finally:
            db.close()

    except Exception as exc:
        paper_logger.error(f"Failed to generate recommendations for user {user_id}: {exc}")
        raise


# Helper functions
def update_task_status(
    db: Session,
    task_id: str,
    status: str,
    progress: int = 0,
    result: Dict[str, Any] = None,
    error: str = None,
    paper_id: str = None,
    user_id: str = None
):
    """Update processing task status."""

    try:
        task = db.query(ProcessingTask).filter(
            ProcessingTask.task_id == task_id
        ).first()

        if not task:
            # Create new task record
            task = ProcessingTask(
                task_id=task_id,
                task_type="paper_processing",
                status=status,
                progress=progress,
                result=result,
                error_message=error,
                paper_id=paper_id,
                user_id=user_id
            )
            db.add(task)
        else:
            # Update existing task
            task.status = status
            task.progress = progress

            if result:
                task.result = result

            if error:
                task.error_message = error

            if status == "running" and not task.started_at:
                task.started_at = datetime.utcnow()
            elif status in ["completed", "failed"]:
                task.completed_at = datetime.utcnow()

        db.commit()

    except Exception as e:
        paper_logger.error(f"Failed to update task status: {e}")
        db.rollback()


def get_task_status(db: Session, task_id: str) -> Dict[str, Any]:
    """Get task status."""

    try:
        task = db.query(ProcessingTask).filter(
            ProcessingTask.task_id == task_id
        ).first()

        if task:
            return {
                "task_id": task.task_id,
                "status": task.status,
                "progress": task.progress,
                "result": task.result,
                "error": task.error_message,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at
            }
        else:
            return {"task_id": task_id, "status": "not_found"}

    except Exception as e:
        paper_logger.error(f"Failed to get task status: {e}")
        return {"task_id": task_id, "status": "error", "error": str(e)}