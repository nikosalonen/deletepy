.PHONY: help install install-dev test lint lint-fix format type-check clean build sync sync-dev upgrade run

help: ## Show this help message
	@echo "Available commands:"
	@echo ""
	@echo "🚀 Recommended (uv-based):"
	@grep -E '^(sync|sync-dev|upgrade|run|test|lint|format|type-check|check-all):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "📦 Legacy (pip-based):"
	@grep -E '^(install|install-dev):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "🛠️  Utilities:"
	@grep -E '^(clean|build|install-pre-commit|update-pre-commit):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# UV-BASED COMMANDS (RECOMMENDED)
# ============================================================================

sync: ## [uv] Install/sync dependencies from lockfile
	uv sync

sync-dev: ## [uv] Install/sync with dev dependencies (recommended)
	uv sync --extra dev

upgrade: ## [uv] Upgrade dependencies and sync
	uv lock --upgrade
	uv sync --extra dev

run: ## [uv] Run deletepy with uv (usage: make run ARGS="doctor dev")
	uv run deletepy $(ARGS)

# ============================================================================
# DEVELOPMENT COMMANDS (UV-AWARE)
# ============================================================================

test: ## Run tests (uses uv if available, falls back to pytest)
	@command -v uv >/dev/null 2>&1 && uv run pytest || pytest

test-coverage: ## Run tests with coverage
	@command -v uv >/dev/null 2>&1 && uv run pytest --cov=src/deletepy --cov-report=html --cov-report=term || pytest --cov=src/deletepy --cov-report=html --cov-report=term

lint: ## Run linting checks (read-only)
	@command -v uv >/dev/null 2>&1 && uv run ruff check src/ tests/ || ruff check src/ tests/

lint-fix: ## Run linting checks and auto-fix issues
	@command -v uv >/dev/null 2>&1 && uv run ruff check src/ tests/ --fix || ruff check src/ tests/ --fix

format: ## Format code
	@command -v uv >/dev/null 2>&1 && uv run ruff format src/ tests/ || ruff format src/ tests/

type-check: ## Run type checking
	@command -v uv >/dev/null 2>&1 && uv run mypy src/ || mypy src/

check-all: ## Run all quality checks
	@command -v uv >/dev/null 2>&1 && uv run ruff check src/ tests/ || ruff check src/ tests/
	@command -v uv >/dev/null 2>&1 && uv run ruff format --check src/ tests/ || ruff format --check src/ tests/
	@command -v uv >/dev/null 2>&1 && uv run mypy src/ || mypy src/
	@command -v uv >/dev/null 2>&1 && uv run pytest || pytest

# ============================================================================
# LEGACY PIP-BASED COMMANDS
# ============================================================================

install: ## [pip] Install the package in development mode (legacy)
	pip install -e .

install-dev: ## [pip] Install with dev dependencies (legacy)
	pip install -e ".[dev]"

# ============================================================================
# UTILITIES
# ============================================================================

clean: ## Clean build artifacts and caches
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

build: ## Build the package
	@command -v uv >/dev/null 2>&1 && uv build || python -m build

install-pre-commit: ## Install pre-commit hooks
	@command -v uv >/dev/null 2>&1 && uv run pre-commit install || pre-commit install

update-pre-commit: ## Update pre-commit hooks
	@command -v uv >/dev/null 2>&1 && uv run pre-commit autoupdate || pre-commit autoupdate
