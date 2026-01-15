"""Skim - Svalboard Keymap Image Maker.

A command-line tool for generating visual keyboard layout images from QMK,
Vial, and Keybard keymap files. Skim parses keymap definitions and produces
high-quality SVG or PNG images suitable for documentation, reference cards,
or sharing keyboard layouts.

Example:
    Generate images from a keymap file::

        $ skim generate --keymap my-layout.kbi --output-dir ./images

    Generate with custom configuration::

        $ skim generate -k layout.vil -c config.yaml -o ./out -f png

    Create a configuration from a Keybard file::

        $ skim configure -k my-layout.kbi -o skim-config.yaml
"""

from importlib.metadata import metadata

_metadata = metadata("qmk-skim")
__version__ = _metadata["Version"]
__prog_name__ = f"{_metadata['Summary']} (skim)"

# We need this import to happen *after* the initialization of __version__ and
# __prog_name__ so other packages can import it without creating a circular
# depencency.
from skim.ui.cli import main  # noqa: E402

__all__ = ["main"]
