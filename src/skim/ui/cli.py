"""Command-line interface for Skim keyboard layout image generator.

This module provides the CLI entry points for the skim tool using Click.
It defines the main command group and subcommands for generating keymap
images and configuration files.

Commands:
    - ``skim generate``: Generate keymap visualization images
    - ``skim configure``: Generate or output configuration files

Example:
    Generate images from a keymap file::

        $ skim generate --keymap layout.kbi --output-dir ./images

    Generate with custom configuration::

        $ skim -v INFO generate -k layout.vil -c config.yaml -f png

    Create configuration from Keybard file::

        $ skim configure -k layout.kbi -o skim-config.yaml

    Read keymap from stdin::

        $ cat keymap.json | skim generate - -o ./out
"""

import sys
from pathlib import Path

import click

from skim import __prog_name__, __version__
from skim.application.config_generator import ConfigGenerator
from skim.application.image_generator import ImageGenerator
from skim.ui.logging_config import setup_logging


class AliasedGroup(click.Group):
    """Click Group that supports command name abbreviation.

    Allows users to invoke commands using unique prefixes instead of
    full command names. For example, ``skim gen`` matches ``generate``
    if no other command starts with "gen".

    Example:
        $ skim gen --keymap foo.kbi  # Matches 'generate'
        $ skim conf -k bar.kbi       # Matches 'configure'
    """

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Resolve a command by name or unique prefix.

        Args:
            ctx: Click context.
            cmd_name: Command name or prefix to resolve.

        Returns:
            Matching Command object, or None if not found.

        Raises:
            click.UsageError: If prefix matches multiple commands.
        """
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None
        if len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple:
        """Resolve command and return full name for help text."""
        cmd_name, cmd, args = super().resolve_command(ctx, args)
        return cmd.name if cmd else cmd_name, cmd, args


@click.group(cls=AliasedGroup)
@click.version_option(version=__version__, prog_name=__prog_name__)
@click.option(
    "--verbosity",
    "-v",
    default="WARNING",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE"], case_sensitive=False
    ),
    help="Logging verbosity level.",
)
@click.option(
    "--quiet", "-q", is_flag=True, help="Silence all output (overrides --verbosity)."
)
def main(verbosity: str, quiet: bool) -> None:
    """Svalboard Keymap Image Maker (skim).

    Generate visual keyboard layout images from keymap configuration files.
    Supports Keybard (.kbi), Vial (.vil), and QMK c2json formats.

    Use --verbosity to control output detail level:
        DEBUG: Detailed debug information
        INFO: Progress updates and summaries
        WARNING: Only warnings and errors (default)
        ERROR: Only errors
        CRITICAL: Only critical errors
        NONE: Silence all output
    """
    setup_logging(verbosity, quiet)


@main.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Configuration file path.",
)
@click.option(
    "--keymap",
    "-k",
    type=click.Path(exists=True, path_type=Path),
    help="Keymap file path (.vil, .kbi, .json).",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Output directory for generated images.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["svg", "png"]),
    default="svg",
    help="Output format.",
)
@click.option(
    "--layer",
    "-l",
    multiple=True,
    help="Layers to generate (all, all-layers, overview, N, N-M).",
)
@click.argument("stdin_marker", required=False, type=click.STRING)
def generate(
    config: Path | None,
    keymap: Path | None,
    output_dir: Path,
    format: str,
    layer: tuple,
    stdin_marker: str | None,
) -> None:
    """Generate keymap visualization images.

    Parses a keymap file and generates SVG or PNG images for each layer.
    Optionally generates an overview image showing all layers.

    STDIN_MARKER: Pass '-' to read keymap from stdin instead of file.

    Layer selection examples:
        -l overview       Generate only the overview image
        -l 1              Generate only layer 1
        -l 1-3            Generate layers 1, 2, and 3
        -l 1 -l 3 -l 5    Generate layers 1, 3, and 5
        -l all            Generate all individual layers
        (no -l)           Generate all layers plus overview
    """
    keymap_content = None
    if stdin_marker == "-":
        keymap = None
        keymap_content = sys.stdin.read()
    elif not keymap:
        if not sys.stdin.isatty():
            keymap_content = sys.stdin.read()

    if not keymap and not keymap_content:
        pass

    try:
        generator = ImageGenerator(config, output_dir, format)
        generator.generate(
            keymap_path=keymap,
            keymap_content=keymap_content,
            layers=list(layer) if layer else None,
        )
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--keybard-keymap",
    "-k",
    type=click.Path(exists=True, path_type=Path),
    help="Keybard keymap file path (.kbi).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output configuration file path.",
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing file.")
@click.option(
    "--qmk-color-header",
    "-C",
    type=click.Path(exists=True, path_type=Path),
    help="Path to QMK color.h file.",
)
@click.option(
    "--adjust-lightness",
    "-l",
    type=float,
    help="Adjust lightness (0.0-1.0).",
)
@click.option(
    "--adjust-saturation",
    "-s",
    type=float,
    help="Adjust saturation (0.0-1.0).",
)
def configure(
    keybard_keymap: Path | None,
    output: Path | None,
    force: bool,
    qmk_color_header: Path | None,
    adjust_lightness: float | None,
    adjust_saturation: float | None,
) -> None:
    """Generate or output configuration file.

    When -k is provided, extracts metadata (layer colors, names, custom
    keycodes) from the Keybard file to create a skim configuration.
    Optionally imports QMK named colors from a color.h file.

    Without -k, outputs the default configuration template.

    Color adjustments (--adjust-lightness, --adjust-saturation) are applied
    to all extracted colors to ensure readable contrast in generated images.
    """
    try:
        content = ""
        if keybard_keymap:
            raw_content = keybard_keymap.read_text()

            qmk_content = None
            if qmk_color_header:
                qmk_content = qmk_color_header.read_text()

            generator = ConfigGenerator()
            content = generator.generate(
                raw_content, qmk_content, adjust_lightness, adjust_saturation
            )
        else:
            asset_path = (
                Path(__file__).parent.parent / "assets" / "data" / "default-config.yaml"
            )
            content = asset_path.read_text()

        if output:
            if output.exists() and not force:
                click.echo(
                    f"Error: File {output} already exists. Use --force to overwrite.",
                    err=True,
                )
                sys.exit(1)
            output.write_text(content)
            click.echo(f"Configuration written to {output}")
        else:
            click.echo(content)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
