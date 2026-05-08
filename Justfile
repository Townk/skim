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

# Preview every published doc version locally (http://127.0.0.1:8000)
[group('Documentation')]
docs-serve-versions:
    uv run --group docs mike serve

# Deploy current source as the "dev" version (what CI does on push to mainline)
[group('Documentation')]
docs-deploy-dev:
    uv run --group docs mike deploy --push --update-aliases dev mainline

# Deploy a tagged version (e.g. `just docs-deploy-version 0.7`) and alias it as "latest"
[group('Documentation')]
docs-deploy-version VERSION:
    uv run --group docs mike deploy --push --update-aliases {{ VERSION }} latest
    uv run --group docs mike set-default --push latest

# List every deployed doc version on the gh-pages branch
[group('Documentation')]
docs-list-versions:
    uv run --group docs mike list

# Generate TUI screenshots (SVG) into docs/_static/tui/
[group('Documentation')]
screenshots:
    uv run --extra tui python scripts/screenshots.py

# Generate per-option illustration SVGs into docs/_static/options/
[group('Documentation')]
option-images:
    uv run python scripts/option_images.py

# Generate spacing-mock SVGs (greyscale keymap with a single highlighted gap)
[group('Documentation')]
spacing-mocks:
    uv run python scripts/spacing_mocks.py

# Regenerate every image embedded in the published docs
[group('Documentation')]
docs-gen-images: option-images spacing-mocks screenshots
    #!/usr/bin/env bash
    set -euo pipefail
    out=out/docs-keymap-images
    mkdir -p "$out"
    uv run skim generate \
        --config samples/config/SvalCOLEMAK-config.yaml \
        --keymap samples/keymaps/SvalCOLEMAKDHM.vil \
        --layer 1 --layer overview \
        --output-dir "$out" --force
    cp "$out/keymap-layer-1.svg"  docs/_static/keymap-1.svg
    cp "$out/keymap-overview.svg" docs/_static/svalboard-overview.svg
    echo "Wrote docs/_static/keymap-1.svg, docs/_static/svalboard-overview.svg"

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

# End-to-end release: regenerate docs assets, format, check, bump+tag, push, create GitHub Release
[group('Project Actions')]
release:
    #!/usr/bin/env bash
    set -euo pipefail

    # ──────── Preflight ────────
    if [ -n "$(git status --porcelain)" ]; then
        echo "Error: working tree is not clean. Commit or stash first." >&2
        git status --short
        exit 1
    fi

    BRANCH=$(git branch --show-current)
    if [ "$BRANCH" != "mainline" ]; then
        echo "Error: must run from 'mainline' (currently on '$BRANCH')." >&2
        exit 1
    fi

    git fetch origin mainline
    if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/mainline)" ]; then
        echo "Error: local mainline is not in sync with origin/mainline." >&2
        echo "       Run 'git pull --rebase' first." >&2
        exit 1
    fi

    if ! command -v gh >/dev/null 2>&1; then
        echo "Error: 'gh' CLI is required to create the GitHub Release." >&2
        exit 1
    fi

    # ──────── 1. Regenerate doc assets ────────
    echo ""
    echo "==> Regenerating doc images..."
    just docs-gen-images
    if [ -n "$(git status --porcelain docs/_static/)" ]; then
        git add docs/_static/
        git commit -m "chore(docs): regenerate option/screenshot images"
    else
        echo "    (no image changes)"
    fi

    # ──────── 2. Format ────────
    echo ""
    echo "==> Running formatter..."
    just format
    if [ -n "$(git status --porcelain)" ]; then
        git add -u
        git commit -m "chore: ruff format"
    else
        echo "    (no format changes)"
    fi

    # ──────── 3. Checks ────────
    echo ""
    echo "==> Running checks (lint + format-check + type-check)..."
    just check

    # ──────── 4. Strip .dev → release version ────────
    echo ""
    echo "==> Bumping to release version..."
    RELEASE_VERSION=$(uv run python scripts/release_version.py strip-dev)
    echo "    Released: $RELEASE_VERSION"

    echo "==> Promoting CHANGELOG [Unreleased] -> [v$RELEASE_VERSION]..."
    uv run python scripts/release_changelog.py promote "$RELEASE_VERSION"

    git add pyproject.toml CHANGELOG.md
    git commit -m "chore: release v$RELEASE_VERSION"

    # ──────── 5. Tag ────────
    echo ""
    echo "==> Tagging v$RELEASE_VERSION..."
    git tag -a "v$RELEASE_VERSION" -m "Release v$RELEASE_VERSION"

    # ──────── 6. Bump to next dev ────────
    echo ""
    echo "==> Bumping to next dev version..."
    NEW_DEV_VERSION=$(uv run python scripts/release_version.py bump-patch)
    echo "    Next dev: $NEW_DEV_VERSION"
    git add pyproject.toml
    git commit -m "chore: bump version to v$NEW_DEV_VERSION"

    # ──────── 7. Push (atomic: branch + tag in one event) ────────
    echo ""
    echo "==> Pushing to origin..."
    git push --atomic origin mainline "v$RELEASE_VERSION"

    # ──────── 8. Create GitHub Release ────────
    # `gh release create` defaults to a published, non-prerelease release
    # — that fires the `release: types: [released]` event the docs.yml
    # workflow listens for, so the new version's docs auto-deploy.
    echo ""
    echo "==> Creating GitHub Release..."
    gh release create "v$RELEASE_VERSION" \
        --title "Release v$RELEASE_VERSION" \
        --generate-notes

    echo ""
    echo "================================================"
    echo "  Released v$RELEASE_VERSION"
    echo "  Mainline is now at v$NEW_DEV_VERSION"
    echo "================================================"
