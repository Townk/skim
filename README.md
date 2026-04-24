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

The package installs the `skim` command-line tool.

### Generate keymap images

```bash
# Generate from a keymap file
skim generate --keymap my-keymap.kbi --output-dir ./images

# Generate with custom configuration
skim generate --keymap my-keymap.kbi --config skim-config.yaml --output-dir ./images

# Generate specific layers only
skim generate --keymap my-keymap.kbi --layer 1 --layer 3-5 --layer overview
```

### Configuration helper

```bash
# Create a configuration file from QMK color.h
skim configure --qmk-color-header /path/to/qmk/quantum/color.h --output skim-config.yaml
```

## Development

This project uses `uv` for dependency management and `just` as a command runner.

### Setup

```bash
# Clone the repository
git clone https://github.com/Townk/skim.git
cd skim

# Install dependencies
just sync
```

### Testing

```bash
# Run all tests (unit + integration)
just tests

# Run only unit tests
just unit-tests

# Run only integration tests
just integration-tests
```

### Code Quality

Run the full suite of checks (linting, formatting, type checking) before
submitting a PR:

```bash
just check
```

Individual checks:

```bash
just lint      # Run ruff linter
just format    # Format code with ruff
just typecheck # Run basedpyright
```

### Building Documentation

```bash
just build-docs
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
