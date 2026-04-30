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
from typing import Any

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
            if (
                "System Font" in result.name
                or "Cairo" in result.name
                or "Playwright" in result.name
                or "Textual" in result.name
            ):
                status = click.style("WARN", fg="yellow", bold=True)

            click.echo(f"[{status}] {result.name}: {result.message}")
            if result.details:
                click.echo(f"       Details: {result.details}")

            # System fonts, optional render engines, and optional TUI dep don't fail the whole check
            if (
                "System Font" not in result.name
                and "Cairo" not in result.name
                and "Playwright" not in result.name
                and "Textual" not in result.name
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
    "-F",
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
@click.option(
    "-N",
    "--no-special-keys",
    "no_special_keys",
    is_flag=True,
    default=False,
    help="Omit the macro and tap-dance legend tables from the rendered SVGs.",
)
@click.option(
    "-Y",
    "--no-symbols",
    "no_symbols",
    is_flag=True,
    default=False,
    help="Omit the symbol legend from the rendered SVGs.",
)
@click.option(
    "--symbol-legend-flow",
    type=click.Choice(["row", "column"], case_sensitive=False),
    default=None,
    help=(
        "Flow direction for the symbol legend table. "
        "'row' fills rows first; 'column' fills columns first. "
        "Default: column."
    ),
)
@click.option(
    "--title",
    "-t",
    type=str,
    default=None,
    help="Override the overview keymap title (output.keymap_title).",
)
@click.option(
    "--adjust-lightness",
    "-L",
    type=float,
    default=None,
    help=(
        "Target lightness (0.0-1.0) applied to every layer base colour. "
        "Ignored when --config is provided."
    ),
)
@click.option(
    "--adjust-saturation",
    "-S",
    type=float,
    default=None,
    help=(
        "Cap saturation (0.0-1.0) on every layer base colour. Ignored when --config is provided."
    ),
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
    no_special_keys: bool,
    no_symbols: bool,
    symbol_legend_flow: str | None,
    title: str | None,
    adjust_lightness: float | None,
    adjust_saturation: float | None,
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
        if config is not None and (adjust_lightness is not None or adjust_saturation is not None):
            click.echo(
                "Note: --adjust-lightness/--adjust-saturation are ignored when --config is provided.",
                err=True,
            )
        generate_keymap(
            inputs,
            outputs,
            targets,
            show_special_keys_legend=not no_special_keys,
            show_symbol_legend=not no_symbols,
            symbol_legend_flow=symbol_legend_flow,
            title=title,
            adjust_lightness=adjust_lightness,
            adjust_saturation=adjust_saturation,
        )
    except click.Abort as e:
        click.echo(f"Aborted: {e}", err=True)
        sys.exit(1)
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Launch interactive configuration editor (TUI).",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Load an existing configuration file (interactive mode).",
)
@click.option(
    "--keymap",
    "-k",
    type=click.Path(exists=True, path_type=Path),
    help="Keymap file path (.kbi, .vil, .json).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output configuration file path.",
)
@click.option("--force", is_flag=True, help="Overwrite existing file.")
@click.option(
    "--qmk-color-header",
    "-C",
    type=click.Path(exists=True, path_type=Path),
    help="Path to QMK color.h file (non-interactive).",
)
@click.option(
    "--adjust-lightness",
    "-L",
    type=float,
    help="Adjust lightness (0.0-1.0) (non-interactive).",
)
@click.option(
    "--adjust-saturation",
    "-S",
    type=float,
    help="Adjust saturation (0.0-1.0) (non-interactive).",
)
@click.option("--title", "-t", type=str, help="Set the keymap title (output.keymap_title).")
@click.option("--copyright", "-r", type=str, help="Set the copyright notice (output.copyright).")
@click.option(
    "--layer-count",
    "-n",
    type=int,
    help="Number of layers to pre-create with defaults (interactive mode).",
)
@click.pass_context
def configure(
    ctx: click.Context,
    interactive: bool,
    config: Path | None,
    keymap: Path | None,
    output: Path | None,
    force: bool,
    qmk_color_header: Path | None,
    adjust_lightness: float | None,
    adjust_saturation: float | None,
    title: str | None,
    copyright: str | None,
    layer_count: int | None,
) -> None:
    """Generate or edit a configuration file.

    With no flags, shows this help message.

    Use -i/--interactive to launch the TUI configuration editor.
    Optionally pass -c/--config to load an existing config file into the editor.

    Use -k to extract metadata (layer colors, names, custom keycodes) from a
    Keybard file. Optionally imports QMK named colors from a color.h file.

    Color adjustments (--adjust-lightness, --adjust-saturation) are applied
    to all extracted colors to ensure readable contrast in generated images.
    """
    from skim.application.config_generator import ConfigGenerator

    # No flags at all: show help
    has_config_overrides = title is not None or copyright is not None
    if not interactive and not keymap and not has_config_overrides:
        click.echo(ctx.get_help())
        return

    try:
        config_data: dict[str, Any] = {}

        if has_config_overrides and not interactive:
            import yaml

            config_data = _load_initial_config(config)
            if title is not None:
                config_data["output"]["keymap_title"] = title
            if copyright is not None:
                config_data["output"]["copyright"] = copyright
            if layer_count is not None:
                _apply_layer_count(config_data, layer_count)
            content = yaml.dump(config_data, sort_keys=False, default_flow_style=False)
            if output:
                _write_config(output, content, force)
            else:
                click.echo(content)
            return

        generator = ConfigGenerator()

        # Generate config data from keymap if provided
        if keymap:
            import yaml as _yaml

            raw_content = keymap.read_text()

            from skim.application.loaders.keymap_loader import (
                _detect_format_from_path,
            )
            from skim.domain import KeymapType

            detected = _detect_format_from_path(keymap)

            if detected == KeymapType.KEYBARD:
                qmk_content = qmk_color_header.read_text() if qmk_color_header else None
                content = generator.generate_from_keybard(
                    raw_content, qmk_content, adjust_lightness, adjust_saturation
                )
            else:
                content = generator.generate_from_keymap(raw_content)

            config_data = _yaml.safe_load(content)

            # If -c is also provided, treat the keymap-derived config as a
            # scaffold and override it with the user's saved config so reloads
            # keep their edits (colors, titles, etc.).
            if config and config.is_file():
                loaded = _yaml.safe_load(config.read_text())
                if loaded:
                    config_data = _deep_merge(config_data, loaded)

            if not interactive:
                merged = _yaml.dump(config_data, sort_keys=False, default_flow_style=False)
                if output:
                    _write_config(output, merged, force)
                else:
                    click.echo(merged)
                return

        # Interactive mode
        if interactive:
            try:
                from skim.tui import launch_tui

                if not keymap:
                    config_data = _load_initial_config(config)
                if title is not None:
                    config_data["output"]["keymap_title"] = title
                if copyright is not None:
                    config_data["output"]["copyright"] = copyright
                if layer_count is not None:
                    _apply_layer_count(config_data, layer_count)
                launch_tui(
                    config_data=config_data,
                    output_path=output,
                    config_path=config,
                    force=force,
                )
                return
            except ImportError:
                click.echo(
                    "Error: The TUI requires the 'textual' package. Install it with:\n"
                    "    pip install qmk-skim[tui]",
                    err=True,
                )
                sys.exit(1)

    except (ValueError, OSError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge ``override`` onto ``base``; ``override`` wins on conflicts.

    Nested dicts merge recursively. Lists and scalars from ``override``
    replace the corresponding value in ``base`` wholesale — list elements
    are not merged, since lists like ``keyboard.layers`` and
    ``palette.layers`` are positionally coupled and partial merges would
    corrupt them.
    """
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _load_initial_config(config_path: Path | None) -> dict:
    """Load config from file if provided, otherwise return defaults."""
    import yaml

    from skim.data.config import SkimConfig

    if config_path and config_path.is_file():
        data = yaml.safe_load(config_path.read_text())
        if data:
            config = SkimConfig.model_validate(data)
            return config.model_dump(mode="json")

    return SkimConfig().model_dump(mode="json")


def _apply_layer_count(config_data: dict, layer_count: int) -> None:
    """Fill config_data with default layers up to layer_count.

    For indices 0 to layer_count-1, any index not already present in
    keyboard.layers gets a default layer entry and a default palette
    color. Existing layers are preserved. The resulting layers list is
    sorted by index.
    """
    from skim.application.render.styling import default_layer_color

    keyboard_layers = config_data.get("keyboard", {}).get("layers", [])
    palette_layers = (
        config_data.get("output", {}).get("style", {}).get("palette", {}).get("layers", [])
    )

    existing_indices = {layer["index"] for layer in keyboard_layers}

    if len(existing_indices) >= layer_count:
        return

    # Build index-to-position map for existing layers
    index_to_kb = {layer["index"]: layer for layer in keyboard_layers}
    index_to_palette = {}
    for pos, layer in enumerate(keyboard_layers):
        if pos < len(palette_layers):
            index_to_palette[layer["index"]] = palette_layers[pos]

    # Fill missing indices
    for idx in range(layer_count):
        if idx not in existing_indices:
            index_to_kb[idx] = {
                "index": idx,
                "name": f"Layer {idx}",
                "id": None,
                "variant": None,
            }
            index_to_palette[idx] = {
                "base_color": default_layer_color(idx),
                "color_index": 2,
                "gradient": None,
            }

    # Rebuild sorted by index
    sorted_indices = sorted(index_to_kb.keys())
    config_data["keyboard"]["layers"] = [index_to_kb[i] for i in sorted_indices]
    config_data["output"]["style"]["palette"]["layers"] = [
        index_to_palette.get(
            i, {"base_color": default_layer_color(i), "color_index": 2, "gradient": None}
        )
        for i in sorted_indices
    ]


def _confirm_via_tty(prompt: str) -> None:
    """Prompt for confirmation reading from /dev/tty instead of stdin.

    When stdin is a pipe, click.confirm cannot read user input because
    stdin is consumed by the piped data. Opening /dev/tty directly
    bypasses the redirected stdin and reads from the real terminal.
    """
    try:
        with open("/dev/tty") as tty:
            saved_stdin = sys.stdin
            sys.stdin = tty
            try:
                click.confirm(prompt, abort=True)
            finally:
                sys.stdin = saved_stdin
    except OSError as err:
        raise click.Abort("Cannot prompt for confirmation without a terminal.") from err


def _write_config(output: Path, content: str, force: bool) -> None:
    """Write config content to file with overwrite protection."""
    if output.is_dir():
        output = output / "skim-config.yaml"

    if output.exists() and not force:
        prompt = f"File {output} already exists. Do you want to overwrite?"
        try:
            if not sys.stdin.isatty():
                _confirm_via_tty(prompt)
            else:
                click.confirm(prompt, abort=True)
        except click.Abort:
            click.echo("Aborted.", err=True)
            sys.exit(1)

    output.write_text(content)
    click.echo(f"Configuration written to {output}")
