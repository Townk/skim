# Project Context

## Purpose
Svalboard Keymap Image Maker (skim). A tool to generate keymap images of Svalboard keyboard firmwares.

## Tech Stack
- Python 3.10+
- Click (CLI)
- PyYAML (Configuration)
- Typst (Rendering)
- uv (Build system)
- pytest (Testing)
- ruff (Linting & Formatting)
- basedpyright (Type checking)

## Project Conventions

### Code Style
- Follows `ruff` configuration (Standard Python style, isort, etc.)
- 88 character line length
- Double quotes for strings
- Type hints required (standard mode via basedpyright)

### Architecture Patterns
- CLI application using `click`
- Entry point: `skim:main`
- Source code located in `src/`
- Tests located in `tests/`
- Output generation in `out/` (implied by coverage config)

### Testing Strategy
- `pytest` for unit and integration tests
- Coverage reporting (`pytest-cov`) required (fail under 95%)

### Git Workflow
- Standard feature branch workflow (implied)

## Domain Context
- **Svalboard**: A specific type of ergonomic keyboard.
  - **About its layouts**: [Svalboard Layouts](https://svalboard.com/pages/the-layout).
  - **About its keys**: [Svalboard Keys](https://svalboard.com/pages/key-mechanism).
  - **Common questions**: [Svalboard FAQ](https://svalboard.com/pages/faqs-1).
- **QMK**: The open source firmware used by Svalboard keyboards.
- **Keymap**: Configuration of keys on the keyboard.
- **Vial**: A web-UI configurator for QMK-based keyboards and also a fork of
  the official firmware with changes to support the configurator.
- **Keybard**: The web-UI configurator specifically for Svalboard keyboards.
- **Typst**: A programmable typesetting system used here for image generation.

## Important Constraints
- Python 3.10 minimum requirement.
- Must maintain high test coverage (95%+).
