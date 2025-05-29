# AI Research Assistant Backend - Getting Started

This comprehensive guide will help you set up and run the AI Research Assistant backend from scratch.

## 🏗️ What We've Built

A production-ready FastAPI backend with:

### Core Features
- **Paper Processing**: Extract and analyze academic papers from URLs (arXiv, journals, PDFs)
- **AI Integration**: OpenAI GPT-4 and Anthropic Claude for paper summarization and analysis
- **Knowledge Base**: Personal research knowledge management with semantic search
- **Citation Networks**: Visualize and analyze paper relationships
- **Background Processing**: Async paper processing with Celery
- **User Management**: JWT authentication with subscription tiers

### Technical Stack
- **Framework**: FastAPI with async support
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache/Queue**: Redis for caching and Celery background tasks
- **AI Services**: OpenAI GPT-4, text embeddings, PDF processing
- **Package Manager**: UV for fast Python package management
- **Code Quality**: Pre-commit hooks, Ruff, Black, MyPy
- **Testing**: Pytest with fixtures and mocking
- **Deployment**: Docker with multi-stage builds

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Git

### 1. Clone and Setup
```bash
git clone <your-repo-url>
cd ai-research-assistant/backend

# Use our convenient setup command
make setup
```

### 2. Configure Environment
```bash
# Edit your environment variables
cp .env.example .env
# Add your OpenAI API key and database credentials
```

### 3. Start Development
```bash
# Start all services with Docker (recommended)
make docker-dev

# OR start manually
make db-migrate
make dev
```

### 4. Test the API
```bash
# Check health
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs
```

## 📋 Detailed Setup

### Option 1: Docker Development (Recommended)

```bash
# Start everything (API, database, Redis, Celery)
make docker-dev

# In background
make docker-dev-bg

# Check logs
make logs
```

### Option 2: Manual Setup

1. **Install Dependencies**
```bash
# Install UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
make install
```

2. **Database Setup**
```bash
# Start PostgreSQL and Redis (via Docker or locally)
docker run -d --name postgres -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Run migrations
make db-migrate
```

3. **Start Services**
```bash
# Terminal 1: API Server
make dev

# Terminal 2: Background Worker
make celery

# Terminal 3: Task Scheduler
make celery-beat

# Terminal 4: Monitoring (optional)
make flower
```

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration

# Run with coverage
make test-cov

# Check code quality
make lint
```

## 📡 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login-json` - User login
- `GET /api/v1/auth/me` - Current user info

### Papers
- `POST /api/v1/papers/` - Add paper from URL
- `GET /api/v1/papers/` - Get user's papers
- `GET /api/v1/papers/{id}` - Get paper details
- `GET /api/v1/papers/{id}/summary` - Get AI summary
- `POST /api/v1/papers/search` - Search papers

### Knowledge Base
- `GET /api/v1/knowledge/` - Get knowledge entries
- `POST /api/v1/knowledge/` - Create knowledge entry
- `POST /api/v1/knowledge/search` - Search knowledge

### Full API documentation at `http://localhost:8000/docs`

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Required
DATABASE_URL=postgresql://postgres:password@localhost:5432/research_db
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-your-openai-key-here
SECRET_KEY=your-super-secret-key-change-in-production

# Optional
ANTHROPIC_API_KEY=your-anthropic-key
PINECONE_API_KEY=your-pinecone-key
DEBUG=true
ENVIRONMENT=development
```

### Subscription Tiers
- **Free**: 5 paper summaries/month
- **Researcher**: Unlimited summaries, advanced features ($29/month)
- **Institution**: Team features, API access ($199/month)

## 📊 Development Workflow

### Daily Development
```bash
# Quick start for new features
make quick-start

# Code → Test → Lint cycle
make quick-test

# Database changes
make db-migrate-create MESSAGE="Add new feature"
make db-migrate
```

### Code Quality
```bash
# Pre-commit hooks (automatic)
make pre-commit

# Manual checks
make lint
make security
```

### Debugging
```bash
# Check application health
make health

# View logs
make logs

# Monitor in real-time
make monitor
```

## 🚀 Production Deployment

### Docker Production
```bash
# Build production image
make build

# Deploy with docker-compose
make docker-prod
```

### Environment Setup
1. Set `ENVIRONMENT=production` in .env
2. Use strong `SECRET_KEY`
3. Configure proper database URLs
4. Set up monitoring and logging
5. Configure reverse proxy (nginx)

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│   PostgreSQL    │    │      Redis      │
│                 │    │                 │    │                 │
│ • Authentication│    │ • User data     │    │ • Caching       │
│ • Paper mgmt    │    │ • Papers        │    │ • Session store │
│ • AI integration│    │ • Knowledge     │    │ • Task queue    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                                              │
         └─────────────────┐                          │
                           │                          │
┌─────────────────┐    ┌──▼──────────────┐    ┌──────▼──────┐
│   Celery Beat   │    │ Celery Workers  │    │   Flower    │
│                 │    │                 │    │             │
│ • Scheduled     │    │ • Paper proc.   │    │ • Monitor   │
│   tasks         │    │ • AI analysis   │    │ • Web UI    │
│ • Maintenance   │    │ • Background    │    │             │
└─────────────────┘    └─────────────────┘    └─────────────┘
```

## 🤝 Contributing

1. **Setup development environment**
   ```bash
   make setup
   ```

2. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature
   ```

3. **Make changes and test**
   ```bash
   make quick-test
   ```

4. **Submit pull request**
   - Code will be automatically checked by pre-commit hooks
   - Tests must pass
   - Documentation should be updated

## 📚 Key Files & Directories

```
backend/
├── app/
│   ├── api/v1/           # API endpoints
│   ├── core/             # Configuration, security, logging
│   ├── db/               # Database models and queries
│   ├── schemas/          # Pydantic models
│   ├── services/         # Business logic
│   └── utils/            # Utility functions
├── tests/                # Test suite
├── scripts/              # Development scripts
├── alembic/              # Database migrations
├── docker-compose.yml    # Local development
├── Dockerfile            # Container build
├── Makefile             # Development commands
└── pyproject.toml       # Project configuration
```

## 🐛 Troubleshooting

### Common Issues

1. **Database connection failed**
   ```bash
   # Check if PostgreSQL is running
   docker ps | grep postgres

   # Reset database
   make db-reset
   ```

2. **Redis connection failed**
   ```bash
   # Check if Redis is running
   docker ps | grep redis

   # Restart Redis
   docker restart redis
   ```

3. **Import errors**
   ```bash
   # Reinstall dependencies
   make clean
   make install
   ```

4. **Tests failing**
   ```bash
   # Check environment
   make info

   # Run specific test
   uv run pytest tests/unit/test_specific.py -v
   ```

### Getting Help

- **Health Check**: `make health`
- **Environment Info**: `make info`
- **Logs**: `make logs`
- **Documentation**: http://localhost:8000/docs

## 🎯 Next Steps

1. **Basic Setup**: Follow the Quick Start guide
2. **Explore API**: Use the interactive docs at `/docs`
3. **Add Features**: Check the issues/roadmap
4. **Deploy**: Set up production environment
5. **Scale**: Add more workers, optimize database

## 📈 Performance Tips

- Use `make docker-dev` for consistent environment
- Monitor with `make flower` (Celery tasks)
- Check `make health` regularly
- Use database indexes for large datasets
- Configure Redis appropriately for your workload

## 🐳 Docker Setup

### Docker Compose Configuration
Create a `docker-compose.yml` file in the project root:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/research_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=research_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  celery:
    build: .
    command: celery -A app.services.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/research_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - api
      - redis

  celery-beat:
    build: .
    command: celery -A app.services.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/research_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - api
      - redis

  flower:
    build: .
    command: celery -A app.services.celery_app flower
    ports:
      - "5555:5555"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/research_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - api
      - redis

volumes:
  postgres_data:
```

### Dockerfile
Create a `Dockerfile` in the project root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy project files
COPY . .

# Install dependencies
RUN uv sync

# Run the application
CMD ["uv", "run", "fastapi", "run", "app/main.py"]
```

### Running with Docker
```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## 🔧 Environment Variables

### Required Variables
```bash
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/research_db

# Redis
REDIS_URL=redis://localhost:6379/0

# API Keys
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key
PINECONE_API_KEY=your-pinecone-key

# Security
SECRET_KEY=your-super-secret-key-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
DEBUG=true
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Optional Variables
```bash
# Email (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Monitoring
SENTRY_DSN=your-sentry-dsn
NEW_RELIC_LICENSE_KEY=your-new-relic-key

# Feature Flags
ENABLE_EMAIL_NOTIFICATIONS=true
ENABLE_ANALYTICS=true
ENABLE_RATE_LIMITING=true

# Cache Settings
CACHE_TTL=3600
CACHE_PREFIX=research_assistant

# API Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600
```

## 📦 Database Management

### Backup and Restore
```bash
# Backup database
pg_dump -U postgres research_db > backup.sql

# Restore database
psql -U postgres research_db < backup.sql

# Backup with Docker
docker-compose exec db pg_dump -U postgres research_db > backup.sql

# Restore with Docker
docker-compose exec -T db psql -U postgres research_db < backup.sql
```

### Migration Management
```bash
# Create new migration
make db-migrate-create MESSAGE="Add new feature"

# Apply migrations
make db-migrate

# Rollback last migration
make db-migrate-rollback

# Check migration status
make db-migrate-status

# Fix failed migrations
make db-migrate-fix
```

---

🚀 **You're ready to build amazing AI-powered research tools!**

For questions or issues, check the troubleshooting section or create an issue in the repository.