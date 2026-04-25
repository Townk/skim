# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Image exporter with support for Playwright and Cairo backends."""

import asyncio
import sys
from pathlib import Path

import click
import drawsvg as draw
from drawsvg import Drawing

from skim.data import OutputFiles, RenderEngine

from .availability import check_cairo_available, check_playwright_available

# Check availability
_PLAYWRIGHT_AVAILABLE = False
_CAIRO_AVAILABLE = False
_chromium_exporter = None
_cairo_exporter = None

try:
    if check_playwright_available():
        from .chromium_exporter import chromium_exporter

        _chromium_exporter = chromium_exporter
        _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

if check_cairo_available():
    try:
        from .cairo_exporter import CairoImageExporter

        _cairo_exporter = CairoImageExporter
        _CAIRO_AVAILABLE = True
    except ImportError:
        pass


def is_playwright_available() -> bool:
    return _PLAYWRIGHT_AVAILABLE


def is_cairo_available() -> bool:
    return _CAIRO_AVAILABLE


def get_available_export_formats() -> list[str]:
    formats = ["svg"]
    if _PLAYWRIGHT_AVAILABLE or _CAIRO_AVAILABLE:
        formats.extend(["png", "jpeg", "webp", "avif"])
    return formats


def get_available_render_engines() -> list[RenderEngine]:
    engines = []
    if _PLAYWRIGHT_AVAILABLE:
        engines.append(RenderEngine.CHROMIUM)
    if _CAIRO_AVAILABLE:
        engines.append(RenderEngine.CAIRO)
    return engines


def _get_render_engine(requested: RenderEngine | None) -> RenderEngine:
    available = get_available_render_engines()
    if not available:
        raise RuntimeError("No render engines available")

    if requested is None:
        return available[0]

    if requested not in available:
        available_names = [e.value for e in available]
        raise RuntimeError(
            f"Render engine {requested.value} is not available. Available: {', '.join(available_names)}"
        )

    return requested


async def _save_with_playwright(
    drawings: dict[str, Drawing], output_dir: Path, output_format: str
) -> None:
    if _chromium_exporter is None:
        raise RuntimeError("Playwright not available")
    async with _chromium_exporter() as exporter:
        for file, drawing in drawings.items():
            await exporter.save(drawing, output_dir / f"{file}.{output_format}")


def _save_with_cairo(
    drawings: dict[str, Drawing],
    output_dir: Path,
    output_format: str,
    convert_text_to_paths: bool,
    use_system_fonts: bool = False,
) -> None:
    if _cairo_exporter is None:
        raise RuntimeError("Cairo not available")
    exporter = _cairo_exporter()
    try:
        for file, drawing in drawings.items():
            exporter.save(
                drawing,
                output_dir / f"{file}.{output_format}",
                convert_text_to_paths=convert_text_to_paths,
                use_system_fonts=use_system_fonts,
            )
    finally:
        exporter.close()


async def _save_keymap_images_async(
    drawings: dict[str, Drawing],
    output_dir: Path,
    output_format: str,
    render_engine: RenderEngine | None,
    convert_text_to_paths: bool,
    use_system_fonts: bool = False,
):
    if output_format == "svg":
        for file, drawing in drawings.items():
            drawing.save_svg(output_dir / f"{file}.svg")
        return

    engine = _get_render_engine(render_engine)

    if engine == RenderEngine.CHROMIUM:
        await _save_with_playwright(drawings, output_dir, output_format)
    elif engine == RenderEngine.CAIRO:
        _save_with_cairo(
            drawings, output_dir, output_format, convert_text_to_paths, use_system_fonts
        )
    else:
        raise RuntimeError(f"Unknown render engine: {engine}")


def _save_keymap_images(
    drawings: dict[str, Drawing],
    output_dir: Path,
    output_format: str,
    render_engine: RenderEngine | None = None,
    convert_text_to_paths: bool = False,
    use_system_fonts: bool = False,
):
    asyncio.run(
        _save_keymap_images_async(
            drawings,
            output_dir,
            output_format,
            render_engine,
            convert_text_to_paths,
            use_system_fonts,
        )
    )


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


def save_drawings(
    outputs: OutputFiles,
    drawings: dict[str, draw.Drawing],
    render_engine: RenderEngine | None = None,
):
    if not outputs.force_overwrite:
        existing_files = []
        for file in drawings:
            file_path = outputs.output_dir / f"{file}.{outputs.output_format}"
            if file_path.exists():
                existing_files.append(file_path)
        if existing_files:
            file_names = ", ".join(f.name for f in existing_files)
            prompt = f"Files already exist: {file_names}. Do you want to overwrite?"
            if not sys.stdin.isatty():
                _confirm_via_tty(prompt)
            else:
                click.confirm(prompt, abort=True)

    # Determine if we need to convert text to paths
    # Cairo always needs text-to_paths because CairoSVG has poor font fallback and baseline support
    convert_text_to_paths = render_engine == RenderEngine.CAIRO or (
        render_engine is None and _CAIRO_AVAILABLE and not _PLAYWRIGHT_AVAILABLE
    )

    _save_keymap_images(
        drawings,
        outputs.output_dir,
        outputs.output_format,
        render_engine,
        convert_text_to_paths,
        outputs.use_system_fonts,
    )
