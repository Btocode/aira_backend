"""
Testing configuration and fixtures.
"""
import asyncio
import pytest
from typing import Generator, AsyncGenerator
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.app_instance import create_app
from app.core.config import settings
from app.core.security import SecurityUtils
from app.db.database import Base, get_db
from app.db.models import User, Paper, KnowledgeEntry
from app.services.ai_service import ai_service


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def app():
    """Create FastAPI app instance for testing."""
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def client(app) -> Generator:
    """Create test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_user(db_session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=SecurityUtils.get_password_hash("testpassword"),
        full_name="Test User",
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_headers(test_user) -> dict:
    """Create authorization headers for test user."""
    token = SecurityUtils.create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_paper(db_session, test_user) -> Paper:
    """Create a test paper."""
    paper = Paper(
        title="Test Paper: AI in Research",
        authors=[{"name": "John Doe"}, {"name": "Jane Smith"}],
        abstract="This is a test paper about AI in research.",
        doi="10.1000/test123",
        url="https://example.com/paper/test123",
        source="arxiv",
        processing_status="completed"
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)

    # Create user-paper relationship
    from app.db.models import UserPaper
    user_paper = UserPaper(
        user_id=test_user.id,
        paper_id=paper.id,
        status="saved"
    )
    db_session.add(user_paper)
    db_session.commit()

    return paper


@pytest.fixture
def test_knowledge_entry(db_session, test_user, test_paper) -> KnowledgeEntry:
    """Create a test knowledge entry."""
    entry = KnowledgeEntry(
        user_id=test_user.id,
        paper_id=test_paper.id,
        title="Test Knowledge Entry",
        content="This is a test knowledge entry with important insights.",
        entry_type="note",
        tags=["test", "research"]
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.fixture
def mock_ai_service():
    """Mock AI service for testing."""
    original_summarize = ai_service.summarize_paper
    original_extract_insights = ai_service.extract_key_insights
    original_generate_embeddings = ai_service.generate_embeddings

    # Mock the methods
    ai_service.summarize_paper = Mock(return_value={
        "research_question": "How does AI help in research?",
        "methodology": "Literature review and analysis",
        "key_findings": ["AI improves efficiency", "AI reduces errors"],
        "limitations": ["Limited scope", "Need more data"],
        "significance": "Important for future research",
        "future_work": ["Expand to more domains", "Improve algorithms"],
        "confidence_score": 0.85
    })

    ai_service.extract_key_insights = Mock(return_value=[
        {
            "insight": "AI can automate literature reviews",
            "relevance_score": 0.9,
            "section": "Results"
        }
    ])

    ai_service.generate_embeddings = Mock(return_value=[0.1] * 1536)

    yield ai_service

    # Restore original methods
    ai_service.summarize_paper = original_summarize
    ai_service.extract_key_insights = original_extract_insights
    ai_service.generate_embeddings = original_generate_embeddings


@pytest.fixture
def mock_redis():
    """Mock Redis for testing."""
    from unittest.mock import MagicMock
    import redis

    original_from_url = redis.from_url
    mock_redis_client = MagicMock()

    # Mock Redis methods
    mock_redis_client.get.return_value = None
    mock_redis_client.setex.return_value = True
    mock_redis_client.incr.return_value = 1

    redis.from_url = Mock(return_value=mock_redis_client)

    yield mock_redis_client

    # Restore original
    redis.from_url = original_from_url


@pytest.fixture
def sample_paper_data():
    """Sample paper data for testing."""
    return {
        "title": "Artificial Intelligence in Academic Research: A Comprehensive Review",
        "authors": [
            {"name": "Dr. Alice Johnson", "affiliation": "MIT"},
            {"name": "Prof. Bob Chen", "affiliation": "Stanford"}
        ],
        "abstract": "This paper presents a comprehensive review of artificial intelligence applications in academic research. We examine current trends, challenges, and future opportunities.",
        "keywords": ["artificial intelligence", "academic research", "machine learning"],
        "publication_year": 2024,
        "journal": "Journal of AI Research",
        "doi": "10.1000/sample2024"
    }


@pytest.fixture
def sample_knowledge_data():
    """Sample knowledge entry data for testing."""
    return {
        "title": "Key Insights from AI Research Paper",
        "content": "The paper highlights several important points about AI in research: 1) AI can significantly speed up literature reviews, 2) Machine learning algorithms can identify patterns in large datasets, 3) There are ethical considerations that need to be addressed.",
        "entry_type": "summary",
        "tags": ["ai", "research", "insights"],
        "section_reference": "Conclusion"
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "newuser@example.com",
        "password": "securepassword123",
        "full_name": "New Test User",
        "research_interests": ["machine learning", "data science"]
    }


# Test utilities
class TestUtils:
    """Utility functions for testing."""

    @staticmethod
    def create_test_user(db_session, email: str = "test@example.com") -> User:
        """Create a test user with given email."""
        user = User(
            email=email,
            hashed_password=SecurityUtils.get_password_hash("testpassword"),
            full_name="Test User",
            is_active=True,
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    @staticmethod
    def get_auth_headers(user: User) -> dict:
        """Get authorization headers for user."""
        token = SecurityUtils.create_access_token(subject=str(user.id))
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def assert_paper_response(response_data: dict, expected_title: str = None):
        """Assert paper response structure."""
        assert "id" in response_data
        assert "title" in response_data
        assert "authors" in response_data
        assert "created_at" in response_data

        if expected_title:
            assert response_data["title"] == expected_title

    @staticmethod
    def assert_knowledge_response(response_data: dict, expected_title: str = None):
        """Assert knowledge entry response structure."""
        assert "id" in response_data
        assert "title" in response_data
        assert "content" in response_data
        assert "entry_type" in response_data
        assert "created_at" in response_data

        if expected_title:
            assert response_data["title"] == expected_title


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    # Set test environment variables
    import os
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"


# Async test utilities
@pytest.fixture
async def async_client(app) -> AsyncGenerator:
    """Create async test client."""
    from httpx import AsyncClient

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client