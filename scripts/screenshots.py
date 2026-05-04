"""Generate Textual TUI screenshots for the docs.

Each shot drives the TUI through Textual's Pilot (simulated keypresses, clicks,
and direct state mutations) into a known state, then exports the current frame
as an SVG. Run via ``just screenshots``.

To add a new shot, append an entry to ``SHOTS`` below. The setup callable
receives the running ``Pilot`` and may press keys, click selectors, or assign
to widget state — Textual will re-render synchronously after a ``pilot.pause()``.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import yaml

from skim.tui.app import SkimConfigApp

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CONFIG = ROOT / "samples" / "config" / "SvalCOLEMAK-config.yaml"
OUTPUT_DIR = ROOT / "docs" / "_static" / "tui"
TERM_SIZE = (120, 36)

# Nerd Font injection. Override either via env var or by editing the constants.
# The SVG that Textual produces hard-codes plain "Fira Code" (no Nerd glyphs);
# we inject a new @font-face and prepend the Nerd Font to the family stack so
# Private-Use-Area glyphs render in the docs site.
NERD_FONT_NAME = os.environ.get("SCREENSHOT_NERD_FONT_NAME", "JetBrainsMono Nerd Font")
NERD_FONT_URL = os.environ.get(
    "SCREENSHOT_NERD_FONT_URL",
    "https://cdn.jsdelivr.net/gh/ryanoasis/nerd-fonts@v3.2.1/patched-fonts/JetBrainsMono/Ligatures/Regular/JetBrainsMonoNerdFont-Regular.ttf",
)
NERD_FONT_FORMAT = os.environ.get("SCREENSHOT_NERD_FONT_FORMAT", "truetype")

PilotSetup = Callable[[Any], Awaitable[None]]


def _load_config(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def _inject_nerd_font(svg_path: Path) -> None:
    """Patch an SVG so its glyphs render in the configured Nerd Font.

    The Rich-generated SVG ships with @font-face blocks for plain "Fira Code"
    and uses ``font-family: Fira Code, monospace`` on every text run. We add
    one more @font-face for the Nerd Font and prepend it to the family stack;
    Fira Code stays as a fallback, so non-Nerd glyphs are unaffected.
    """
    if not NERD_FONT_URL:
        return
    text = svg_path.read_text(encoding="utf-8")
    new_face = (
        f'    @font-face {{\n'
        f'        font-family: "{NERD_FONT_NAME}";\n'
        f'        src: local("{NERD_FONT_NAME}"),\n'
        f'             url("{NERD_FONT_URL}") format("{NERD_FONT_FORMAT}");\n'
        f'    }}\n'
    )
    # Insert the new @font-face just after the opening <style> tag.
    text = text.replace("<style>\n", f"<style>\n{new_face}", 1)
    # Push the Nerd Font to the front of every Fira Code stack.
    text = re.sub(
        r"font-family:\s*Fira Code,\s*monospace",
        f'font-family: "{NERD_FONT_NAME}", Fira Code, monospace',
        text,
    )
    svg_path.write_text(text, encoding="utf-8")


async def _capture(name: str, config: dict[str, Any], setup: PilotSetup) -> Path:
    app = SkimConfigApp(config_data=config)
    target = OUTPUT_DIR / f"{name}.svg"
    async with app.run_test(size=TERM_SIZE) as pilot:
        await pilot.pause()
        await setup(pilot)
        await pilot.pause()
        app.save_screenshot(filename=target.name, path=str(OUTPUT_DIR))
    _inject_nerd_font(target)
    return target


async def _initial(_pilot: Any) -> None:
    """No-op — capture the freshly-mounted app."""


async def _switch_to_keycodes(pilot: Any) -> None:
    pilot.app.query_one("TabbedContent").active = "keycodes-tab"


async def _switch_to_output(pilot: Any) -> None:
    pilot.app.query_one("TabbedContent").active = "output-tab"


async def _switch_to_output_style(pilot: Any) -> None:
    pilot.app.query_one("TabbedContent").active = "output-tab"
    await pilot.pause()
    pilot.app.query_one("#output-style-section").scroll_visible(top=True, animate=False)


SHOTS: list[tuple[str, PilotSetup]] = [
    ("keyboard-tab", _initial),
    ("keycodes-tab", _switch_to_keycodes),
    ("output-tab", _switch_to_output),
    ("output-style-tab", _switch_to_output_style),
]


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = _load_config(SAMPLE_CONFIG)
    print(f"Generating {len(SHOTS)} screenshot(s) at {TERM_SIZE[0]}x{TERM_SIZE[1]}")
    for name, setup in SHOTS:
        target = await _capture(name, config, setup)
        size = target.stat().st_size
        print(f"  {target.relative_to(ROOT)} ({size // 1024} KB)")


if __name__ == "__main__":
    asyncio.run(main())
