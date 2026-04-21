# Justfile for skim (Svalboard Keymap Image Maker)

# Default recipe: show available commands
default:
    @just --list

# Recipe to create a virtual environment
venv:
    uv venv .venv
    # Optional: activate the environment (requires sourcing in the shell)
    # echo "Run 'source ${VENV_DIR}/bin/activate' to activate the environment."

# Sync dependencies (dev + docs)
sync: venv
    uv sync --dev --group docs --extra playwright --extra cairo

# Run all tests (unit + integration)
tests: install-browsers
    uv run pytest tests/ --cov=skim --cov-report=html:out/coverage --cov-report=term-missing --html=out/tests/test-report.html --junitxml=out/tests/test-report.xml

# Run only unit tests
unit-tests:
    uv run pytest tests/unit/

# Run only integration tests (requires Playwright browsers)
integration-tests: install-browsers
    uv run pytest tests/integration/ -m integration

# Run all checks: lint, format check, and type check
check: lint format-check typecheck

# Run linter
lint:
    uv run ruff check src tests

# Check code formatting (without modifying files)
format-check:
    uv run ruff format --check src tests

# Run type checker
typecheck:
    uv run basedpyright

# Format code
format:
    uv run ruff format src tests

# Fix linting issues automatically
fix:
    uv run ruff check --fix src tests

# Build documentation
build-docs:
    uv run sphinx-build -b html docs out/docs

# Serve documentation locally (build first, then open)
serve-docs: build-docs
    @echo "Documentation built at out/docs/index.html"
    open out/docs/index.html || xdg-open out/docs/index.html 2>/dev/null || echo "Open out/docs/index.html in your browser"

# Run the skim CLI (pass arguments after --)
skim *ARGS:
    uv run skim {{ ARGS }}

# Build the package
build:
    uv build

# Clean build artifacts and caches
clean:
    rm -rf out/ dist/ build/ .pytest_cache/ .ruff_cache/ .coverage
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Install Playwright browsers (needed for PNG export and integration tests)
install-browsers:
    uv run playwright install chromium

# Run a quick check (fast feedback loop: format + lint + typecheck)
quick-check: format lint typecheck

# Full CI pipeline: all checks + all tests
ci: check tests
