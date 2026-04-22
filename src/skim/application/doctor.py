# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Doctor command logic to verify system environment and installation integrity."""

import sys
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

from skim.application.exporter.availability import (
    check_cairo_available,
    check_playwright_available,
)
from skim.assets import ASSETS


@dataclass
class CheckResult:
    """Result of a doctor check."""

    name: str
    passed: bool
    message: str
    details: str | None = None


def check_installation_integrity() -> CheckResult:
    """Verify that all bundled assets are present."""
    missing = []
    assets_to_check = [
        ("Keycode Mappings", "keycode_mappings"),
        ("Nerd Font Glyphs", "nerd_font_glyphs"),
        ("Roboto Regular", "font_roboto_regular"),
        ("Roboto Black", "font_roboto_black"),
        ("Roboto Thin", "font_roboto_thin"),
        ("Symbols Nerd Font", "font_symbols_nerd"),
        ("Svalboard Logo", "logo_svalboard"),
    ]

    for name, attr in assets_to_check:
        try:
            # Accessing the property triggers the check in BundleAssets
            getattr(ASSETS, attr)
        except FileNotFoundError:
            missing.append(name)
        except Exception as e:
            missing.append(f"{name} (Error: {e})")

    if missing:
        return CheckResult(
            name="Installation Integrity",
            passed=False,
            message="Missing bundled assets.",
            details=f"Missing: {', '.join(missing)}",
        )

    return CheckResult(
        name="Installation Integrity",
        passed=True,
        message="All bundled assets are present.",
    )


def check_render_engines() -> Generator[CheckResult, None, None]:
    """Check availability of render engines."""
    # Playwright
    pw_available = check_playwright_available()
    yield CheckResult(
        name="Playwright (Chromium)",
        passed=pw_available,
        message="Available" if pw_available else "Not available",
        details="Required for PNG/JPEG/WEBP export using Chromium." if not pw_available else None,
    )

    # Cairo
    cairo_available = check_cairo_available()
    yield CheckResult(
        name="Cairo Graphics",
        passed=cairo_available,
        message="Available" if cairo_available else "Not available",
        details="Required for PNG/JPEG/WEBP export using Cairo (faster than Chromium)."
        if not cairo_available
        else None,
    )


def check_system_fonts() -> Generator[CheckResult, None, None]:
    """Check for presence of specific system fonts."""
    fonts_to_check = [
        "Roboto-Regular.ttf",
        "Roboto-Black.ttf",
        "Roboto-Thin.ttf",
        "SymbolsNerdFont-Regular.ttf",
    ]

    # Common font directories based on OS
    font_dirs = []
    if sys.platform == "darwin":
        font_dirs = [
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path.home() / "Library/Fonts",
        ]
    elif sys.platform == "linux":
        font_dirs = [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".local/share/fonts",
            Path.home() / ".fonts",
        ]
    elif sys.platform == "win32":
        import os

        windir = os.environ.get("WINDIR", "C:\\Windows")
        font_dirs = [Path(windir) / "Fonts"]

    for font_filename in fonts_to_check:
        found = False
        for directory in font_dirs:
            # Simple recursive search could be slow, so we just check direct or use glob if needed.
            # Most users install fonts at the top level of these dirs or one level deep.
            # Let's do a quick rglob for the filename.
            if not directory.exists():
                continue

            try:
                # Use rglob to find the file in subdirectories
                if any(directory.rglob(font_filename)):
                    found = True
                    break
            except OSError:
                continue

        yield CheckResult(
            name=f"System Font: {font_filename}",
            passed=found,
            message="Found" if found else "Not found",
            details="System font usage requires this font to be installed." if not found else None,
        )


def check_textual_available() -> bool:
    """Check if textual TUI library is available."""
    try:
        import textual  # noqa: F401

        return True
    except ImportError:
        return False


def run_doctor_checks() -> Generator[CheckResult, None, None]:
    """Run all doctor checks."""
    yield check_installation_integrity()
    yield from check_render_engines()
    yield from check_system_fonts()

    # Optional TUI dependency
    textual_available = check_textual_available()
    yield CheckResult(
        name="Textual (TUI)",
        passed=textual_available,
        message="Available" if textual_available else "Not available",
        details="Required for interactive configuration editor (skim configure)."
        if not textual_available
        else None,
    )
