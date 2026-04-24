# qmk-skim (Svalboard Keymap Image Maker)

[![Coverage](https://img.shields.io/badge/coverage-81%25-yellowgreen.svg)](https://github.com/Townk/skim)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://github.com/Townk/skim/actions/workflows/release.yml/badge.svg)](https://github.com/Townk/skim/actions/workflows/release.yml)
[![PyPI version](https://badge.fury.io/py/qmk-skim.svg)](https://badge.fury.io/py/qmk-skim)

A Python CLI tool for generating high-quality keymap layout images for the
[Svalboard](https://svalboard.com) keyboard.

## Features

- Generate individual layer keymap images with layer indicator circles
- Generate overview images showing all layers with connector lines
- Interactive TUI configurator for editing configuration files
- System dependency checker (`skim doctor`)
- Support for multiple keymap formats:
  - Keybard (`.kbi`)
  - Vial (`.vil`)
  - QMK c2json (`.json`)
- Configurable colors, layer names, and appearance
- High-quality output in multiple formats:
  - Vector: SVG
  - Raster: PNG, JPEG, WEBP, AVIF
- Stdin support for piping keymap data in scripts

## Installation

You can install `qmk-skim` using `pip`, `pipx`, or `uv`.

### Using uv (Recommended)

```bash
uv tool install qmk-skim
```

### Using pipx

```bash
pipx install qmk-skim
```

### Using pip

```bash
pip install qmk-skim
```

## Usage

The package installs the `skim` command-line tool, but if you prefer to use the
tool without installing it, you can use `uvx`:

```bash
uvx --python 3.10 --from 'qmk-skim[cairo,playwright]' skim doctor
```

### Check your environment

```bash
# Verify system dependencies (render engines, etc.)
skim doctor
```

### Generate keymap images

```bash
# Generate all layers + overview from a keymap file
skim generate --keymap my-keymap.kbi --output-dir ./images

# Generate with custom configuration
skim generate --keymap my-keymap.kbi --config skim-config.yaml --output-dir ./images

# Generate specific layers only
skim generate --keymap my-keymap.kbi --layer 1 --layer 3-5 --layer overview

# Generate PNG output (requires Chromium or Cairo)
skim generate --keymap my-keymap.kbi --format png --output-dir ./images

# Read keymap from stdin
cat my-keymap.json | skim generate - --output-dir ./images
```

### Configure appearance

```bash
# Launch the interactive TUI configurator
skim configure --interactive

# Edit an existing configuration file in the TUI
skim configure --interactive --config skim-config.yaml

# Generate a config from a Keybard keymap (extracts layer colors, names, custom keycodes)
skim configure --keymap my-keymap.kbi --output skim-config.yaml

# Import QMK named colors from color.h
skim configure --keymap my-keymap.kbi --qmk-color-header /path/to/color.h --output skim-config.yaml
```

## Development

This project uses `uv` for dependency management and `just` as a command runner.

### Setup

```bash
# Clone the repository
git clone https://github.com/Townk/skim.git
cd skim

# Install dependencies (dev + docs + extras)
just sync
```

### Testing

```bash
# Run all tests (unit + integration) with coverage
just tests

# Run only unit tests
just unit-tests

# Run only integration tests
just integration-tests
```

### Code Quality

```bash
# Run all checks (lint, format, type check)
just check

# Quick feedback loop (format + lint + typecheck)
just quick-check

# Full CI pipeline (all checks + all tests)
just ci
```

Individual checks:

```bash
just lint          # Run ruff linter
just format        # Format code with ruff
just format-check  # Check formatting without modifying
just fix           # Auto-fix lint issues
just typecheck     # Run basedpyright
```

### Building

```bash
just build       # Build the package
just build-docs  # Build Sphinx documentation
just serve-docs  # Build and open documentation in browser
just clean       # Remove build artifacts and caches
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
