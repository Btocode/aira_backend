"""
Main application entry point.
"""
from app.app_instance import create_app
from app.core.app_logging import app_logger

# Create FastAPI application
app = create_app()

if __name__ == "__main__":
    import uvicorn
    from app.core.config import settings

    app_logger.info(f"Starting server on {settings.host}:{settings.port}")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )