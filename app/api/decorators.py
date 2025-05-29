"""
API route decorators for common functionality.
"""
import time
from functools import wraps
from typing import Callable, Optional, Dict, Any

from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse
import redis

from app.core.config import settings
from app.core.app_logging import api_logger, log_error


# Redis client for rate limiting
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def rate_limit(
    requests_per_minute: int = 60,
    window_minutes: int = 1,
    key_func: Optional[Callable] = None
):
    """
    Rate limiting decorator for API endpoints.

    Args:
        requests_per_minute: Number of requests allowed per minute
        window_minutes: Time window in minutes
        key_func: Function to generate rate limit key (defaults to IP-based)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from kwargs or args
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # If no request found, skip rate limiting
                return await func(*args, **kwargs)

            # Generate rate limit key
            if key_func:
                rate_key = key_func(request)
            else:
                # Default to IP-based rate limiting
                client_ip = request.client.host
                rate_key = f"rate_limit:{func.__name__}:{client_ip}"

            try:
                # Get current count
                current_requests = redis_client.get(rate_key)

                if current_requests is None:
                    # First request in window
                    redis_client.setex(rate_key, window_minutes * 60, 1)
                else:
                    current_count = int(current_requests)

                    if current_count >= requests_per_minute:
                        # Rate limit exceeded
                        api_logger.warning(
                            f"Rate limit exceeded for {rate_key}: {current_count}/{requests_per_minute}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Rate limit exceeded. Max {requests_per_minute} requests per {window_minutes} minute(s).",
                            headers={"Retry-After": str(window_minutes * 60)}
                        )

                    # Increment counter
                    redis_client.incr(rate_key)

            except redis.RedisError as e:
                # Redis error - log but don't block request
                api_logger.error(f"Redis error in rate limiting: {e}")

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def cache_response(
    expiration_seconds: int = 300,
    key_func: Optional[Callable] = None,
    vary_by_user: bool = True
):
    """
    Response caching decorator.

    Args:
        expiration_seconds: Cache expiration time in seconds
        key_func: Function to generate cache key
        vary_by_user: Whether to vary cache by user ID
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default cache key
                func_name = func.__name__
                args_str = "_".join(str(arg) for arg in args[1:])  # Skip 'self'
                kwargs_str = "_".join(f"{k}:{v}" for k, v in kwargs.items())
                cache_key = f"cache:{func_name}:{args_str}:{kwargs_str}"

            # Add user ID to cache key if requested
            if vary_by_user:
                # Try to extract user from kwargs
                current_user = kwargs.get('current_user')
                if current_user:
                    cache_key = f"{cache_key}:user:{current_user.id}"

            try:
                # Try to get cached response
                cached_response = redis_client.get(cache_key)

                if cached_response:
                    api_logger.debug(f"Cache hit for key: {cache_key}")
                    import json
                    return json.loads(cached_response)

                # Execute function
                result = await func(*args, **kwargs)

                # Cache the result
                if result is not None:
                    import json
                    redis_client.setex(
                        cache_key,
                        expiration_seconds,
                        json.dumps(result, default=str)
                    )
                    api_logger.debug(f"Cached response for key: {cache_key}")

                return result

            except redis.RedisError as e:
                # Redis error - log but continue without caching
                api_logger.error(f"Redis error in response caching: {e}")
                return await func(*args, **kwargs)
            except Exception as e:
                # JSON serialization error or other issues
                api_logger.error(f"Caching error: {e}")
                return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_subscription(tier: str = "researcher"):
    """
    Decorator to require specific subscription tier.

    Args:
        tier: Required subscription tier ('free', 'researcher', 'institution')
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs
            current_user = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Check subscription tier
            tier_levels = {
                "free": 0,
                "researcher": 1,
                "institution": 2
            }

            user_level = tier_levels.get(current_user.subscription_tier, 0)
            required_level = tier_levels.get(tier, 0)

            if user_level < required_level:
                api_logger.warning(
                    f"User {current_user.id} attempted to access {tier} feature "
                    f"with {current_user.subscription_tier} subscription"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This feature requires {tier} subscription or higher"
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def log_api_call(
    log_request: bool = True,
    log_response: bool = False,
    log_duration: bool = True
):
    """
    Decorator to log API calls.

    Args:
        log_request: Whether to log request details
        log_response: Whether to log response details
        log_duration: Whether to log call duration
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            # Log request
            if log_request:
                api_logger.info(f"API call: {func.__name__}")
                if kwargs.get('current_user'):
                    api_logger.debug(f"User: {kwargs['current_user'].id}")

            try:
                # Execute function
                result = await func(*args, **kwargs)

                # Log response
                if log_response:
                    api_logger.debug(f"Response type: {type(result).__name__}")

                # Log duration
                if log_duration:
                    duration = time.time() - start_time
                    api_logger.info(f"API call {func.__name__} completed in {duration:.3f}s")

                return result

            except Exception as e:
                # Log error
                duration = time.time() - start_time
                api_logger.error(
                    f"API call {func.__name__} failed after {duration:.3f}s: {str(e)}"
                )
                log_error(e, {
                    "function": func.__name__,
                    "duration": duration,
                    "user_id": kwargs.get('current_user', {}).get('id') if kwargs.get('current_user') else None
                })
                raise

        return wrapper
    return decorator


def handle_errors(
    default_message: str = "An error occurred",
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
):
    """
    Decorator to handle and standardize API errors.

    Args:
        default_message: Default error message
        status_code: Default HTTP status code
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Re-raise HTTP exceptions as-is
                raise
            except ValueError as e:
                # Convert ValueError to 400 Bad Request
                api_logger.warning(f"ValueError in {func.__name__}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                # Log unexpected errors and return generic message
                api_logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                log_error(e, {"function": func.__name__})

                raise HTTPException(
                    status_code=status_code,
                    detail=default_message
                )

        return wrapper
    return decorator


def validate_content_type(allowed_types: list = ["application/json"]):
    """
    Decorator to validate request content type.

    Args:
        allowed_types: List of allowed content types
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request:
                content_type = request.headers.get("content-type", "").split(";")[0]

                if content_type not in allowed_types:
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail=f"Content type {content_type} not supported. "
                               f"Allowed types: {', '.join(allowed_types)}"
                    )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def paginate(default_limit: int = 20, max_limit: int = 100):
    """
    Decorator to add pagination parameters validation.

    Args:
        default_limit: Default number of items per page
        max_limit: Maximum allowed limit
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Validate limit parameter
            limit = kwargs.get('limit', default_limit)
            if limit > max_limit:
                kwargs['limit'] = max_limit
                api_logger.warning(f"Limit {limit} exceeded maximum {max_limit}, using {max_limit}")

            # Validate offset parameter
            offset = kwargs.get('offset', 0)
            if offset < 0:
                kwargs['offset'] = 0
                api_logger.warning(f"Negative offset {offset} not allowed, using 0")

            return await func(*args, **kwargs)

        return wrapper
    return decorator


# Utility functions for decorators
def user_based_rate_limit_key(request: Request) -> str:
    """Generate rate limit key based on user ID if available, otherwise IP."""
    # This would need to extract user info from the request
    # For now, use IP-based key
    return f"rate_limit:{request.url.path}:{request.client.host}"


def endpoint_cache_key(*args, **kwargs) -> str:
    """Generate cache key for endpoint responses."""
    # Extract meaningful parameters for cache key
    params = []

    for key, value in kwargs.items():
        if key not in ['db', 'current_user', 'background_tasks']:
            params.append(f"{key}:{value}")

    return ":".join(params) if params else "default"