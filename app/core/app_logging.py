"""
Application logging configuration.
"""
import logging
import sys
from typing import Any, Dict

from app.core.config import settings


class CustomFormatter(logging.Formatter):
    """Custom log formatter with colors for development."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[91m",   # Bright Red
        "RESET": "\033[0m"        # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors in development."""

        if settings.is_development:
            # Add color to levelname
            color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"

        # Add request ID if available
        if hasattr(record, "request_id"):
            record.msg = f"[{record.request_id}] {record.msg}"

        return super().format(record)


def setup_logging() -> None:
    """Setup application logging configuration."""

    # Set root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Create formatter
    formatter = CustomFormatter(
        fmt=settings.log_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Configure specific loggers
    configure_specific_loggers()

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Level: {settings.log_level}")


def configure_specific_loggers() -> None:
    """Configure specific third-party loggers."""

    # Reduce SQLAlchemy logging noise in production
    if not settings.is_development:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    # Configure HTTP client logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Configure Celery logging
    logging.getLogger("celery").setLevel(logging.INFO)

    # Reduce OpenAI client logging
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx._client").setLevel(logging.WARNING)


class RequestContextFilter(logging.Filter):
    """Add request context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request ID to log record if available."""

        # This would integrate with FastAPI middleware to add request context
        # For now, it's a placeholder
        if not hasattr(record, "request_id"):
            record.request_id = "N/A"

        return True


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


# Application loggers
app_logger = get_logger("ai_research_assistant")
api_logger = get_logger("ai_research_assistant.api")
db_logger = get_logger("ai_research_assistant.db")
ai_logger = get_logger("ai_research_assistant.ai")
paper_logger = get_logger("ai_research_assistant.paper")


class LoggerMixin:
    """Mixin to add logging capabilities to classes."""

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")


def log_function_call(func_name: str, **kwargs) -> None:
    """Log function call with parameters."""

    logger = get_logger("ai_research_assistant.functions")

    # Filter sensitive parameters
    safe_kwargs = {
        k: v if k not in ["password", "token", "key", "secret"] else "[REDACTED]"
        for k, v in kwargs.items()
    }

    logger.debug(f"Calling {func_name} with params: {safe_kwargs}")


def log_ai_request(service: str, model: str, token_count: int, response_time: float) -> None:
    """Log AI service request."""

    ai_logger.info(
        f"AI Request - Service: {service}, Model: {model}, "
        f"Tokens: {token_count}, Time: {response_time:.2f}s"
    )


def log_paper_processed(paper_id: str, processing_time: float, status: str) -> None:
    """Log paper processing completion."""

    paper_logger.info(
        f"Paper processed - ID: {paper_id}, Time: {processing_time:.2f}s, Status: {status}"
    )


def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """Log error with context."""

    logger = get_logger("ai_research_assistant.errors")

    context_str = f" Context: {context}" if context else ""
    logger.error(f"Error: {str(error)}{context_str}", exc_info=True)