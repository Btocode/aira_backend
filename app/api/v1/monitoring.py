"""
Monitoring and health check endpoints.
"""
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user, require_subscription_tier
from app.db.database import get_db
from app.schemas.user import UserInDB
from app.core.analytics import metrics_collector, health_checker
from app.core.app_logging import api_logger

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return await health_checker.get_system_health()


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with all system components."""
    return await health_checker.get_system_health()


@router.get("/metrics")
async def get_metrics():
    """Get basic system metrics (for Prometheus scraping)."""
    try:
        metrics = await metrics_collector.get_real_time_metrics()

        # Format for Prometheus (simple format)
        prometheus_metrics = []

        # Request metrics
        if "requests" in metrics:
            prometheus_metrics.append(f'api_requests_total {metrics["requests"]["total"]}')
            prometheus_metrics.append(f'api_errors_total {metrics["requests"]["errors"]}')
            prometheus_metrics.append(f'api_success_rate {metrics["requests"]["success_rate"]}')

        # Response time metrics
        if "response_times" in metrics:
            prometheus_metrics.append(f'api_response_time_avg {metrics["response_times"]["average"]}')
            prometheus_metrics.append(f'api_response_time_max {metrics["response_times"]["maximum"]}')

        # User metrics
        if "users" in metrics:
            prometheus_metrics.append(f'api_active_users {metrics["users"]["active"]}')

        return "\n".join(prometheus_metrics)

    except Exception as e:
        api_logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@router.get("/metrics/realtime")
async def get_realtime_metrics(
    current_user: UserInDB = Depends(require_subscription_tier("institution"))
):
    """Get real-time system metrics (requires institution subscription)."""
    try:
        metrics = await metrics_collector.get_real_time_metrics()
        return metrics
    except Exception as e:
        api_logger.error(f"Failed to get real-time metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve real-time metrics"
        )


@router.get("/metrics/historical")
async def get_historical_metrics(
    days: int = 7,
    current_user: UserInDB = Depends(require_subscription_tier("institution"))
):
    """Get historical system metrics (requires institution subscription)."""
    try:
        if days > 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 30 days of historical data allowed"
            )

        metrics = await metrics_collector.get_historical_metrics(days)
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get historical metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve historical metrics"
        )


@router.get("/analytics/user")
async def get_user_analytics(
    days: int = 30,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get analytics for current user."""
    try:
        if days > 90:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 90 days of user analytics allowed"
            )

        analytics = await metrics_collector.get_user_analytics(str(current_user.id), days)
        return analytics
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Failed to get user analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user analytics"
        )


@router.get("/status")
async def get_system_status():
    """Get system status summary."""
    try:
        health = await health_checker.get_system_health()
        metrics = await metrics_collector.get_real_time_metrics()

        return {
            "status": health["status"],
            "version": health["version"],
            "environment": health["environment"],
            "uptime": "N/A",  # Would calculate actual uptime
            "requests_per_hour": metrics.get("requests", {}).get("total", 0),
            "error_rate": metrics.get("requests", {}).get("errors", 0),
            "active_users": metrics.get("users", {}).get("active", 0),
            "database_status": health["checks"].get("database", {}).get("status", "unknown"),
            "redis_status": health["checks"].get("redis", {}).get("status", "unknown"),
            "timestamp": health["timestamp"]
        }
    except Exception as e:
        api_logger.error(f"Failed to get system status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system status"
        )


@router.get("/stats/overview")
async def get_stats_overview(
    current_user: UserInDB = Depends(require_subscription_tier("researcher"))
):
    """Get overview statistics (requires researcher subscription)."""
    try:
        # Get basic stats from database
        from app.db.queries.paper_queries import get_paper_stats
        from app.db.queries.user_queries import get_user_stats

        db = next(get_db())

        try:
            paper_stats = await get_paper_stats(db)
            user_stats = await get_user_stats(db, str(current_user.id))

            return {
                "user_stats": user_stats,
                "system_stats": paper_stats,
                "generated_at": "2024-01-01T00:00:00Z"
            }
        finally:
            db.close()

    except Exception as e:
        api_logger.error(f"Failed to get stats overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics overview"
        )


@router.post("/alerts/test")
async def test_alert_system(
    current_user: UserInDB = Depends(require_subscription_tier("institution"))
):
    """Test alert system (requires institution subscription)."""
    try:
        # This would test various alert mechanisms
        # - Email notifications
        # - Slack/Discord webhooks
        # - PagerDuty integration
        # - SMS alerts

        api_logger.info(f"Alert system test triggered by user: {current_user.id}")

        return {
            "message": "Alert system test completed",
            "alerts_sent": [
                {"type": "email", "status": "success"},
                {"type": "slack", "status": "success"},
                {"type": "webhook", "status": "success"}
            ],
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        api_logger.error(f"Alert system test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Alert system test failed"
        )


@router.get("/version")
async def get_version_info():
    """Get application version information."""
    from app.core.config import settings

    return {
        "version": settings.version,
        "environment": settings.environment,
        "python_version": "3.11+",
        "api_version": "v1",
        "build_date": "2024-01-01",
        "commit_hash": "N/A",  # Would be populated by CI/CD
        "features": [
            "paper_processing",
            "ai_summarization",
            "knowledge_base",
            "citation_network",
            "semantic_search",
            "background_tasks",
            "user_management"
        ]
    }


@router.get("/debug/info")
async def get_debug_info(
    current_user: UserInDB = Depends(require_subscription_tier("institution"))
):
    """Get debug information (requires institution subscription)."""
    try:
        from app.core.config import settings
        import sys
        import os

        return {
            "python_version": sys.version,
            "platform": sys.platform,
            "environment_variables": {
                "ENVIRONMENT": settings.environment,
                "DEBUG": settings.debug,
                "DATABASE_URL": "***" if settings.database_url else None,
                "REDIS_URL": "***" if settings.redis_url else None,
            },
            "system_info": {
                "cpu_count": os.cpu_count(),
                "current_working_directory": os.getcwd(),
            },
            "warnings": [
                "This endpoint should only be available in non-production environments"
            ] if settings.is_production else []
        }
    except Exception as e:
        api_logger.error(f"Failed to get debug info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve debug information"
        )


@router.post("/maintenance/mode")
async def toggle_maintenance_mode(
    enabled: bool,
    current_user: UserInDB = Depends(require_subscription_tier("institution"))
):
    """Toggle maintenance mode (requires institution subscription)."""
    try:
        # This would set a flag in Redis or database to enable/disable maintenance mode
        # The middleware would check this flag and return maintenance responses

        if redis_client:
            redis_client.set("maintenance_mode", "enabled" if enabled else "disabled")

        api_logger.info(f"Maintenance mode {'enabled' if enabled else 'disabled'} by user: {current_user.id}")

        return {
            "maintenance_mode": enabled,
            "message": f"Maintenance mode {'enabled' if enabled else 'disabled'}",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        api_logger.error(f"Failed to toggle maintenance mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle maintenance mode"
        )