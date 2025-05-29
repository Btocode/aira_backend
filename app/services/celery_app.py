"""
Celery configuration for background tasks.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.core.app_logging import setup_logging, paper_logger


# Create Celery instance
celery_app = Celery(
    "ai_research_assistant",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "app.services.celery_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        "app.services.celery_tasks.process_paper_task": {"queue": "paper_processing"},
        "app.services.celery_tasks.generate_embeddings_task": {"queue": "ai_processing"},
        "app.services.celery_tasks.update_citations_task": {"queue": "citations"},
    },

    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Task execution
    task_always_eager=False,  # Set to True for testing
    task_eager_propagates=True,
    task_ignore_result=False,

    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    # Task time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes

    # Result backend settings
    result_expires=3600,  # 1 hour

    # Retry settings
    task_acks_late=True,
    worker_disable_rate_limits=False,

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Beat schedule for periodic tasks
    beat_schedule={
        "process_pending_papers": {
            "task": "app.services.celery_tasks.process_pending_papers_task",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        "cleanup_failed_tasks": {
            "task": "app.services.celery_tasks.cleanup_failed_tasks",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
        },
        "update_paper_metrics": {
            "task": "app.services.celery_tasks.update_paper_metrics_task",
            "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        },
    },
)


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks."""
    paper_logger.info("Setting up Celery periodic tasks")


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f'Request: {self.request!r}')
    return "Debug task completed"


# Event handlers
@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_paper_task(self, paper_id: str):
    """Background task to process a paper with AI."""
    import asyncio
    from app.db.database import SessionLocal
    from app.services.paper_service import paper_service

    paper_logger.info(f"Starting paper processing task for: {paper_id}")

    try:
        # Create database session
        db = SessionLocal()

        try:
            # Process paper using asyncio.run since Celery tasks are sync
            success = asyncio.run(paper_service.process_paper_content(paper_id, db))

            if success:
                paper_logger.info(f"Paper processing completed successfully: {paper_id}")
                return {"status": "completed", "paper_id": paper_id}
            else:
                paper_logger.error(f"Paper processing failed: {paper_id}")
                return {"status": "failed", "paper_id": paper_id}

        finally:
            db.close()

    except Exception as exc:
        paper_logger.error(f"Paper processing task failed for {paper_id}: {exc}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries * 60  # Exponential backoff
            paper_logger.info(f"Retrying paper processing in {countdown} seconds")
            raise self.retry(countdown=countdown)

        # Max retries reached
        paper_logger.error(f"Max retries reached for paper processing: {paper_id}")

        # Update paper status to failed
        try:
            db = SessionLocal()
            from app.db.queries.paper_queries import update_paper_processing_status
            from app.db.models import ProcessingStatus

            asyncio.run(update_paper_processing_status(
                db, paper_id, ProcessingStatus.FAILED, str(exc)
            ))
            db.close()

        except Exception as update_exc:
            paper_logger.error(f"Failed to update paper status: {update_exc}")

        raise exc


if __name__ == "__main__":
    # Setup logging for Celery worker
    setup_logging()
    celery_app.start()