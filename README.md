# Svalboard Keymap Image Maker (skim)

[![Coverage](https://img.shields.io/badge/coverage-96%25-brightgreen.svg)](https://github.com/Townk/skim)
[![Python Version](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://github.com/Townk/skim/actions/workflows/prerelease.yml/badge.svg)](https://github.com/Townk/skim/actions/workflows/prerelease.yml)
[![PyPI version](https://badge.fury.io/py/qmk-skim.svg)](https://badge.fury.io/py/qmk-skim)

A Python CLI tool for generating keymap layout images for the [Svalboard](https://svalboard.com) keyboard.

## Features

- Generate individual layer keymap images
- Generate overview images showing all layers
- Support for multiple keymap formats:
  - Keybard (`.kbi`)
  - Vial (`.vil`)
  - QMK c2json (`.json`)
- Configurable colors and appearance
- High-quality SVG and PNG output

## Installation

```bash
pip install skim
```

## Usage

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

### Setup

```bash
# Clone the repository
git clone https://github.com/your-repo/skim.git
cd skim

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv sync --dev
```

### Testing

```bash
# Run tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/unit/domain/test_colors.py
```

### Building Documentation

```bash
cd docs
sphinx-build -b html . _build
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
