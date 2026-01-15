# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Modified the release workflow to call the publish workflow directly to
  guarantee PyPI always receives a new release version when there is one.

## [0.4.3] - 2026-01-15

### Added

- Version validation script (`scripts/validate_version.py`)
- Git hooks for release automation (`scripts/hooks/`)
- Hook setup script (`scripts/setup-hooks.sh`)

### Changed

- Release workflow now supports both dev and release versions from
  `pyproject.toml`
- Renamed `prerelease.yml` to `release.yml`
- Release automation via `reference-transaction` hook auto-bumps and pushes
  dev version after release push

## [0.4.2] - 2026-01-15

### Added

- Overwrite protection with interactive confirmation prompt when output files
  exist
- `--force` flag for `skim generate` to skip overwrite confirmation
- OpenSpec framework for AI-assisted change management (`openspec/`)

## [0.4.1] - 2026-01-14

### Added

- Pre-release GitHub Actions workflow to auto-build versions on commit
- Package keywords and classifiers in `pyproject.toml`
- Automated coverage badge updates via pre-commit hook
- Sphinx documentation theme changed to Furo with GitHub integration
- New helper script `scripts/update_coverage.py`

### Changed

- Renamed package to `qmk-skim`
- Updated uv build configuration
- Updated README badges for coverage, build status, and PyPI version

## [0.4.0] - 2025-01-14

### Added

- Initial public release of skim (Svalboard Keymap Image Maker)
- CLI tool for generating keyboard layout images from keymap files
- Support for Keybard (`.kbi`), Vial (`.vil`), and QMK c2json (`.json`) formats
- SVG and PNG output format support
- Layer selection options (all, overview, specific layers, ranges)
- Configuration file support for customizing appearance
- Configuration generator for extracting metadata from Keybard files
- QMK color.h import support with lightness/saturation adjustment
- Stdin support for piping keymap data
- Comprehensive test suite with 96% code coverage
- Google-style docstrings for all public APIs
- Sphinx documentation with GitHub Pages deployment workflow
- Pre-commit hooks for ruff formatting/linting and basedpyright type checking

[Unreleased]: https://github.com/Townk/skim/compare/v0.4.3...HEAD
[0.4.3]: https://github.com/Townk/skim/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/Townk/skim/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/Townk/skim/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Townk/skim/releases/tag/v0.4.0
