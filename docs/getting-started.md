# Getting Started

## Installation

Skim is a Python tool that can be installed using various package managers. We
recommend using `uv` or `pipx` to install it in an isolated environment.

### Using uv (Recommended)

```bash
uv tool install 'qmk-skim[playwright,cairo,tui]'
```

You can upgrade to a new version using:

```bash
uv tool upgrade qmk-skim
```

### Using pipx

```bash
pipx install 'qmk-skim[playwright,cairo,tui]'
```

### Using pip

```bash
pip install 'qmk-skim[playwright,cairo,tui]'
```

## System Dependencies

Skim generates SVG images by default, which requires no external dependencies.
However, if you want to generate raster images (PNG, JPEG, WEBP, AVIF), you
need to install additional software.

### Chromium (Playwright)

To use the Chromium render engine (recommended for best quality):

1. Install the package with the `playwright` extra (if using pip):

    ```bash
    pip install "qmk-skim[playwright]"
    ```

2. Install the browser binaries:

    ```bash
    playwright install chromium
    ```

### Cairo

To use the Cairo render engine:

- **macOS:** Install `cairo` via Homebrew:

    ```bash
    brew install cairo
    ```

- **Linux (Debian/Ubuntu):** Install `libcairo2`:

    ```bash
    sudo apt-get install libcairo2
    ```

- **Windows:** GTK+ runtime is required (instructions vary).

## Checking Your Setup

After installation, run the `doctor` command to verify your environment:

```bash
skim doctor
```

This checks for available render engines (Chromium, Cairo) and reports any
missing optional dependencies.

## Quick Start

1. **Launch the interactive configurator:**

    The easiest way to create a configuration file is the interactive TUI:

    ```bash
    skim configure --interactive
    ```

    This opens a tabbed interface where you can set layer names, colors,
    keycodes, and styling options. Save with `Ctrl+S`.

2. **Or generate a config from a keymap:**

    If you have a Keybard, Vial, or QMK c2json file, extract a config from it:

    ```bash
    skim configure --keymap my-keymap.kbi --output skim-config.yaml
    ```

3. **Generate images:**

    ```bash
    skim generate --keymap my-keymap.kbi --config skim-config.yaml
    ```

    This generates SVG images for all layers plus an overview in the current
    directory.

4. **Explore options:**

    ```bash
    skim generate --help
    skim configure --help
    ```
