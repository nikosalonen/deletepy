.PHONY: help install install-dev test lint lint-fix format type-check clean build uv-upgrade uv-install uv-install-dev

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package in development mode
	pip install -e .

install-dev: ## Install the package with development dependencies
	pip install -e ".[dev]"

test: ## Run tests
	pytest

test-coverage: ## Run tests with coverage
	pytest --cov=src/deletepy --cov-report=html --cov-report=term

lint: ## Run linting checks (read-only)
	ruff check src/ tests/

lint-fix: ## Run linting checks and auto-fix issues
	ruff check src/ tests/ --fix

format: ## Format code
	ruff format src/ tests/

type-check: ## Run type checking
	mypy src/

check-all: ## Run all quality checks
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/
	pytest

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

build: ## Build the package
	python -m build

install-pre-commit: ## Install pre-commit hooks
	pre-commit install

update-pre-commit: ## Update pre-commit hooks
	pre-commit autoupdate

uv-upgrade: ## Upgrade dependencies using uv (lock + sync dev)
	uv lock --upgrade
	uv sync --group dev

uv-install: ## Create/refresh .venv using uv (default deps from lockfile)
	uv sync

uv-install-dev: ## Create/refresh .venv with dev group using uv
	uv sync --group dev
