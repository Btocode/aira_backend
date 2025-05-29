# AI Research Assistant Backend

This is the backend of the AI Research Assistant project. It is a FastAPI project that provides the API for the Chrome extension and web frontend.

## Features

- **Paper Processing**: Extract and analyze academic papers from various sources
- **AI Integration**: OpenAI GPT-4 and Anthropic Claude for paper summarization
- **Vector Search**: Semantic search using embeddings and Pinecone
- **Citation Networks**: Build and analyze citation relationships
- **Background Processing**: Async paper processing with Celery
- **Authentication**: JWT-based user authentication
- **Database**: PostgreSQL with SQLAlchemy ORM

## Getting Started

To get started clone the repository and run the following commands:

```bash
git clone <repository-url>
cd ai-research-assistant/backend
```

This project uses [UV](https://astral.sh/blog/uv) to manage the virtual environment, packages and the project itself. To install UV run the following command:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installing UV, you can run the following command to install all the project requirements:

```bash
uv sync
```

This should create a virtual environment and install all the requirements.

## Environment Setup

Create a `.env` file in the backend directory:

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `OPENAI_API_KEY`: OpenAI API key
- `PINECONE_API_KEY`: Pinecone API key
- `SECRET_KEY`: JWT secret key

## Database Setup

Run database migrations:

```bash
# Create migration
uv run alembic revision --autogenerate -m "Initial migration"

# Apply migrations
uv run alembic upgrade head
```

## Running the Application

To run the project:

```bash
# Development mode with auto-reload
uv run fastapi dev app/main.py

# Production mode
uv run fastapi run app/main.py
```

The API will be available at `http://localhost:8000`

API Documentation will be available at `http://localhost:8000/docs`

## Background Workers

Start Celery workers for background processing:

```bash
# Start worker
uv run celery -A app.services.celery_app worker --loglevel=info

# Start flower for monitoring (optional)
uv run celery -A app.services.celery_app flower
```

## Adding Dependencies

To add a new dependency to the project:

```bash
uv add <package-name>
```

For development dependencies:

```bash
uv add --dev <package-name>
```

## Running Tests

Run all tests:

```bash
uv run pytest
```

Run specific test types:

```bash
# Unit tests only
uv run pytest tests/unit

# Integration tests only
uv run pytest tests/integration

# Specific test file
uv run pytest tests/unit/test_paper_service.py
```

## Code Quality

Run linting and formatting:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run all checks
uv run pre-commit run --all-files

# Run specific tools
uv run ruff check .
uv run black .
uv run mypy .
```

## Project Structure

```
app/
├── api/                    # API routes and endpoints
│   ├── decorators.py      # Route decorators
│   └── v1/                # API version 1
├── app_instance.py        # FastAPI app instance
├── core/                  # Core functionality
│   ├── config.py         # Configuration settings
│   ├── security.py       # Authentication & authorization
│   └── app_logging.py    # Logging configuration
├── db/                    # Database layer
│   ├── models.py         # SQLAlchemy models
│   ├── database.py       # Database connection
│   └── queries/          # Database queries
├── schemas/               # Pydantic models
├── services/              # Business logic
│   ├── ai_service.py     # AI integration
│   ├── paper_service.py  # Paper processing
│   └── celery_app.py     # Background tasks
├── utils/                 # Utility functions
└── main.py               # Application entry point
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/me` - Get current user

### Papers
- `POST /api/v1/papers/` - Add paper from URL
- `GET /api/v1/papers/{paper_id}` - Get paper details
- `POST /api/v1/papers/search` - Search papers
- `GET /api/v1/papers/{paper_id}/summary` - Get AI summary

### Knowledge Base
- `GET /api/v1/knowledge/` - Get user's knowledge entries
- `POST /api/v1/knowledge/` - Create knowledge entry
- `GET /api/v1/knowledge/search` - Semantic search

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## License

MIT License