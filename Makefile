# AI Research Assistant Backend Makefile
# Convenience commands for development and deployment

.PHONY: help setup dev prod test lint clean docker-dev docker-prod

# Default target
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development Environment Setup
setup: ## Set up development environment
	@echo "🚀 Setting up development environment..."
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "Installing UV..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi
	uv sync
	uv run pre-commit install
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "⚠️  Please edit .env file with your configuration!"; \
	fi
	@echo "✅ Development environment setup complete!"

# Development Server
dev: ## Start development server
	@echo "🔥 Starting development server..."
	uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000

# Production Server
prod: ## Start production server
	@echo "🚀 Starting production server..."
	uv run fastapi run app/main.py --host 0.0.0.0 --port 8000

# Testing
test: ## Run all tests
	@echo "🧪 Running all tests..."
	uv run pytest -v

test-unit: ## Run unit tests only
	@echo "🧪 Running unit tests..."
	uv run pytest tests/unit -v

test-integration: ## Run integration tests only
	@echo "🧪 Running integration tests..."
	uv run pytest tests/integration -v

test-cov: ## Run tests with coverage
	@echo "🧪 Running tests with coverage..."
	uv run pytest --cov=app --cov-report=html --cov-report=term

# Code Quality
lint: ## Run linting and formatting
	@echo "🔍 Running linting and formatting..."
	uv run ruff check . --fix
	uv run black .
	uv run isort .

lint-check: ## Check linting without fixing
	@echo "🔍 Checking code quality..."
	uv run ruff check .
	uv run black --check .
	uv run isort --check-only .
	uv run mypy app/

# Database Operations
db-migrate: ## Run database migrations
	@echo "🗄️  Running database migrations..."
	uv run alembic upgrade head

db-migrate-create: ## Create new migration (use MESSAGE="description")
	@echo "🗄️  Creating database migration..."
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Error: Please provide MESSAGE='migration description'"; \
		exit 1; \
	fi
	uv run alembic revision --autogenerate -m "$(MESSAGE)"

db-reset: ## Reset database (WARNING: destructive)
	@echo "⚠️  This will reset the database. Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	uv run alembic downgrade base
	uv run alembic upgrade head
	@echo "✅ Database reset complete!"

db-backup: ## Backup database
	@echo "💾 Creating database backup..."
	mkdir -p backups
	pg_dump research_db > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Database backed up!"

# Background Services
celery: ## Start Celery worker
	@echo "⚙️  Starting Celery worker..."
	uv run celery -A app.services.celery_app worker --loglevel=info

celery-beat: ## Start Celery beat scheduler
	@echo "⏰ Starting Celery beat..."
	uv run celery -A app.services.celery_app beat --loglevel=info

flower: ## Start Flower monitoring
	@echo "🌸 Starting Flower monitoring..."
	uv run celery -A app.services.celery_app flower --port=5555

# Docker Operations
docker-dev: ## Start development environment with Docker
	@echo "🐳 Starting Docker development environment..."
	docker-compose up --build

docker-dev-bg: ## Start development environment in background
	@echo "🐳 Starting Docker development environment in background..."
	docker-compose up --build -d

docker-prod: ## Start production environment with Docker
	@echo "🐳 Starting Docker production environment..."
	docker-compose --profile production up --build -d

docker-stop: ## Stop all Docker containers
	@echo "🛑 Stopping Docker containers..."
	docker-compose down

docker-clean: ## Clean Docker containers and volumes
	@echo "🧹 Cleaning Docker containers and volumes..."
	docker-compose down -v --remove-orphans
	docker system prune -f

# Utility Commands
health: ## Check application health
	@echo "🏥 Checking application health..."
	@curl -s http://localhost:8000/health | python -m json.tool || echo "❌ Application not responding"

logs: ## Show application logs (Docker)
	docker-compose logs -f api

logs-celery: ## Show Celery worker logs (Docker)
	docker-compose logs -f celery_worker

install: ## Install dependencies
	@echo "📦 Installing dependencies..."
	uv sync

install-dev: ## Install development dependencies
	@echo "📦 Installing development dependencies..."
	uv sync --dev

update: ## Update dependencies
	@echo "⬆️  Updating dependencies..."
	uv sync --upgrade

# Cleanup
clean: ## Clean up temporary files
	@echo "🧹 Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

clean-all: clean ## Clean everything including venv
	rm -rf .venv

# Documentation
docs: ## Generate API documentation
	@echo "📚 Generating API documentation..."
	@echo "API docs available at: http://localhost:8000/docs"
	@echo "ReDoc available at: http://localhost:8000/redoc"

# Git hooks and pre-commit
pre-commit: ## Run pre-commit on all files
	@echo "🔍 Running pre-commit hooks..."
	uv run pre-commit run --all-files

# Load sample data for development
sample-data: ## Load sample data for development
	@echo "📊 Loading sample data..."
	uv run python scripts/load_sample_data.py

# Security checks
security: ## Run security checks
	@echo "🔒 Running security checks..."
	uv run bandit -r app/
	uv run safety check

# Performance and profiling
profile: ## Profile the application
	@echo "📈 Starting application with profiling..."
	uv run python -m cProfile -o profile_stats.prof app/main.py

# Deployment helpers
build: ## Build application for deployment
	@echo "🏗️  Building application..."
	docker build -t ai-research-assistant:latest .

deploy-staging: ## Deploy to staging
	@echo "🚀 Deploying to staging..."
	@echo "Staging deployment not configured yet"

deploy-prod: ## Deploy to production
	@echo "🚀 Deploying to production..."
	@echo "Production deployment not configured yet"

# Quick development workflow
quick-start: setup db-migrate dev ## Quick start for new developers

quick-test: lint test ## Quick test run

# Monitor application
monitor: ## Monitor application resources
	@echo "📊 Monitoring application..."
	@while true; do \
		echo "=== $$(date) ==="; \
		curl -s http://localhost:8000/health | python -m json.tool; \
		echo ""; \
		sleep 5; \
	done

# Environment info
info: ## Show environment information
	@echo "📋 Environment Information:"
	@echo "Python version: $$(python --version)"
	@echo "UV version: $$(uv --version 2>/dev/null || echo 'Not installed')"
	@echo "Docker version: $$(docker --version 2>/dev/null || echo 'Not installed')"
	@echo "Git version: $$(git --version 2>/dev/null || echo 'Not installed')"
	@echo "Current directory: $$(pwd)"
	@echo "Virtual environment: $$(echo $$VIRTUAL_ENV)"
	@if [ -f .env ]; then echo ".env file: ✅ Present"; else echo ".env file: ❌ Missing"; fi