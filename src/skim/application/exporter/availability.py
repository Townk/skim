"""Availability checks for render engines."""

import os
import sys
from pathlib import Path


def setup_cairo_library_path() -> None:
    """Configure library paths for cairocffi to find homebrew cairo on macOS."""
    if sys.platform != "darwin":
        return

    homebrew_lib = Path("/opt/homebrew/lib")
    if not homebrew_lib.exists():
        return

    # Add homebrew lib to DYLD_LIBRARY_PATH for cairocffi
    current_path = os.environ.get("DYLD_LIBRARY_PATH", "")
    homebrew_lib_str = str(homebrew_lib)
    if homebrew_lib_str not in current_path:
        paths = [homebrew_lib_str]
        if current_path:
            paths.append(current_path)
        os.environ["DYLD_LIBRARY_PATH"] = ":".join(paths)


def check_playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                browser_path = p.chromium.executable_path
                if browser_path and Path(browser_path).exists():
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False


def check_cairo_available() -> bool:
    """Check if Cairo library is available without importing heavy modules."""
    try:
        # Setup cairo library path before checking availability
        setup_cairo_library_path()

        import cairocffi  # noqa: F401
        import cairosvg  # noqa: F401

        return True
    except (ImportError, OSError):
        return False
