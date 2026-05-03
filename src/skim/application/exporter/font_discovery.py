# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""System-font discovery utilities for the Cairo bitmap exporter.

Cairo can't read the embedded ``@font-face`` data the SVG renderer
emits — when it rasterises an SVG to PNG / PDF it needs an
on-filesystem font file. These helpers locate platform-appropriate
candidates (Apple Symbols / Helvetica on macOS, DejaVu / Liberation
on Linux, Segoe UI / Arial on Windows) and fall back to one of the
bundled fonts (:attr:`Font.FINGER_KEY.path`) when no system font
matches.

Render-side code uses :class:`Font` directly with the bundled font
files; this module is exporter-only.
"""

import os
import sys
from pathlib import Path

from skim.application.render.font import Font


def find_system_fonts() -> list[Path]:
    """Find available system fonts."""
    system_fonts = []
    font_candidates: list[Path] = []

    if sys.platform == "darwin":
        font_candidates = [
            Path("/System/Library/Fonts/Apple Symbols.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Black.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
        ]
    elif sys.platform == "linux" or sys.platform == "linux2":
        font_candidates = [
            Path("/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansSymbols-Regular.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/misc/unifont.pcf.gz"),
        ]
    elif sys.platform == "win32":
        windows_fonts = os.environ.get("WINDIR", "C:\\Windows")
        fonts_dir = Path(windows_fonts) / "Fonts"
        font_candidates = [
            fonts_dir / "seguisym.ttf",
            fonts_dir / "seguisb.ttf",
            fonts_dir / "segoeui.ttf",
            fonts_dir / "arialbd.ttf",
            fonts_dir / "arial.ttf",
            fonts_dir / "arialuni.ttf",
        ]

    for font_path in font_candidates:
        if font_path.exists() and font_path.is_file():
            system_fonts.append(font_path)

    return system_fonts


def get_system_font_path(font_family: str | None) -> Path:
    """Get the path to a system font based on family name."""
    if not font_family:
        font_family = "sans-serif"

    font_family_lower = font_family.lower()

    if sys.platform == "darwin":
        if "black" in font_family_lower:
            candidates = [
                Path("/System/Library/Fonts/Supplemental/Arial Black.ttf"),
                Path("/Library/Fonts/Arial Black.ttf"),
            ]
        elif "bold" in font_family_lower:
            candidates = [
                Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                Path("/Library/Fonts/Arial Bold.ttf"),
            ]
        elif "thin" in font_family_lower or "light" in font_family_lower:
            candidates = [
                Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            ]
        elif "symbol" in font_family_lower or "nerd" in font_family_lower:
            candidates = [
                Path("/System/Library/Fonts/Apple Symbols.ttf"),
            ]
        else:
            candidates = [
                Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
                Path("/System/Library/Fonts/Helvetica.ttc"),
            ]
    else:
        return Font.FINGER_KEY.path

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return Font.FINGER_KEY.path
