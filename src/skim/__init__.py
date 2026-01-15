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
__prog_name__ = f"{_metadata['Summary']} ({_metadata['Name']})"


def main() -> None:
    """Entry point placeholder for the skim package.

    This function serves as a simple entry point for package verification.
    The actual CLI functionality is provided by the :mod:`skim.ui.cli` module
    through Click commands.

    Note:
        For CLI usage, invoke ``skim`` directly or use
        ``python -m skim.ui.cli``.
    """
    print("Hello from skim!")
