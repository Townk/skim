# Copyright (c) 2025 Thiago Alves
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
# ------------------------------------------------------------------------------
# Convenience

# Default recipe: show available commands
default:
    @just --list --unsorted --list-heading $'\e[1m\e[32mAvailable Recipes\n-----------------\n\e[0m'

# Run the skim CLI (pass arguments after --)
skim *ARGS:
    uv run skim {{ ARGS }}

# ------------------------------------------------------------------------------
# Bootstrap

# One-command setup for new developers
[group('Bootstrap')]
setup:
    uv sync --all-groups --all-extras

# Install Playwright browsers (needed for PNG export and integration tests)
[group('Bootstrap')]
install-browsers:
    uv run playwright install chromium

# ------------------------------------------------------------------------------
# Tests

# Run unit tests (Target: < 10s)
[group('Tests')]
test-unit *PYTEST_ARGS:
    uv run --group test pytest tests/unit {{ PYTEST_ARGS }}

# Run snapshot tests
[group('Tests')]
test-snapshot *PYTEST_ARGS:
    uv run --group test pytest tests/snapshot {{ PYTEST_ARGS }}

# Run integration tests (requires Playwright browsers)
[group('Tests')]
test-integration *PYTEST_ARGS: install-browsers
    uv run --group test pytest tests/integration -m integration {{ PYTEST_ARGS }}

# Run the full test suite with coverage and HTML report
[group('Tests')]
test *PYTEST_ARGS: install-browsers
    mkdir -p out/tests
    uv run --group test pytest tests/ --cov=skim --cov-report=html:out/coverage --cov-report=term-missing --html=out/tests/test-report.html --junitxml=out/tests/test-report.xml {{ PYTEST_ARGS }}

# ------------------------------------------------------------------------------
# Quality & Code Conformity

# Check for linting issues
[group('Code Quality')]
lint:
    uv run --group lint ruff check src tests

# Automatically fix fixable linting issues
[group('Code Quality')]
lint-fix:
    uv run --group lint ruff check --fix src tests

# Run type checking
[group('Code Quality')]
type-check:
    uv run --group lint basedpyright

# Format code to standard style
[group('Code Quality')]
format:
    uv run --group lint ruff format src tests

# Check code formatting (without modifying files)
[group('Code Quality')]
format-check:
    uv run --group lint ruff format --check src tests

# Run all checks: lint, format check, and type check
[group('Code Quality')]
check: lint type-check format-check

# ------------------------------------------------------------------------------
# Documentation

# Build the documentation (strict: fail on warnings)
[group('Documentation')]
docs:
    uv run --group docs mkdocs build --strict --site-dir out/docs

# Launch local documentation server with live reload
[group('Documentation')]
docs-serve:
    uv run --group docs mkdocs serve --livereload

# Deploy documentation to GitHub Pages
[group('Documentation')]
docs-deploy:
    uv run --group docs mkdocs gh-deploy --force

# Generate TUI screenshots (SVG) into docs/_static/tui/
[group('Documentation')]
screenshots:
    uv run --extra tui python scripts/screenshots.py

# Generate per-option illustration SVGs into docs/_static/options/
[group('Documentation')]
option-images:
    uv run python scripts/option_images.py

# ------------------------------------------------------------------------------
# Project Actions

# Build the project artifacts
[group('Project Actions')]
build:
    uv build

# Clean build artifacts and caches
[group('Project Actions')]
clean:
    rm -rf out/ dist/ build/ .pytest_cache/ .ruff_cache/ .coverage
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Full CI pipeline: all checks + all tests
[group('Project Actions')]
ci: check test
