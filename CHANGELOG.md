# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.3] - 2026-04-24

### Added

- Contextual help system for the TUI configurator — press F1 or Alt+H on any field to see a help modal with field-specific documentation.
  - Per-field markdown help content for all fields across Keyboard, Keycodes, and Style tabs.
  - Vim-style scroll bindings in help modal (j/k, Ctrl+D/U, Ctrl+F/B, G/g).
  - General help fallback with keyboard shortcuts overview.
- `show_layer_connectors` configuration option to toggle layer connector lines in overview images.
- `--title` and `--copyright` options to `configure` command.
- `--layer-count` option with sparse fill logic for `configure` command.
- `--keymap` option to `configure` for Vial and c2json format support.
- Layer move mode to reorder layers in list views.
- Custom `SkimButton` widget with Space and Enter activation.

### Changed

- Renamed `--keybard-keymap` CLI option to `--keymap`.
- Non-standard keycode scanning for configuration generation.
- Skip empty layers and simplify keycode override detection.
- Updated documentation: README, Sphinx docs, and example SVGs to reflect current features.

### Fixed

- Directional focus navigation inside modal dialogs.
- QMK firmware index used for layer lookup, fixing overview rendering issues.
- Circular dots for overview layer connectors (previously rendered as pills).
- Footer keybind display order and styling standardised.
- GitHub Actions and PyPI publishing fixes.

## [0.5.2] - 2026-04-22

### Fixed

- GitHub Actions and PyPI publishing fixes.

## [0.5.1] - 2026-04-22

### Fixed

- GitHub Actions and PyPI publishing fixes.

## [0.5.0] - 2026-04-22

### Added

- Interactive TUI for configuration editing via `skim configure --interactive`.
  - Tabbed interface with Keyboard, Keycodes, and Style tabs.
  - List/detail panels for layers, keycodes, and layer colors.
  - Enter-to-edit, Escape-to-rollback field editing with commit/cancel hints.
  - Add/Remove buttons for layers, keycodes, and layer colors.
  - Color swatches and W3C named color suggestions for color input fields.
  - Gradient preview on dark and light backgrounds with index numbers.
  - Dynamic/Manual gradient type selector for layer colors.
  - Keycode autocomplete and spatial arrow-key focus navigation.
  - Save & quit dialog with confirmation.
- Overview image rendering with layer badges and cluster layout.
  - Dotted connector lines from layer indicator circles to target layers.
  - Intelligent connector routing with per-key escape directions.
- Layer indicator circles on individual layer images.
- Non-sequential layer index support (QMK index independent of config position).
  - Layer index field editing with validation in TUI.
  - Dict-based keymap layers in data model.
- `skim doctor` command with cairo optional dependency check.
- `ConfigGenerator` for generating default and keybard-based configurations.
- Font subsetting support via `FontUsageAnalyzer` and `FontSubsetter`.
- `subtitle` (later renamed to `variant`) field for `KeyboardLayer`.
- Optional `copyright` field in Output configuration.
- `--interactive` and `--config` flags for `configure` command.

### Changed

- Renamed `KeyboardLayer.subtitle` to `variant`.
- Extracted reusable `ListDetailPane` base class for TUI widgets.
- Major overview layout overhaul with improved badge positioning and connector routing.
- Upgraded dependencies.

### Fixed

- Resolved all ruff lint, formatting, and basedpyright errors.
- Granted `id-token` permission for PyPI trusted publishing.
- Numerous TUI layout, focus, and interaction fixes.

## [0.4.4] - 2026-01-19

### Added

- Support for QMK hold-tap keys (e.g., `LT(1, KC_SPC)`, `LSFT_T(KC_A)`).
- Support for complex macro functions via `macro_functions` mapping.
- Support for modifier union arguments (e.g., `OSM(MOD_LCTL|MOD_LSFT)`).

### Changed

- Updated config generator to create `USER##` mappings for custom keycodes found in Keybard files.
- Improved config generator to prevent duplicate custom key entries if they already exist in internal mappings.
- Refactored keycode transformer to use a unified, data-driven pipeline for
  resolving all function-style keycodes (modifiers, layers, macros).
- Modified the release workflow to call the publish workflow directly to
  guarantee PyPI always receives a new release version when there is one.

### Fixed

- Fixed incorrect nesting of `named_colors` in generated configuration files (now directly under `appearance`).
- Fixed issue where layer toggle targets were not identified when using aliased keycodes in `reversed_alias`.
- Fixed bug where `skim generate` would create files even when user aborted the overwrite prompt.
- Fixed inconsistent behavior in `skim configure` by adding an overwrite confirmation prompt (matching `generate`).
- Fixed false positive overwrite prompt in `skim configure` when output is an existing directory (now targets `skim-config.yaml` inside it).

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

[Unreleased]: https://github.com/Townk/skim/compare/v0.5.3...HEAD
[0.5.3]: https://github.com/Townk/skim/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/Townk/skim/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/Townk/skim/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/Townk/skim/compare/v0.4.4...v0.5.0
[0.4.4]: https://github.com/Townk/skim/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/Townk/skim/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/Townk/skim/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/Townk/skim/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Townk/skim/releases/tag/v0.4.0
