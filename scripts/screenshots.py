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
- Set ``focus`` to a callable that returns a widget to focus before the
  screenshot is saved. Useful for showing the focused state of a field
  (e.g. accent-coloured input border).

To add a new shot, append an entry to ``SHOTS`` below. The setup callable
receives the running ``Pilot`` and may press keys, click selectors, or assign
to widget state — Textual will re-render synchronously after a ``pilot.pause()``.
"""

from __future__ import annotations

import asyncio
import base64
import html
import io
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from textual.widgets import TabbedContent

from skim.assets import ASSETS
from skim.tui.app import SkimConfigApp
from skim.tui.widgets import SkimFooter, SkimVerticalScroll

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CONFIG = ROOT / "samples" / "config" / "SvalCOLEMAK-config.yaml"
OUTPUT_DIR = ROOT / "docs" / "_static" / "tui"

WIDTH = 120
PROBE_HEIGHT = 500

NERD_FONT_FAMILY = "JetBrainsMono Nerd Font Mono"
"""Font family the screenshot pipeline embeds and writes into the SVG stack.

Rich's SVG export hard-codes ``font-family: Fira Code, monospace`` on every
text run. Fira Code lacks the Nerd-Font PUA glyphs Skim's TUI paints (chip
caps ``\\ue0b6``/``\\ue0b4``, scrollbar arrows, etc.), so the rendered PUA
codepoints would fall through to tofu. We replace the family with the
Nerd-Font-patched Mono variant of JetBrains Mono, embed a subset of that
font as a base64 data URL, and end up with a self-contained SVG where text,
box-drawing, and PUA glyphs all render from the same cell-aligned font.
"""

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
        focus: Optional callable that returns a widget to focus before
            the screenshot is saved. The capture pass calls
            ``widget.focus()`` and waits for layout to settle, so the
            screenshot reflects the focused state (e.g. a focus-coloured
            border on inputs).
    """

    name: str
    setup: PilotSetup
    width: int = WIDTH
    height: int | None = None
    clip: ClipTarget | None = None
    clip_padding: tuple[int, int, int, int] = (0, 0, 0, 0)
    focus: ClipTarget | None = None


def _load_config(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


TERMINAL_BACKGROUND = "#121212"


def _strip_outside_region(
    text: str, region: Any, cell_w: float, cell_h: float
) -> str:
    """Drop SVG elements that don't intersect the widget rect.

    Removes Rich's terminal-window chrome (outer rounded rect, title text,
    traffic-light circles), every matrix cell rect whose bbox falls entirely
    outside the widget, and every text whose row sits outside the widget's
    row range or whose textLength sits outside the widget's x-range. Cell
    rects that partially overlap the widget are clamped to the widget
    bounds so they can't bleed into the padding ring. Per-line clip-path
    defs that no remaining text references are also dropped.
    """
    wx0 = region.x * cell_w
    wy0 = region.y * cell_h
    wx1 = (region.x + region.width) * cell_w
    wy1 = (region.y + region.height) * cell_h

    def _filter_rect(match: re.Match) -> str:
        attrs_pre = match.group(1)
        x = float(match.group(2))
        y = float(match.group(3))
        w = float(match.group(4))
        h = float(match.group(5))
        attrs_post = match.group(6)
        nx = max(x, wx0)
        ny = max(y, wy0)
        nx_end = min(x + w, wx1)
        ny_end = min(y + h, wy1)
        nw = nx_end - nx
        nh = ny_end - ny
        if nw <= 0 or nh <= 0:
            return ""
        return (
            f'<rect{attrs_pre}x="{nx:g}" y="{ny:g}" '
            f'width="{nw:g}" height="{nh:g}"{attrs_post}/>'
        )

    # Cell rects: tagged with shape-rendering="crispEdges". Order of x/y/w/h
    # in Rich's output is consistent, so the stricter regex is safe.
    text = re.sub(
        r'<rect( [^>]*?)x="([\d.-]+)" y="([\d.-]+)" '
        r'width="([\d.]+)" height="([\d.]+)"'
        r'( [^>]*shape-rendering="crispEdges"[^>]*)/>',
        _filter_rect,
        text,
    )

    rows_inside = set(range(region.y, region.y + region.height))
    referenced_lines: set[int] = set()

    def _filter_text(match: re.Match) -> str:
        full = match.group(0)
        line_match = re.search(r"#terminal-\d+-line-(\d+)\)", full)
        if not line_match:
            return full
        line_n = int(line_match.group(1))
        if line_n not in rows_inside:
            return ""
        x_match = re.search(r'\bx="([\d.-]+)"', full)
        len_match = re.search(r'textLength="([\d.]+)"', full)
        if x_match and len_match:
            tx = float(x_match.group(1))
            tlen = float(len_match.group(1))
            if tx + tlen <= wx0 or tx >= wx1:
                return ""
        referenced_lines.add(line_n)
        return full

    # Cell texts carry class "terminal-N-rM" (the title uses class
    # "terminal-N-title" and is dropped by the chrome step).
    text = re.sub(
        r'<text class="terminal-\d+-r\d+"[^>]*>[^<]*</text>',
        _filter_text,
        text,
    )

    # Per-line clip-paths whose line is no longer referenced.
    text = re.sub(
        r'<clipPath id="terminal-\d+-line-(\d+)">\s*<rect[^/]*/>\s*</clipPath>\s*',
        lambda m: "" if int(m.group(1)) not in referenced_lines else m.group(0),
        text,
    )

    # Rich chrome: outer rounded rect, title text, traffic-light group.
    text = re.sub(
        r'<rect[^/]*rx="8"/>',
        "",
        text,
        count=1,
    )
    text = re.sub(
        r'<text class="terminal-\d+-title"[^>]*>[^<]*</text>',
        "",
        text,
        count=1,
    )
    text = re.sub(
        r'<g transform="translate\(26,22\)">.*?</g>',
        "",
        text,
        count=1,
        flags=re.DOTALL,
    )

    return text


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

    text = _strip_outside_region(text, region, cell_w, cell_h)

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


def _used_codepoints(svg_text: str) -> set[int]:
    """Return every Unicode codepoint painted inside an SVG ``<text>`` element.

    Walks every ``<text>...</text>`` block, decodes HTML entities (Rich emits
    ``&#160;`` for non-breaking spaces, ``&lt;`` etc.), and collects the
    resulting characters. fontTools silently ignores any codepoint the font
    doesn't carry, so passing the union here is safe — we use the Mono
    variant of Symbols Nerd Font, which carries PUA glyphs plus the
    box-drawing / monospace-spacing characters Rich emits, all sized to a
    single cell width.
    """
    codepoints: set[int] = set()
    for match in re.finditer(r"<text [^>]*>([^<]*)</text>", svg_text):
        for ch in html.unescape(match.group(1)):
            codepoints.add(ord(ch))
    return codepoints


def _embed_nerd_font(svg_path: Path) -> None:
    """Embed a subset of ``JetBrainsMonoNerdFontMono-Regular.ttf`` into the SVG.

    Subsets the bundled Nerd-Font-patched JetBrains Mono down to the
    codepoints painted in this SVG, encodes the subset as a base64 data
    URL, injects an ``@font-face`` rule just after the SVG's opening
    ``<style>`` tag, and replaces every ``Fira Code, monospace`` stack
    with ``"<NERD_FONT_FAMILY>", monospace`` so every glyph — text,
    box-drawing, Nerd-Font symbols — resolves against the embedded font's
    cell-aligned metrics. The rendered SVG is self-contained with no
    external font load.

    Subsetting matters here — the full font is ~2.4 MB, while a subset
    for a typical shot is in the low-tens of KB.
    """
    from fontTools.subset import Options, Subsetter, load_font

    text = svg_path.read_text(encoding="utf-8")
    codepoints = _used_codepoints(text)
    if not codepoints:
        return

    options = Options()
    options.notdef_glyph = True
    options.notdef_outline = True
    options.recommended_glyphs = True
    # FontForge build-time tables fontTools doesn't know how to subset.
    options.drop_tables = ["PfEd", "FFTM"]

    tt_font = load_font(str(ASSETS.font_jetbrains_mono_nerd), options)
    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(tt_font)

    buf = io.BytesIO()
    tt_font.save(buf)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")

    new_face = (
        f"    @font-face {{\n"
        f'        font-family: "{NERD_FONT_FAMILY}";\n'
        f'        src: url("data:font/ttf;base64,{encoded}") format("truetype");\n'
        f"    }}\n"
    )
    text = text.replace("<style>\n", f"<style>\n{new_face}", 1)
    text = re.sub(
        r"font-family:\s*Fira Code,\s*monospace",
        f'font-family: "{NERD_FONT_FAMILY}", monospace',
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
        if shot.focus is not None:
            shot.focus(capture_app).focus()
            await pilot.pause()
        capture_app.save_screenshot(filename=target.name, path=str(OUTPUT_DIR))
        if shot.clip is not None:
            clip_region = shot.clip(capture_app).region

    if clip_region is not None:
        _crop_svg_to_region(target, clip_region, padding=shot.clip_padding)
    _embed_nerd_font(target)
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


async def _initial_double_south_on(pilot: Any) -> None:
    """Initial state but with the Double South switch set to ``True``.

    The sample config keeps ``keyboard.features.double_south = false`` so the
    default setup renders the switch in its off state. For documentation we
    want the on state — flip the value reactively so the screenshot shows
    the active styling.
    """
    pilot.app.query_one("#double-south").value = True


def _active_pane_scrollable(app: SkimConfigApp) -> SkimVerticalScroll:
    """Return the outer ``SkimVerticalScroll`` of whichever tab is active."""
    tabbed = app.query_one(TabbedContent)
    pane = tabbed.get_pane(tabbed.active)
    return pane.query_one(SkimVerticalScroll)


def _tabs_strip(app: SkimConfigApp) -> Any:
    """Return the ``Tabs`` widget rendered at the top of ``TabbedContent``."""
    return app.query_one(TabbedContent).query_one("Tabs")


def _status_bar(app: SkimConfigApp) -> Any:
    """Return the ``SkimFooter`` widget at the bottom of the app."""
    return app.query_one(SkimFooter)


def _field_row_for(descendant_id: str) -> ClipTarget:
    """Return a clip target resolving to the field-row that contains ``descendant_id``.

    The keyboard / output tabs build each editable row as a ``Horizontal``
    that wraps a left-aligned label and the editing widget. Looking up the
    editing widget by id and walking up to its parent gives us the full
    label + component bounding box.
    """

    def _resolver(app: SkimConfigApp) -> Any:
        return app.query_one(f"#{descendant_id}").parent

    return _resolver


def _widget(selector: str) -> ClipTarget:
    """Return a clip target resolving to the first widget matching ``selector``."""

    def _resolver(app: SkimConfigApp) -> Any:
        return app.query_one(selector)

    return _resolver


ANATOMY_FRAME = {"width": 107, "height": 29}
"""Shared 107x29 base frame for every Anatomy-section illustration.

Width 107 fits the seven status-bar bindings on one row exactly; height 29
leaves the keyboard tab's list-view buttons partially clipped at the
bottom so the scrolling affordance reads from the screenshot alone.
"""


SHOTS: list[Shot] = [
    # Full Anatomy reference frame.
    Shot("keyboard-tab", _initial, **ANATOMY_FRAME),
    Shot("keycodes-tab", _switch_to_keycodes),
    Shot("output-tab", _switch_to_output),
    Shot("output-style-tab", _switch_to_output_style),
    # Per-piece crops of the Anatomy frame, each padded by 1 row top/bottom
    # and 3 cols left/right with the terminal background colour so the
    # widget reads as its own card rather than a slice from the frame.
    Shot(
        "tabs",
        _initial,
        **ANATOMY_FRAME,
        clip=_tabs_strip,
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        "scrolling-area",
        _initial,
        **ANATOMY_FRAME,
        clip=_active_pane_scrollable,
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        "status-bar",
        _initial,
        **ANATOMY_FRAME,
        clip=_status_bar,
        clip_padding=(1, 3, 1, 3),
    ),
    # Field-component shots — each clips to a single label-plus-widget row,
    # using a terminal width tight enough that the component sits at its
    # natural footprint (the field label is fixed at 22 cells; the rest is
    # the component itself). Heights auto-fit so the target row is always
    # rendered regardless of which section it lives in.
    Shot(
        "field-text-input",
        _initial,
        width=50,
        clip=_field_row_for("keymap-title-text"),
        clip_padding=(1, 3, 1, 3),
        focus=_widget("#keymap-title-text"),
    ),
    Shot(
        "field-numeric-input",
        _switch_to_output,
        width=50,
        clip=_field_row_for("layout-width"),
        clip_padding=(1, 3, 1, 3),
        focus=_widget("#layout-width"),
    ),
    Shot(
        "field-switch",
        _initial_double_south_on,
        width=35,
        clip=_widget("#features-row"),
        clip_padding=(1, 3, 1, 3),
        focus=_widget("#double-south"),
    ),
    Shot(
        "field-select",
        _switch_to_output,
        width=60,
        clip=_field_row_for("hold-symbol-position"),
        clip_padding=(1, 3, 1, 3),
        focus=_widget("#hold-symbol-position"),
    ),
    Shot(
        # The sample config gives every layer an explicit gradient list, so the
        # LayerColorListPane initialises in ``manual-mode`` — that hides
        # ``#lc-dynamic-color`` via CSS and reveals the ``lc-manual-step-N``
        # rows. Clip to step 0 (label + swatch + colour input + autocomplete).
        # The step input is disabled until the pane enters edit mode, so we
        # don't focus it here — the screenshot shows the read-only state.
        "field-color-input",
        _switch_to_output,
        width=70,
        clip=_widget("#lc-manual-step-0"),
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        # Focus the layer ListView so the selected entry is highlighted; the
        # detail-side inputs stay disabled (they only enable in edit mode).
        "field-list-detail",
        _initial,
        width=95,
        clip=_widget("LayerListPane"),
        clip_padding=(1, 3, 1, 3),
        focus=_widget("LayerListPane .ldp-list"),
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
