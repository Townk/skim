import asyncio
from pathlib import Path

import click
import drawsvg as draw
from drawsvg import Drawing

from skim.data.cli import OutputFiles

from .image_exporter import image_exporter


async def _save_keymap_images_async(
    drawings: dict[str, Drawing], output_dir: Path, output_format: str
):
    if output_format == "svg":
        for file, drawing in drawings.items():
            drawing.save_svg(output_dir / f"{file}.svg")
    else:
        async with image_exporter() as exporter:
            for file, drawing in drawings.items():
                await exporter.save(drawing, output_dir / f"{file}.{output_format}")


def _save_keymap_images(drawings: dict[str, Drawing], output_dir: Path, output_format: str):
    asyncio.run(_save_keymap_images_async(drawings, output_dir, output_format))


def save_drawings(outputs: OutputFiles, drawings: dict[str, draw.Drawing]):
    if not outputs.force_overwrite:
        existing_files: list[Path] = []
        for file in drawings:
            file_path = outputs.output_dir / f"{file}.{outputs.output_format}"
            if file_path.exists():
                existing_files.append(file_path)
        if existing_files:
            click.confirm(
                f"Files already exist: {', '.join(f.name for f in existing_files)}. Do you want to overwrite?",
                abort=True,
            )
    _save_keymap_images(drawings, outputs.output_dir, outputs.output_format)
