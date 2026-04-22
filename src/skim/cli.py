# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Command-line interface for the Svalboard Keymap Image Maker tool.

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

        $ qmk c2json -kb svalboard/trackball/pmw3389/right -km vial --no-cpp $QMK_ROOT/keyboards/svalboard/keymaps/vial/keymap.c | skim generate - -o ./out
"""

import json
import sys
from functools import partial
from pathlib import Path

import click

from skim import __prog_name__, __version__

from skim.application import generate_keymap, setup_logging
from skim.application.doctor import run_doctor_checks
from skim.application.exporter import get_available_export_formats
from skim.data import InputFiles, KeymapGeneratorTargets, OutputFiles, RenderEngine


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
@click.option("--quiet", "-q", is_flag=True, help="Silence all output (overrides --verbosity).")
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
def doctor() -> None:
    """Check system environment and dependencies."""
    click.echo(f"Running doctor checks for {__prog_name__} v{__version__}...\n")

    all_passed = True
    for result in run_doctor_checks():
        if result.passed:
            status = click.style("PASS", fg="green", bold=True)
            click.echo(f"[{status}] {result.name}: {result.message}")
        else:
            status = click.style("FAIL", fg="red", bold=True)
            # Some failures might be warnings (like system fonts which are optional)
            if "System Font" in result.name:
                status = click.style("WARN", fg="yellow", bold=True)

            click.echo(f"[{status}] {result.name}: {result.message}")
            if result.details:
                click.echo(f"       Details: {result.details}")

            # System fonts are optional, so they don't fail the whole check
            if (
                "System Font" not in result.name
                and "Cairo" not in result.name
                and "Playwright" not in result.name
            ):
                all_passed = False

    click.echo("")
    if all_passed:
        click.secho("Everything looks good!", fg="green")
    else:
        click.secho("Some checks failed or warned. See details above.", fg="yellow")


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
    "output_format",
    type=click.Choice(get_available_export_formats()),
    default="svg",
    help="Output format. Raster formats (png, jpeg, webp, avif) require a render engine.",
)
@click.option(
    "--layer",
    "-l",
    multiple=True,
    help="Layers to generate (all, all-layers, overview, N, N-M).",
)
@click.option(
    "--use-system-fonts",
    "-S",
    is_flag=True,
    help="Use system fonts instead of embedding fonts in SVG.",
)
@click.option(
    "--render-engine",
    "-e",
    type=click.Choice(["chromium", "cairo"]),
    default=None,
    help="Render engine for non-vector formats. 'chromium' uses Playwright, 'cairo' uses Cairo library. Only shown when both are available.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing files without confirmation.",
)
@click.argument("stdin_marker", required=False, type=click.STRING)
def generate(
    config: Path | None,
    keymap: Path | None,
    output_dir: Path,
    output_format: str,
    layer: tuple,
    force: bool,
    use_system_fonts: bool,
    render_engine: str | None,
    stdin_marker: str | None,
) -> None:
    """Generate keymap visualization images.

    Parses a keymap file and generates a keymap image for each layer.
    Optionally generates an overview image showing all layers.

    The supported output formats depend on the dependencies installed. For
    non-vector images (PNG, JPEG, WEBP, and AVIF), the Playwright Chromium
    Browser, or the Cairo library must be installed in the system.

    STDIN_MARKER: Pass '-' to read keymap from stdin instead of file.

    \b
    Layer selection examples:
        -l overview       Generate only the overview image
        -l 1              Generate only layer 1
        -l 1-3            Generate layers 1, 2, and 3
        -l 1 -l 3 -l 5    Generate layers 1, 3, and 5
        -l all            Generate all individual layers
        (no -l)           Generate all layers plus overview
    """

    try:
        inputs = InputFiles(config, keymap, stdin_marker == "-")
        engine = RenderEngine(render_engine) if render_engine else None
        outputs = OutputFiles(output_dir, output_format, force, use_system_fonts, engine)
        targets = KeymapGeneratorTargets.from_args(layer, partial(click.echo, err=True))
        generate_keymap(inputs, outputs, targets)
    except click.Abort as e:
        click.echo(f"Aborted: {e}", err=True)
        sys.exit(1)
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as e:
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
    from skim.application.config_generator import ConfigGenerator

    try:
        generator = ConfigGenerator()

        if keybard_keymap:
            raw_content = keybard_keymap.read_text()
            qmk_content = qmk_color_header.read_text() if qmk_color_header else None
            content = generator.generate_from_keybard(
                raw_content, qmk_content, adjust_lightness, adjust_saturation
            )
        else:
            content = generator.generate_default()

        if output:
            if output.is_dir():
                output = output / "skim-config.yaml"

            if output.exists() and not force:
                try:
                    click.confirm(
                        f"File {output} already exists. Do you want to overwrite?",
                        abort=True,
                    )
                except click.Abort:
                    click.echo("Aborted.", err=True)
                    sys.exit(1)

            output.write_text(content)
            click.echo(f"Configuration written to {output}")
        else:
            click.echo(content)

    except (ValueError, OSError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
