#!/usr/bin/env python3
"""
Development command-line utilities for the AI Research Assistant project.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(command: str, cwd: str = None) -> int:
    """Run a shell command and return the exit code."""
    print(f"Running: {command}")
    if cwd:
        print(f"Working directory: {cwd}")

    result = subprocess.run(command, shell=True, cwd=cwd)
    return result.returncode


def setup_env():
    """Set up the development environment."""
    print("🚀 Setting up development environment...")

    # Install UV if not already installed
    if subprocess.run("which uv", shell=True, capture_output=True).returncode != 0:
        print("Installing UV...")
        subprocess.run("curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True)

    # Sync dependencies
    print("Installing dependencies...")
    run_command("uv sync")

    # Install pre-commit hooks
    print("Installing pre-commit hooks...")
    run_command("uv run pre-commit install")

    # Create .env file if it doesn't exist
    if not os.path.exists(".env"):
        print("Creating .env file from template...")
        subprocess.run("cp .env.example .env", shell=True)
        print("⚠️  Please edit .env file with your configuration!")

    print("✅ Development environment setup complete!")


def start_dev():
    """Start the development server."""
    print("🔥 Starting development server...")
    run_command("uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000")


def start_prod():
    """Start the production server."""
    print("🚀 Starting production server...")
    run_command("uv run fastapi run app/main.py --host 0.0.0.0 --port 8000")


def run_tests(test_type: str = "all"):
    """Run tests."""
    print(f"🧪 Running {test_type} tests...")

    if test_type == "unit":
        return run_command("uv run pytest tests/unit -v")
    elif test_type == "integration":
        return run_command("uv run pytest tests/integration -v")
    elif test_type == "all":
        return run_command("uv run pytest -v")
    else:
        print(f"Unknown test type: {test_type}")
        return 1


def run_linting():
    """Run linting and formatting."""
    print("🔍 Running linting and formatting...")

    print("Running ruff...")
    run_command("uv run ruff check .")

    print("Running black...")
    run_command("uv run black .")

    print("Running isort...")
    run_command("uv run isort .")

    print("Running mypy...")
    run_command("uv run mypy app/")


def db_migrate(message: str = None):
    """Create and run database migrations."""
    print("🗄️  Running database migrations...")

    if message:
        print(f"Creating migration: {message}")
        run_command(f'uv run alembic revision --autogenerate -m "{message}"')

    print("Applying migrations...")
    run_command("uv run alembic upgrade head")


def db_reset():
    """Reset the database."""
    print("⚠️  Resetting database...")
    response = input("Are you sure you want to reset the database? (y/N): ")

    if response.lower() == 'y':
        run_command("uv run alembic downgrade base")
        run_command("uv run alembic upgrade head")
        print("✅ Database reset complete!")
    else:
        print("Database reset cancelled.")


def start_celery():
    """Start Celery worker and beat."""
    print("⚙️  Starting Celery services...")

    # Start worker in background
    print("Starting Celery worker...")
    subprocess.Popen(
        "uv run celery -A app.services.celery_app worker --loglevel=info",
        shell=True
    )

    # Start beat scheduler
    print("Starting Celery beat...")
    run_command("uv run celery -A app.services.celery_app beat --loglevel=info")


def start_flower():
    """Start Flower monitoring."""
    print("🌸 Starting Flower monitoring...")
    run_command("uv run celery -A app.services.celery_app flower --port=5555")


def docker_dev():
    """Start development environment with Docker."""
    print("🐳 Starting Docker development environment...")

    # Build and start services
    run_command("docker-compose up --build")


def docker_prod():
    """Start production environment with Docker."""
    print("🐳 Starting Docker production environment...")

    # Start with production profile
    run_command("docker-compose --profile production up --build -d")


def backup_db():
    """Backup the database."""
    print("💾 Creating database backup...")

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_research_db_{timestamp}.sql"

    run_command(f"pg_dump research_db > backups/{backup_file}")
    print(f"✅ Database backed up to: backups/{backup_file}")


def load_sample_data():
    """Load sample data for development."""
    print("📊 Loading sample data...")

    # This would run a script to load sample papers, users, etc.
    run_command("uv run python scripts/load_sample_data.py")


def check_health():
    """Check application health."""
    print("🏥 Checking application health...")

    import requests

    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Application is healthy!")
            print(f"   Status: {data.get('status')}")
            print(f"   Version: {data.get('version')}")
            print(f"   Database: {data.get('database')}")
        else:
            print(f"❌ Application unhealthy: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to application: {e}")


def generate_api_docs():
    """Generate API documentation."""
    print("📚 Generating API documentation...")

    # This would generate OpenAPI docs, postman collections, etc.
    run_command("uv run python scripts/generate_docs.py")


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="AI Research Assistant Development Tools")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup command
    subparsers.add_parser("setup", help="Set up development environment")

    # Server commands
    subparsers.add_parser("dev", help="Start development server")
    subparsers.add_parser("prod", help="Start production server")

    # Testing commands
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("--type", choices=["unit", "integration", "all"],
                           default="all", help="Type of tests to run")

    # Code quality commands
    subparsers.add_parser("lint", help="Run linting and formatting")

    # Database commands
    db_parser = subparsers.add_parser("migrate", help="Run database migrations")
    db_parser.add_argument("--message", "-m", help="Migration message")

    subparsers.add_parser("db-reset", help="Reset database")
    subparsers.add_parser("backup", help="Backup database")

    # Celery commands
    subparsers.add_parser("celery", help="Start Celery worker and beat")
    subparsers.add_parser("flower", help="Start Flower monitoring")

    # Docker commands
    subparsers.add_parser("docker-dev", help="Start Docker development environment")
    subparsers.add_parser("docker-prod", help="Start Docker production environment")

    # Utility commands
    subparsers.add_parser("health", help="Check application health")
    subparsers.add_parser("docs", help="Generate API documentation")
    subparsers.add_parser("sample-data", help="Load sample data")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Execute commands
    if args.command == "setup":
        setup_env()
    elif args.command == "dev":
        start_dev()
    elif args.command == "prod":
        start_prod()
    elif args.command == "test":
        exit_code = run_tests(args.type)
        sys.exit(exit_code)
    elif args.command == "lint":
        run_linting()
    elif args.command == "migrate":
        db_migrate(args.message)
    elif args.command == "db-reset":
        db_reset()
    elif args.command == "backup":
        backup_db()
    elif args.command == "celery":
        start_celery()
    elif args.command == "flower":
        start_flower()
    elif args.command == "docker-dev":
        docker_dev()
    elif args.command == "docker-prod":
        docker_prod()
    elif args.command == "health":
        check_health()
    elif args.command == "docs":
        generate_api_docs()
    elif args.command == "sample-data":
        load_sample_data()
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()


if __name__ == "__main__":
    main()