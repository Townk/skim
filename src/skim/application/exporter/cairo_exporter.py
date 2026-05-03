# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Image exporter using Cairo for SVG-to-image conversion."""

import contextlib
from pathlib import Path

import drawsvg as draw
from PIL import Image

from skim.application.exporter.font_discovery import find_system_fonts, get_system_font_path
from skim.application.render.text import Font
from skim.application.render.text_to_paths import FontReader, TextToPathConverter


class CairoImageExporter:
    """Exports SVG drawings to raster image formats using Cairo."""

    def __init__(self) -> None:
        self._font_converters = {}
        self._fallback_readers = []

        # Initialize fallbacks
        bundled_fonts = [Font.FINGER_KEY, Font.THUMB_KEY, Font.SYMBOLS]
        for font in bundled_fonts:
            with contextlib.suppress(Exception):
                self._fallback_readers.append(FontReader(font.path))

        for font_path in find_system_fonts():
            with contextlib.suppress(Exception):
                self._fallback_readers.append(FontReader(font_path))

    def _get_converter(self, font_path: Path) -> TextToPathConverter:
        if font_path not in self._font_converters:
            self._font_converters[font_path] = TextToPathConverter(font_path)
        return self._font_converters[font_path]

    def save(
        self,
        drawing: draw.Drawing,
        output_path: Path,
        convert_text_to_paths: bool = False,
        use_system_fonts: bool = False,
    ) -> None:
        if convert_text_to_paths:
            drawing = self._convert_drawing_text_to_paths(drawing, use_system_fonts)

        png_path = output_path.with_suffix(".png")
        try:
            drawing.save_png(str(png_path))
        except Exception as e:
            raise RuntimeError(f"Failed to rasterize with Cairo: {e}") from e

        if output_path.suffix.lower() != ".png":
            with Image.open(png_path) as img:
                img.save(output_path)
            png_path.unlink()

    def _convert_drawing_text_to_paths(
        self, drawing: draw.Drawing, use_system_fonts: bool = False
    ) -> draw.Drawing:
        # Preserve any svg_args set on the source drawing (notably ``viewBox``,
        # which the renderer uses to keep the natural coordinate system while
        # presenting the SVG at the user-requested width/height).
        svg_args = dict(getattr(drawing, "svg_args", {}) or {})
        new_drawing = draw.Drawing(drawing.width, drawing.height, **svg_args)

        for element in drawing.elements:
            converted = self._convert_element(element, use_system_fonts)
            if isinstance(converted, list):
                for elem in converted:
                    new_drawing.append(elem)
            else:
                new_drawing.append(converted)

        return new_drawing

    def _convert_element(self, element, use_system_fonts: bool = False):
        if isinstance(element, draw.Text):
            return self._convert_text_element(element, use_system_fonts)

        if isinstance(element, draw.Group):
            transform = element.args.get("transform") if hasattr(element, "args") else None
            new_group = draw.Group(transform=transform) if transform else draw.Group()
            for child in element.children if hasattr(element, "children") else []:
                converted = self._convert_element(child, use_system_fonts)
                if isinstance(converted, list):
                    for elem in converted:
                        new_group.append(elem)
                else:
                    new_group.append(converted)
            return new_group

        return element

    def _convert_text_element(
        self, text_element: draw.Text, use_system_fonts: bool = False
    ) -> draw.Group:
        text = getattr(text_element, "escaped_text", "")
        args = text_element.args if hasattr(text_element, "args") else {}

        font_size = args.get("font-size", 12)
        x = args.get("x", 0)
        y = args.get("y", 0)
        fill = args.get("fill", "#000")
        font_family = args.get("font-family", None)
        text_anchor = args.get("text-anchor", "start")
        dominant_baseline = args.get("dominant-baseline", "alphabetic")

        if use_system_fonts:
            font_path = get_system_font_path(font_family)
        else:
            font = self._get_font_from_family(font_family)
            font_path = font.path
        converter = self._get_converter(font_path)

        all_paths = []
        current_x = 0

        if text:
            paths_data, end_x = converter.convert_text(
                text, current_x, y, font_size, fill, dominant_baseline, self._fallback_readers
            )
            all_paths.extend(paths_data)
            current_x = end_x

        for tspan in text_element.children if hasattr(text_element, "children") else []:
            if isinstance(tspan, draw.TSpan):
                tspan_args = tspan.args if hasattr(tspan, "args") else {}
                tspan_text = getattr(tspan, "escaped_text", "")
                tspan_fill = tspan_args.get("fill", fill)
                tspan_family = tspan_args.get("font-family", font_family)
                tspan_baseline = tspan_args.get("dominant-baseline", dominant_baseline)

                if tspan_text:
                    if use_system_fonts:
                        tspan_font_path = get_system_font_path(tspan_family)
                    else:
                        tspan_font = self._get_font_from_family(tspan_family)
                        tspan_font_path = tspan_font.path
                    tspan_converter = self._get_converter(tspan_font_path)
                    tspan_paths, end_x = tspan_converter.convert_text(
                        tspan_text,
                        current_x,
                        y,
                        font_size,
                        tspan_fill,
                        tspan_baseline,
                        self._fallback_readers,
                    )
                    all_paths.extend(tspan_paths)
                    current_x = end_x

        total_width = current_x
        x_offset = 0

        if text_anchor == "middle":
            x_offset = x - total_width / 2
        elif text_anchor == "end":
            x_offset = x - total_width
        else:
            x_offset = x

        group = draw.Group(transform=f"translate({x_offset}, 0)") if x_offset != 0 else draw.Group()

        for path_data in all_paths:
            path = draw.Path(
                d=path_data["d"], transform=path_data["transform"], fill=path_data["fill"]
            )
            group.append(path)

        return group

    def _get_font_from_family(self, font_family: str | None) -> Font:
        if not font_family:
            return Font.FINGER_KEY
        font_family_lower = font_family.lower()
        if "thumb" in font_family_lower or "black" in font_family_lower:
            return Font.THUMB_KEY
        elif "title" in font_family_lower or "thin" in font_family_lower:
            return Font.TITLE
        elif "symbol" in font_family_lower or "nerd" in font_family_lower:
            return Font.SYMBOLS
        return Font.FINGER_KEY

    def close(self) -> None:
        for converter in self._font_converters.values():
            converter.close()
        self._font_converters.clear()

        for reader in self._fallback_readers:
            reader.close()
        self._fallback_readers.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
