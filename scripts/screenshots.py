"""Generate Textual TUI screenshots for the docs.

Each shot drives the TUI through Textual's Pilot (simulated keypresses, clicks,
and direct state mutations) into a known state, then exports the current frame
as an SVG. Run via ``just screenshots``.

Two-pass auto-fit capture
-------------------------

Textual's ``app.save_screenshot`` exports the entire virtual terminal, so the
final SVG height is exactly the terminal height. To capture a tab in full
without internal scrolling we run the shot twice:

1. **Probe pass.** Launch the app at the shot's ``width`` and a generously
   tall provisional terminal (``PROBE_HEIGHT``), run the shot's setup, then
   override every ``SkimVerticalScroll`` inside the active tab to
   ``height: auto`` so the scrollable expands to its natural content size.
   Read the rendered region to compute the smallest terminal height that
   fits the content.
2. **Capture pass.** Launch a fresh app at exactly ``(width, measured_height)``,
   replay the setup and the same CSS overrides, then ``save_screenshot``.

Per-shot configuration
----------------------

Each shot is a ``Shot`` instance with a name, an async setup callable, and
optional ``width``, ``height`` and ``clip`` overrides.

- Set a smaller ``width`` to capture a narrow component without leftover
  whitespace beside it.
- Leave ``height`` as ``None`` (the default) to auto-fit the active tab's
  content. Set ``height`` to a fixed integer to skip the auto-fit probe
  and capture the active tab in its natural scrolling state — useful for
  showing the user that a tab can scroll.
- Set ``clip`` to a callable that returns a single widget; the saved SVG's
  ``viewBox`` is then cropped to that widget's region. Everything outside
  the widget (tab strip, footer, Rich's terminal-window chrome) is left in
  the SVG file but hidden by the new viewBox, so the rendered image shows
  only the widget you want documented.
- Set ``clip_padding`` to a ``(top, right, bottom, left)`` tuple of cell
  counts to add visual breathing room around the clipped widget. The
  viewBox expands by that many cells on each side, and a background rect
  is injected so the padding area shows the terminal background colour
  instead of the chrome / footer that sits outside the widget's region.

To add a new shot, append an entry to ``SHOTS`` below. The setup callable
receives the running ``Pilot`` and may press keys, click selectors, or assign
to widget state — Textual will re-render synchronously after a ``pilot.pause()``.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from textual.widgets import TabbedContent

from skim.tui.app import SkimConfigApp
from skim.tui.widgets import SkimFooter, SkimVerticalScroll

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CONFIG = ROOT / "samples" / "config" / "SvalCOLEMAK-config.yaml"
OUTPUT_DIR = ROOT / "docs" / "_static" / "tui"

WIDTH = 120
PROBE_HEIGHT = 500

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


ClipTarget = Callable[[Any], Any]


@dataclass(frozen=True)
class Shot:
    """A single screenshot specification.

    Attributes:
        name: Output filename stem (``<name>.svg``).
        setup: Async callable that drives the app into the desired state.
        width: Virtual terminal width in cells. Defaults to ``WIDTH``.
        height: Virtual terminal height in cells. ``None`` (the default)
            auto-fits the height to the active tab's natural content size
            by overriding every ``SkimVerticalScroll`` to ``height: auto``.
            An integer skips the probe and the CSS override, giving you a
            fixed-height capture in the tab's natural scrolling state.
        clip: Optional callable that takes the running app and returns a
            single widget. After ``save_screenshot``, the SVG's ``viewBox``
            is rewritten to expose only that widget's rendered region. The
            rest of the SVG (tab strip, footer, Rich chrome) stays in the
            file but renders outside the visible rect.
        clip_padding: Cell counts ``(top, right, bottom, left)`` of
            breathing room added around the clipped region. A background
            rect matching the terminal background colour is injected so
            the padding area doesn't expose adjacent widgets or Rich's
            chrome. Ignored when ``clip`` is ``None``.
    """

    name: str
    setup: PilotSetup
    width: int = WIDTH
    height: int | None = None
    clip: ClipTarget | None = None
    clip_padding: tuple[int, int, int, int] = (0, 0, 0, 0)


def _load_config(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


TERMINAL_BACKGROUND = "#121212"


def _crop_svg_to_region(
    svg_path: Path,
    region: Any,
    padding: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> None:
    """Rewrite the SVG's ``viewBox`` to expose only the cells inside ``region``.

    Reads the matrix-group's ``translate(x, y)`` and the matrix style's
    ``font-size`` / ``line-height`` to derive grid offsets and per-cell
    pixel dimensions, then rewrites the root ``viewBox``. Other elements
    (Rich's outer chrome, the tab strip, the footer) stay in the file but
    render outside the new viewBox so they're invisible.

    ``padding`` is a ``(top, right, bottom, left)`` tuple of cell counts
    added on each side of ``region``. When any side is non-zero, the
    function also injects a background rect just before the matrix group
    so the padded area shows ``TERMINAL_BACKGROUND`` instead of leaking
    the surrounding tab strip / footer / chrome.

    The cell-width ratio (font-size × 0.61) matches Rich's monospace cell
    width for the default JetBrains Mono / Fira Code metrics; if Rich
    changes its export, only this constant needs to move.
    """
    text = svg_path.read_text(encoding="utf-8")

    matrix_group = re.search(
        r'<g transform="translate\(([\d.]+),\s*([\d.]+)\)"\s+clip-path="url\(#terminal-',
        text,
    )
    if not matrix_group:
        raise ValueError(f"{svg_path}: could not locate matrix translate group")
    matrix_x = float(matrix_group.group(1))
    matrix_y = float(matrix_group.group(2))

    metrics = re.search(
        r"font-size:\s*(\d+(?:\.\d+)?)px;\s*line-height:\s*(\d+(?:\.\d+)?)px",
        text,
    )
    if not metrics:
        raise ValueError(f"{svg_path}: could not locate matrix font metrics")
    font_size_px = float(metrics.group(1))
    cell_h = float(metrics.group(2))
    cell_w = font_size_px * 0.61

    pad_top, pad_right, pad_bottom, pad_left = padding
    x_px = matrix_x + region.x * cell_w - pad_left * cell_w
    y_px = matrix_y + region.y * cell_h - pad_top * cell_h
    w_px = (region.width + pad_left + pad_right) * cell_w
    h_px = (region.height + pad_top + pad_bottom) * cell_h

    if any(side > 0 for side in padding):
        # Tighten the matrix's clip-path to the widget region (in matrix-local
        # coordinates) so cells outside the widget — tab strip, footer, etc. —
        # don't render on top of the background rect we're about to inject.
        clip_x = region.x * cell_w
        clip_y = region.y * cell_h
        clip_w = region.width * cell_w
        clip_h = region.height * cell_h
        text = re.sub(
            r'(<clipPath id="terminal-\d+-clip-terminal">\s*)<rect[^/]*/>',
            rf'\1<rect x="{clip_x:g}" y="{clip_y:g}" '
            rf'width="{clip_w:g}" height="{clip_h:g}"/>',
            text,
            count=1,
        )

        # Inject a background rect spanning the padded viewBox just before
        # the matrix group so the padding ring shows uniform terminal-bg
        # rather than leaking the SVG chrome underneath.
        bg_rect = (
            f'<rect x="{x_px:g}" y="{y_px:g}" '
            f'width="{w_px:g}" height="{h_px:g}" '
            f'fill="{TERMINAL_BACKGROUND}"/>'
        )
        text = re.sub(
            r'(<g transform="translate\([\d.]+,\s*[\d.]+\)"\s+clip-path="url\(#terminal-)',
            bg_rect + r"\1",
            text,
            count=1,
        )

    new_viewbox = f"{x_px:g} {y_px:g} {w_px:g} {h_px:g}"
    text = re.sub(r'viewBox="[^"]+"', f'viewBox="{new_viewbox}"', text, count=1)
    svg_path.write_text(text, encoding="utf-8")


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
    text = text.replace("<style>\n", f"<style>\n{new_face}", 1)
    text = re.sub(
        r"font-family:\s*Fira Code,\s*monospace",
        f'font-family: "{NERD_FONT_NAME}", Fira Code, monospace',
        text,
    )
    svg_path.write_text(text, encoding="utf-8")


def _expand_active_pane_scrollables(app: SkimConfigApp) -> list[SkimVerticalScroll]:
    """Override every ``SkimVerticalScroll`` inside the active TabPane to ``height: auto``.

    Returns the list of scrollables that were adjusted, so the caller can
    measure their rendered region after layout reflow. We deliberately do
    not touch nested scrollables outside ``SkimVerticalScroll`` (e.g. the
    fixed-height list inside ``ListDetailPane``) — those are intentionally
    bounded and their content is inherently scroll-only.
    """
    tabbed = app.query_one(TabbedContent)
    pane = tabbed.get_pane(tabbed.active)
    scrollables = list(pane.query(SkimVerticalScroll))
    for scrollable in scrollables:
        scrollable.styles.height = "auto"
        scrollable.styles.max_height = None
    return scrollables


def _required_height(
    app: SkimConfigApp, scrollables: list[SkimVerticalScroll]
) -> int:
    """Compute the smallest terminal height that fits the active tab's content.

    Sums the bottom edge of the lowest expanded scrollable (so chrome above
    is included via ``region.y``) plus the footer's height (so it isn't
    clipped). Falls back to the active TabPane's region when the active tab
    has no SkimVerticalScroll (defensive — every current tab has one).
    """
    bottoms = [w.region.bottom for w in scrollables if w.region.height > 0]
    if not bottoms:
        tabbed = app.query_one(TabbedContent)
        bottoms = [tabbed.get_pane(tabbed.active).region.bottom]
    content_bottom = max(bottoms)

    footer_widgets = list(app.query(SkimFooter))
    footer_height = footer_widgets[0].region.height if footer_widgets else 0
    return content_bottom + footer_height


async def _settle(pilot: Any, setup: PilotSetup, *, expand: bool) -> None:
    """Run setup, optionally expand active-pane scrollables, settle layout."""
    await pilot.pause()
    await setup(pilot)
    await pilot.pause()
    if expand:
        _expand_active_pane_scrollables(pilot.app)
        await pilot.pause()


async def _capture(shot: Shot, config: dict[str, Any]) -> tuple[Path, int]:
    target = OUTPUT_DIR / f"{shot.name}.svg"

    if shot.height is None:
        # Probe pass — measure the auto-fit height for the active tab.
        probe_app = SkimConfigApp(config_data=config)
        async with probe_app.run_test(size=(shot.width, PROBE_HEIGHT)) as pilot:
            await _settle(pilot, shot.setup, expand=True)
            scrollables = list(
                probe_app.query_one(TabbedContent)
                .get_pane(probe_app.query_one(TabbedContent).active)
                .query(SkimVerticalScroll)
            )
            height = _required_height(probe_app, scrollables)
    else:
        height = shot.height

    capture_app = SkimConfigApp(config_data=config)
    clip_region = None
    async with capture_app.run_test(size=(shot.width, height)) as pilot:
        await _settle(pilot, shot.setup, expand=shot.height is None)
        capture_app.save_screenshot(filename=target.name, path=str(OUTPUT_DIR))
        if shot.clip is not None:
            clip_region = shot.clip(capture_app).region

    if clip_region is not None:
        _crop_svg_to_region(target, clip_region, padding=shot.clip_padding)
    _inject_nerd_font(target)
    return target, height


async def _initial(_pilot: Any) -> None:
    """No-op — capture the freshly-mounted app."""


async def _switch_to_keycodes(pilot: Any) -> None:
    pilot.app.query_one(TabbedContent).active = "keycodes-tab"


async def _switch_to_output(pilot: Any) -> None:
    pilot.app.query_one(TabbedContent).active = "output-tab"


async def _switch_to_output_style(pilot: Any) -> None:
    pilot.app.query_one(TabbedContent).active = "output-tab"
    await pilot.pause()
    pilot.app.query_one("#output-style-section").scroll_visible(top=True, animate=False)


def _active_pane_scrollable(app: SkimConfigApp) -> SkimVerticalScroll:
    """Return the outer ``SkimVerticalScroll`` of whichever tab is active."""
    tabbed = app.query_one(TabbedContent)
    pane = tabbed.get_pane(tabbed.active)
    return pane.query_one(SkimVerticalScroll)


SHOTS: list[Shot] = [
    Shot("keyboard-tab", _initial),
    Shot("keycodes-tab", _switch_to_keycodes),
    Shot("output-tab", _switch_to_output),
    Shot("output-style-tab", _switch_to_output_style),
    # Fixed-height shot showing the Output tab in its natural scrolling
    # state (content clipped, scrollbar visible). The viewBox is then
    # cropped to the SkimVerticalScroll's region so the rendered SVG
    # contains only the scrolling component (no tab strip, no footer).
    Shot(
        "scrolling-area",
        _switch_to_output,
        height=30,
        clip=_active_pane_scrollable,
        clip_padding=(1, 3, 1, 3),
    ),
]


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = _load_config(SAMPLE_CONFIG)
    print(f"Generating {len(SHOTS)} screenshot(s); width and height per shot")
    for shot in SHOTS:
        target, height = await _capture(shot, config)
        size = target.stat().st_size
        print(f"  {target.relative_to(ROOT)} ({shot.width}x{height}, {size // 1024} KB)")


if __name__ == "__main__":
    asyncio.run(main())
