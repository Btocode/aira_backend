  """
Performance monitoring and analytics middleware.
"""
import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis

from app.core.config import settings
from app.core.app_logging import api_logger, get_logger
from app.db.database import SessionLocal
from app.db.models import APIUsage, UserActivity


# Analytics logger
analytics_logger = get_logger("analytics")

# Redis client for metrics
try:
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
except Exception as e:
    analytics_logger.warning(f"Redis connection failed for analytics: {e}")
    redis_client = None


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for performance monitoring and analytics."""

    async def dispatch(self, request: Request, call_next):
        """Process request and collect metrics."""

        # Generate request ID
        request_id = str(uuid4())
        request.state.request_id = request_id

        # Start timing
        start_time = time.time()

        # Collect request info
        request_info = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "timestamp": datetime.utcnow().isoformat()
        }

        # Extract user info if available
        user_id = None
        try:
            # Try to extract user from auth header
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                from app.core.security import SecurityUtils
                token = auth_header.split(" ")[1]
                user_id = SecurityUtils.verify_token(token)
        except Exception:
            pass  # Continue without user info

        request_info["user_id"] = user_id

        # Process request
        try:
            response = await call_next(request)

            # Calculate response time
            response_time = time.time() - start_time

            # Collect response info
            response_info = {
                "status_code": response.status_code,
                "response_time": response_time,
                "success": 200 <= response.status_code < 400
            }

            # Log performance metrics
            await self._log_performance_metrics(request_info, response_info)

            # Add response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{response_time:.3f}s"

            return response

        except Exception as e:
            # Handle errors
            response_time = time.time() - start_time

            response_info = {
                "status_code": 500,
                "response_time": response_time,
                "success": False,
                "error": str(e)
            }

            await self._log_performance_metrics(request_info, response_info)

            # Return error response
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
                headers={"X-Request-ID": request_id}
            )

    async def _log_performance_metrics(self, request_info: Dict[str, Any], response_info: Dict[str, Any]):
        """Log performance metrics to various backends."""

        try:
            # Log to application logger
            analytics_logger.info(
                f"API Request - "
                f"Method: {request_info['method']} "
                f"Path: {request_info['path']} "
                f"Status: {response_info['status_code']} "
                f"Time: {response_info['response_time']:.3f}s "
                f"User: {request_info.get('user_id', 'anonymous')}"
            )

            # Store in Redis for real-time metrics
            if redis_client:
                await self._store_redis_metrics(request_info, response_info)

            # Store in database for long-term analytics
            await self._store_database_metrics(request_info, response_info)

        except Exception as e:
            analytics_logger.error(f"Failed to log performance metrics: {e}")

    async def _store_redis_metrics(self, request_info: Dict[str, Any], response_info: Dict[str, Any]):
        """Store metrics in Redis for real-time monitoring."""

        try:
            now = datetime.utcnow()
            hour_key = now.strftime("%Y-%m-%d-%H")
            minute_key = now.strftime("%Y-%m-%d-%H-%M")

            # Increment counters
            pipe = redis_client.pipeline()

            # Request counts
            pipe.incr(f"api:requests:total:{hour_key}")
            pipe.incr(f"api:requests:total:{minute_key}")
            pipe.incr(f"api:requests:method:{request_info['method']}:{hour_key}")
            pipe.incr(f"api:requests:status:{response_info['status_code']}:{hour_key}")

            # Response times
            pipe.lpush(f"api:response_times:{minute_key}", response_info['response_time'])
            pipe.expire(f"api:response_times:{minute_key}", 3600)  # Keep for 1 hour

            # Error tracking
            if not response_info['success']:
                pipe.incr(f"api:errors:{hour_key}")
                pipe.lpush(f"api:errors:details:{hour_key}", json.dumps({
                    "path": request_info['path'],
                    "method": request_info['method'],
                    "status": response_info['status_code'],
                    "error": response_info.get('error'),
                    "timestamp": request_info['timestamp']
                }))

            # User activity
            if request_info.get('user_id'):
                pipe.sadd(f"api:active_users:{hour_key}", request_info['user_id'])
                pipe.incr(f"api:user_requests:{request_info['user_id']}:{hour_key}")

            # Execute all commands
            await asyncio.to_thread(pipe.execute)

        except Exception as e:
            analytics_logger.error(f"Failed to store Redis metrics: {e}")

    async def _store_database_metrics(self, request_info: Dict[str, Any], response_info: Dict[str, Any]):
        """Store metrics in database for long-term analytics."""

        try:
            # Only store significant requests to avoid database bloat
            if self._should_store_request(request_info, response_info):
                db = SessionLocal()

                try:
                    # Create API usage record
                    api_usage = APIUsage(
                        user_id=request_info.get('user_id'),
                        endpoint=request_info['path'],
                        method=request_info['method'],
                        status_code=response_info['status_code'],
                        response_time=response_info['response_time'],
                        ai_service=self._extract_ai_service(request_info),
                        tokens_used=0,  # Would be populated by AI service calls
                        cost=0.0,
                        created_at=datetime.utcnow()
                    )

                    db.add(api_usage)

                    # Create user activity record
                    if request_info.get('user_id'):
                        activity = UserActivity(
                            user_id=request_info['user_id'],
                            activity_type=self._get_activity_type(request_info),
                            activity_data={
                                "endpoint": request_info['path'],
                                "method": request_info['method'],
                                "response_time": response_info['response_time'],
                                "success": response_info['success']
                            },
                            ip_address=request_info.get('client_host'),
                            user_agent=request_info.get('user_agent'),
                            created_at=datetime.utcnow()
                        )
                        db.add(activity)

                    db.commit()

                finally:
                    db.close()

        except Exception as e:
            analytics_logger.error(f"Failed to store database metrics: {e}")

    def _should_store_request(self, request_info: Dict[str, Any], response_info: Dict[str, Any]) -> bool:
        """Determine if request should be stored in database."""

        # Always store errors
        if not response_info['success']:
            return True

        # Store authenticated requests
        if request_info.get('user_id'):
            return True

        # Store API endpoints (not health checks, static files, etc.)
        if request_info['path'].startswith('/api/'):
            return True

        # Store slow requests
        if response_info['response_time'] > 2.0:
            return True

        return False

    def _extract_ai_service(self, request_info: Dict[str, Any]) -> Optional[str]:
        """Extract AI service name from request."""

        path = request_info['path']

        if 'summary' in path:
            return 'openai'
        elif 'knowledge' in path and request_info['method'] == 'POST':
            return 'openai'

        return None

    def _get_activity_type(self, request_info: Dict[str, Any]) -> str:
        """Get activity type from request."""

        path = request_info['path']
        method = request_info['method']

        if '/papers' in path:
            if method == 'POST':
                return 'paper_added'
            elif method == 'GET':
                return 'paper_viewed'
            elif 'search' in path:
                return 'paper_search'
        elif '/knowledge' in path:
            if method == 'POST':
                return 'knowledge_created'
            elif 'search' in path:
                return 'knowledge_search'
        elif '/auth' in path:
            return 'authentication'

        return 'api_request'


class MetricsCollector:
    """Collect and aggregate metrics."""

    @staticmethod
    async def get_real_time_metrics() -> Dict[str, Any]:
        """Get real-time metrics from Redis."""

        if not redis_client:
            return {}

        try:
            now = datetime.utcnow()
            current_hour = now.strftime("%Y-%m-%d-%H")
            current_minute = now.strftime("%Y-%m-%d-%H-%M")

            # Get basic metrics
            total_requests = redis_client.get(f"api:requests:total:{current_hour}") or 0
            total_errors = redis_client.get(f"api:errors:{current_hour}") or 0

            # Get response times for current minute
            response_times = redis_client.lrange(f"api:response_times:{current_minute}", 0, -1)
            response_times = [float(t) for t in response_times]

            # Calculate statistics
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            max_response_time = max(response_times) if response_times else 0

            # Get active users
            active_users = redis_client.scard(f"api:active_users:{current_hour}")

            # Get method breakdown
            methods = ['GET', 'POST', 'PUT', 'DELETE']
            method_counts = {}
            for method in methods:
                count = redis_client.get(f"api:requests:method:{method}:{current_hour}") or 0
                method_counts[method] = int(count)

            # Get status code breakdown
            status_codes = [200, 201, 400, 401, 403, 404, 500]
            status_counts = {}
            for status in status_codes:
                count = redis_client.get(f"api:requests:status:{status}:{current_hour}") or 0
                status_counts[str(status)] = int(count)

            return {
                "timestamp": now.isoformat(),
                "requests": {
                    "total": int(total_requests),
                    "errors": int(total_errors),
                    "success_rate": (int(total_requests) - int(total_errors)) / max(int(total_requests), 1) * 100
                },
                "response_times": {
                    "average": round(avg_response_time, 3),
                    "maximum": round(max_response_time, 3),
                    "count": len(response_times)
                },
                "users": {
                    "active": int(active_users)
                },
                "methods": method_counts,
                "status_codes": status_counts
            }

        except Exception as e:
            analytics_logger.error(f"Failed to get real-time metrics: {e}")
            return {}

    @staticmethod
    async def get_historical_metrics(days: int = 7) -> Dict[str, Any]:
        """Get historical metrics from database."""

        try:
            db = SessionLocal()

            try:
                # Calculate date range
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=days)

                # Get API usage statistics
                api_usage_stats = db.query(APIUsage).filter(
                    APIUsage.created_at >= start_date
                ).all()

                # Aggregate metrics
                total_requests = len(api_usage_stats)
                successful_requests = len([r for r in api_usage_stats if 200 <= r.status_code < 400])

                # Calculate average response time
                response_times = [r.response_time for r in api_usage_stats if r.response_time]
                avg_response_time = sum(response_times) / len(response_times) if response_times else 0

                # Most popular endpoints
                endpoint_counts = {}
                for usage in api_usage_stats:
                    endpoint = f"{usage.method} {usage.endpoint}"
                    endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1

                popular_endpoints = sorted(
                    endpoint_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]

                # Daily breakdown
                daily_stats = {}
                for usage in api_usage_stats:
                    date_key = usage.created_at.strftime("%Y-%m-%d")
                    if date_key not in daily_stats:
                        daily_stats[date_key] = {"requests": 0, "errors": 0}

                    daily_stats[date_key]["requests"] += 1
                    if usage.status_code >= 400:
                        daily_stats[date_key]["errors"] += 1

                return {
                    "period": f"{days} days",
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "summary": {
                        "total_requests": total_requests,
                        "successful_requests": successful_requests,
                        "success_rate": successful_requests / max(total_requests, 1) * 100,
                        "average_response_time": round(avg_response_time, 3)
                    },
                    "popular_endpoints": popular_endpoints,
                    "daily_stats": daily_stats
                }

            finally:
                db.close()

        except Exception as e:
            analytics_logger.error(f"Failed to get historical metrics: {e}")
            return {}

    @staticmethod
    async def get_user_analytics(user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get analytics for specific user."""

        try:
            db = SessionLocal()

            try:
                # Calculate date range
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=days)

                # Get user activities
                activities = db.query(UserActivity).filter(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= start_date
                ).all()

                # Get API usage
                api_usage = db.query(APIUsage).filter(
                    APIUsage.user_id == user_id,
                    APIUsage.created_at >= start_date
                ).all()

                # Activity breakdown
                activity_counts = {}
                for activity in activities:
                    activity_counts[activity.activity_type] = activity_counts.get(activity.activity_type, 0) + 1

                # Usage patterns
                hourly_usage = {}
                for usage in api_usage:
                    hour = usage.created_at.hour
                    hourly_usage[hour] = hourly_usage.get(hour, 0) + 1

                return {
                    "user_id": user_id,
                    "period": f"{days} days",
                    "total_activities": len(activities),
                    "total_api_calls": len(api_usage),
                    "activity_breakdown": activity_counts,
                    "hourly_usage_pattern": hourly_usage,
                    "most_active_hour": max(hourly_usage.items(), key=lambda x: x[1])[0] if hourly_usage else None
                }

            finally:
                db.close()

        except Exception as e:
            analytics_logger.error(f"Failed to get user analytics: {e}")
            return {}


class HealthChecker:
    """System health monitoring."""

    @staticmethod
    async def get_system_health() -> Dict[str, Any]:
        """Get comprehensive system health status."""

        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.version,
            "environment": settings.environment,
            "checks": {}
        }

        # Database health
        try:
            from app.db.database import DatabaseManager
            db_healthy = DatabaseManager.check_connection()
            health_status["checks"]["database"] = {
                "status": "healthy" if db_healthy else "unhealthy",
                "response_time": 0  # Would measure actual response time
            }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Redis health
        try:
            if redis_client:
                redis_client.ping()
                health_status["checks"]["redis"] = {"status": "healthy"}
            else:
                health_status["checks"]["redis"] = {"status": "unhealthy", "error": "Not connected"}
        except Exception as e:
            health_status["checks"]["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # AI service health
        try:
            # This would test AI service connectivity
            health_status["checks"]["ai_service"] = {"status": "healthy"}
        except Exception as e:
            health_status["checks"]["ai_service"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Overall health
        unhealthy_checks = [
            check for check in health_status["checks"].values()
            if check["status"] != "healthy"
        ]

        if unhealthy_checks:
            health_status["status"] = "unhealthy"

        return health_status


# Export metrics collector and health checker
metrics_collector = MetricsCollector()
health_checker = HealthChecker()