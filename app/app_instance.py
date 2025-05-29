"""
FastAPI application instance and configuration.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.app_logging import setup_logging, app_logger
from app.db.database import init_db, DatabaseManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""

    # Startup
    app_logger.info("Starting AI Research Assistant API...")

    # Setup logging
    setup_logging()

    # Initialize database
    try:
        init_db()
        app_logger.info("Database initialized successfully")
    except Exception as e:
        app_logger.error(f"Database initialization failed: {e}")
        raise

    # Check database connection
    if not DatabaseManager.check_connection():
        app_logger.error("Database connection check failed")
        raise Exception("Database connection failed")

    app_logger.info("Application startup complete")
    yield

    # Shutdown
    app_logger.info("Shutting down AI Research Assistant API...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="AI-powered academic research assistant API",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Add middleware
    setup_middleware(app)

    # Include routers
    include_routers(app)

    return app


def setup_middleware(app: FastAPI) -> None:
    """Setup FastAPI middleware."""

    # Trusted Host Middleware (security)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["yourdomain.com", "api.yourdomain.com"]
        )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip Middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)


def include_routers(app: FastAPI) -> None:
    """Include API routers."""

    from app.api.v1.auth import router as auth_router
    from app.api.v1.papers import router as papers_router
    from app.api.v1.knowledge import router as knowledge_router
    from app.api.v1.users import router as users_router
    from app.api.v1.search import router as search_router
    from app.api.v1.citations import router as citations_router

    # API v1 routes
    api_prefix = "/api/v1"

    app.include_router(
        auth_router,
        prefix=f"{api_prefix}/auth",
        tags=["authentication"]
    )

    app.include_router(
        users_router,
        prefix=f"{api_prefix}/users",
        tags=["users"]
    )

    app.include_router(
        papers_router,
        prefix=f"{api_prefix}/papers",
        tags=["papers"]
    )

    app.include_router(
        knowledge_router,
        prefix=f"{api_prefix}/knowledge",
        tags=["knowledge"]
    )

    app.include_router(
        search_router,
        prefix=f"{api_prefix}/search",
        tags=["search"]
    )

    app.include_router(
        citations_router,
        prefix=f"{api_prefix}/citations",
        tags=["citations"]
    )

    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint."""
        db_healthy = DatabaseManager.check_connection()

        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "version": settings.version,
            "environment": settings.environment,
            "database": "connected" if db_healthy else "disconnected"
        }

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint."""
        return {
            "message": "AI Research Assistant API",
            "version": settings.version,
            "docs": "/docs" if settings.debug else "Documentation not available in production",
            "health": "/health"
        }