# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Text to SVG path conversion using fontTools.

This module provides functionality to convert text to SVG path elements,
eliminating font rendering dependencies. Uses fontTools (pure Python) to
extract glyph outlines from TTF fonts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import drawsvg as draw
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont


class GlyphNotFoundError(Exception):
    """Raised when a glyph cannot be found for a character."""


@dataclass
class GlyphMetrics:
    """Metrics for a glyph."""

    advance_width: float
    left_side_bearing: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float


class FontReader:
    """Reads TTF fonts and extracts glyph paths."""

    def __init__(self, font_path: Path) -> None:
        self.font_path = font_path
        self._font = TTFont(str(font_path))
        self._glyph_set = self._font.getGlyphSet()
        self.units_per_em = cast(Any, self._font["head"]).unitsPerEm
        self.ascent = self._font["hhea"].ascender
        self.descent = self._font["hhea"].descender

    def get_glyph_path(self, char: str) -> str:
        if len(char) != 1:
            raise ValueError(f"Expected single character, got: {char!r}")

        cmap = self._font.getBestCmap()
        if not cmap:
            raise GlyphNotFoundError("No cmap found")

        code_point = ord(char)
        glyph_name = cmap.get(code_point)

        if glyph_name is None:
            raise GlyphNotFoundError(f"No glyph for: {char!r} (U+{code_point:04X})")

        if glyph_name not in self._glyph_set:
            raise GlyphNotFoundError(f"Glyph {glyph_name!r} not found")

        glyph = self._glyph_set[glyph_name]
        pen = SVGPathPen(self._glyph_set)
        glyph.draw(pen)
        return pen.getCommands()

    def get_glyph_metrics(self, char: str) -> GlyphMetrics:
        if len(char) != 1:
            raise ValueError(f"Expected single character, got: {char!r}")

        cmap = self._font.getBestCmap()
        code_point = ord(char)
        glyph_name = cmap.get(code_point) if cmap else None

        if glyph_name is None or glyph_name not in self._glyph_set:
            return GlyphMetrics(0, 0, 0, 0, 0, 0)

        glyph = self._glyph_set[glyph_name]
        hmtx = self._font["hmtx"]
        advance_width, left_side_bearing = hmtx[glyph_name]
        x_min, y_min, x_max, y_max = glyph.bounds if hasattr(glyph, "bounds") else (0, 0, 0, 0)

        return GlyphMetrics(
            advance_width=advance_width,
            left_side_bearing=left_side_bearing,
            x_min=x_min or 0,
            y_min=y_min or 0,
            x_max=x_max or 0,
            y_max=y_max or 0,
        )

    def get_text_width(self, text: str) -> float:
        return sum(self.get_glyph_metrics(char).advance_width for char in text)

    def close(self) -> None:
        self._font.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class TextToPathConverter:
    """Converts text to SVG paths."""

    def __init__(self, font_path: Path) -> None:
        self._font_reader = FontReader(font_path)

    def convert_text(
        self,
        text: str,
        x: float,
        y: float,
        font_size: float,
        fill: str = "#000",
        dominant_baseline: str = "alphabetic",
        fallback_readers: list[FontReader] | None = None,
    ) -> tuple[list[dict], float]:
        paths = []
        current_x = x
        scale = font_size / self._font_reader.units_per_em

        y_offset = self._get_baseline_offset(dominant_baseline, font_size)

        for char in text:
            font_reader = self._font_reader
            char_scale = scale
            char_y_offset = y_offset
            path_data = None
            metrics = None

            try:
                path_data = font_reader.get_glyph_path(char)
                metrics = font_reader.get_glyph_metrics(char)
            except GlyphNotFoundError:
                found = False
                fallback_font_reader = None
                if fallback_readers:
                    for fallback in fallback_readers:
                        try:
                            path_data = fallback.get_glyph_path(char)
                            metrics = fallback.get_glyph_metrics(char)
                            fallback_font_reader = fallback
                            char_scale = font_size / fallback.units_per_em
                            found = True
                            break
                        except GlyphNotFoundError:
                            continue

                if found and fallback_font_reader:
                    ascent_ratio = (
                        self._font_reader.ascent / fallback_font_reader.ascent
                        if fallback_font_reader.ascent != 0
                        else 1.0
                    )
                    char_scale = (font_size / fallback_font_reader.units_per_em) * ascent_ratio
                    font_reader = fallback_font_reader

                if not found:
                    synthetic = self._create_synthetic_glyph(char, font_size)
                    if synthetic:
                        synth_path = str(synthetic["d"])
                        synth_width = float(synthetic["width"])
                        transform = f"translate({current_x}, {y + y_offset}) scale({char_scale}, {-char_scale}) translate(0, {-self._font_reader.ascent})"
                        paths.append(
                            {
                                "d": synth_path,
                                "transform": transform,
                                "fill": fill,
                                "_char": char,
                            }
                        )
                        current_x += synth_width
                    continue

            if path_data is not None and metrics is not None:
                transform = f"translate({current_x}, {y + char_y_offset}) scale({char_scale}, {-char_scale}) translate(0, {-font_reader.ascent})"

                paths.append(
                    {
                        "d": path_data,
                        "transform": transform,
                        "fill": fill,
                        "_char": char,
                    }
                )

                current_x += metrics.advance_width * char_scale

        return paths, current_x

    def _get_baseline_offset_for_reader(
        self, dominant_baseline: str, font_size: float, reader: FontReader
    ) -> float:
        scale = font_size / reader.units_per_em
        ascent = reader.ascent
        descent = reader.descent

        if dominant_baseline == "central" or dominant_baseline == "middle":
            center = (ascent + descent) / 2
            return scale * (center - ascent)
        elif (
            dominant_baseline == "bottom"
            or dominant_baseline == "text-bottom"
            or dominant_baseline == "text-after-edge"
        ):
            return scale * (descent - ascent)
        elif (
            dominant_baseline == "top"
            or dominant_baseline == "text-top"
            or dominant_baseline == "text-before-edge"
        ):
            return 0
        elif dominant_baseline == "hanging":
            return scale * (ascent * 0.8 - ascent)
        else:
            return 0

    def _create_synthetic_glyph(self, char: str, font_size: float) -> dict | None:
        units_per_em = self._font_reader.units_per_em
        scale_factor = font_size / units_per_em

        if char == "│":
            advance_width = units_per_em * 0.8
            line_width = units_per_em * 0.08
            x_center = advance_width / 2
            y_bottom = self._font_reader.descent
            y_top = self._font_reader.ascent

            path = f"M {x_center - line_width / 2} {y_bottom} L {x_center + line_width / 2} {y_bottom} L {x_center + line_width / 2} {y_top} L {x_center - line_width / 2} {y_top} Z"
            return {"d": path, "width": advance_width * scale_factor}
        elif char == "⎋":
            advance_width = units_per_em * 0.9
            radius = units_per_em * 0.38
            stroke_width = units_per_em * 0.1
            x_center = advance_width / 2
            y_center = (self._font_reader.ascent + self._font_reader.descent) / 2

            arrow_length = radius * 0.5
            arrow_head = radius * 0.25
            arrow_start_x = x_center
            arrow_start_y = y_center
            arrow_end_x = x_center - arrow_length * 0.707
            arrow_end_y = y_center - arrow_length * 0.707

            inner_radius = radius - stroke_width
            outer_radius = radius

            path = (
                f"M {x_center - outer_radius} {y_center} "
                f"A {outer_radius} {outer_radius} 0 1 1 {x_center + outer_radius} {y_center} "
                f"A {outer_radius} {outer_radius} 0 1 1 {x_center - outer_radius} {y_center} "
                f"M {x_center - inner_radius} {y_center} "
                f"A {inner_radius} {inner_radius} 0 1 0 {x_center + inner_radius} {y_center} "
                f"A {inner_radius} {inner_radius} 0 1 0 {x_center - inner_radius} {y_center} "
                f"M {arrow_start_x} {arrow_start_y} "
                f"L {arrow_end_x} {arrow_end_y} "
                f"M {arrow_end_x} {arrow_end_y} "
                f"L {arrow_end_x + arrow_head} {arrow_end_y} "
                f"M {arrow_end_x} {arrow_end_y} "
                f"L {arrow_end_x} {arrow_end_y + arrow_head}"
            )
            return {"d": path, "width": advance_width * scale_factor}
        return None

    def _get_baseline_offset(self, dominant_baseline: str, font_size: float) -> float:
        scale = font_size / self._font_reader.units_per_em
        ascent = self._font_reader.ascent
        descent = self._font_reader.descent

        if dominant_baseline == "central" or dominant_baseline == "middle":
            center = (ascent + descent) / 2
            return scale * (center - ascent)
        elif (
            dominant_baseline == "bottom"
            or dominant_baseline == "text-bottom"
            or dominant_baseline == "text-after-edge"
        ):
            return scale * (descent - ascent)
        elif (
            dominant_baseline == "top"
            or dominant_baseline == "text-top"
            or dominant_baseline == "text-before-edge"
        ):
            return 0
        elif dominant_baseline == "hanging":
            return scale * (ascent * 0.8 - ascent)
        else:
            return 0

    def convert_text_to_group(
        self, text: str, x: float, y: float, font_size: float, fill: str = "#000"
    ) -> draw.Group:
        group = draw.Group()
        paths_data, _ = self.convert_text(text, x, y, font_size, fill)

        for path_data in paths_data:
            path = draw.Path(
                d=path_data["d"],
                transform=path_data["transform"],
                fill=path_data["fill"],
            )
            group.append(path)

        return group

    def get_text_width(self, text: str, font_size: float) -> float:
        font_units_width = self._font_reader.get_text_width(text)
        scale = font_size / self._font_reader.units_per_em
        return font_units_width * scale

    def close(self) -> None:
        self._font_reader.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
