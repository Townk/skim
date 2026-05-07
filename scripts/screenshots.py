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
from textual.geometry import Region
from textual.widgets import TabbedContent
from textual.widgets._select import SelectOverlay

from skim.assets import ASSETS
from skim.tui.app import SkimConfigApp
from skim.tui.widgets import SkimFooter, SkimVerticalScroll

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CONFIG = ROOT / "samples" / "config" / "SvalCOLEMAK-config.yaml"
SKIM_SAMPLE_CONFIG = ROOT / "samples" / "config" / "skim-config.yaml"
VIAL_SAMPLE_KEYMAP = ROOT / "samples" / "keymaps" / "vial-sample.vil"
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
        config: Optional path to a YAML configuration to load for this
            shot. ``None`` (the default) uses the module-level
            ``SAMPLE_CONFIG``. Override per-shot when a different config
            is needed — e.g. one with populated keycodes lists so the
            detail-side editor renders real entries.
        keymap: Optional path to a keymap file (``.vil`` / ``.kbi`` /
            ``.json``) to derive the config from — same flow as
            ``skim configure -i -k <path>``. Takes precedence over
            ``config`` when both are set, since keymap-driven configs
            populate keycodes.macros / keycodes.tap_dances lists from
            the keymap's own metadata.
    """

    name: str
    setup: PilotSetup
    width: int = WIDTH
    height: int | None = None
    clip: ClipTarget | None = None
    clip_padding: tuple[int, int, int, int] = (0, 0, 0, 0)
    focus: ClipTarget | None = None
    config: Path | None = None
    keymap: Path | None = None


def _load_config(path: Path) -> dict[str, Any]:
    """Load a YAML config and route it through ``SkimConfig`` so the result
    carries every default the TUI's compose step expects (e.g.
    ``output.layout`` is required at runtime even if the YAML omits it).
    """
    from skim.data.config import SkimConfig

    raw = yaml.safe_load(path.read_text()) or {}
    return SkimConfig.model_validate(raw).model_dump(mode="json")


def _load_config_from_keymap(keymap_path: Path) -> dict[str, Any]:
    """Mirror ``cli.configure -i -k <keymap>``: derive a SkimConfig from a
    keymap file so the TUI launches with macros / tap-dances / overrides
    populated from the keymap's own metadata.
    """
    from skim.application.config_generator import ConfigGenerator
    from skim.application.loaders.keymap_loader import _detect_format_from_path
    from skim.data.config import SkimConfig
    from skim.domain import KeymapType

    generator = ConfigGenerator()
    raw = keymap_path.read_text()
    detected = _detect_format_from_path(keymap_path)
    if detected == KeymapType.KEYBARD:
        yaml_str = generator.generate_from_keybard(raw)
    else:
        yaml_str = generator.generate_from_keymap(raw)
    raw_dict = yaml.safe_load(yaml_str) or {}
    return SkimConfig.model_validate(raw_dict).model_dump(mode="json")


TERMINAL_BACKGROUND = "#121212"


def _strip_outside_regions(
    text: str, regions: list[Region], cell_w: float, cell_h: float
) -> str:
    """Drop SVG elements that don't intersect any of the widget regions.

    Removes Rich's terminal-window chrome (outer rounded rect, title text,
    traffic-light circles), every matrix cell rect whose bbox falls entirely
    outside every region, and every text whose row + x-range matches no
    region. Cell rects that partially overlap a region are clamped to the
    region with which they have the largest overlap, so they can't bleed
    into the dead zone between regions or into the padding ring. Per-line
    clip-path defs that no remaining text references are also dropped.

    With more than one region, the dead zone between regions is left empty
    (the padding-bg rect, when injected, fills it with the terminal-bg
    colour); cells from intervening widgets that happened to sit there get
    cleanly removed.
    """
    boxes = [
        (
            r.x * cell_w,
            r.y * cell_h,
            (r.x + r.width) * cell_w,
            (r.y + r.height) * cell_h,
        )
        for r in regions
    ]

    def _filter_rect(match: re.Match) -> str:
        attrs_pre = match.group(1)
        x = float(match.group(2))
        y = float(match.group(3))
        w = float(match.group(4))
        h = float(match.group(5))
        attrs_post = match.group(6)
        best: tuple[float, float, float, float] | None = None
        best_area = 0.0
        for bx0, by0, bx1, by1 in boxes:
            nx = max(x, bx0)
            ny = max(y, by0)
            nx_end = min(x + w, bx1)
            ny_end = min(y + h, by1)
            nw = nx_end - nx
            nh = ny_end - ny
            if nw > 0 and nh > 0:
                area = nw * nh
                if area > best_area:
                    best_area = area
                    best = (nx, ny, nw, nh)
        if best is None:
            return ""
        nx, ny, nw, nh = best
        return (
            f'<rect{attrs_pre}x="{nx:g}" y="{ny:g}" '
            f'width="{nw:g}" height="{nh:g}"{attrs_post}/>'
        )

    text = re.sub(
        r'<rect( [^>]*?)x="([\d.-]+)" y="([\d.-]+)" '
        r'width="([\d.]+)" height="([\d.]+)"'
        r'( [^>]*shape-rendering="crispEdges"[^>]*)/>',
        _filter_rect,
        text,
    )

    referenced_lines: set[int] = set()

    def _filter_text(match: re.Match) -> str:
        full = match.group(0)
        line_match = re.search(r"#terminal-\d+-line-(\d+)\)", full)
        if not line_match:
            return full
        line_n = int(line_match.group(1))
        x_match = re.search(r'\bx="([\d.-]+)"', full)
        len_match = re.search(r'textLength="([\d.]+)"', full)
        tx = float(x_match.group(1)) if x_match else None
        tlen = float(len_match.group(1)) if len_match else None
        for r in regions:
            if not (r.y <= line_n < r.y + r.height):
                continue
            if tx is not None and tlen is not None:
                rx0 = r.x * cell_w
                rx1 = (r.x + r.width) * cell_w
                if tx + tlen <= rx0 or tx >= rx1:
                    continue
            referenced_lines.add(line_n)
            return full
        return ""

    text = re.sub(
        r'<text class="terminal-\d+-r\d+"[^>]*>[^<]*</text>',
        _filter_text,
        text,
    )

    text = re.sub(
        r'<clipPath id="terminal-\d+-line-(\d+)">\s*<rect[^/]*/>\s*</clipPath>\s*',
        lambda m: "" if int(m.group(1)) not in referenced_lines else m.group(0),
        text,
    )

    text = re.sub(r'<rect[^/]*rx="8"/>', "", text, count=1)
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


def _bounding_region(regions: list[Region]) -> Region:
    """Smallest Region containing every region in ``regions``."""
    min_x = min(r.x for r in regions)
    min_y = min(r.y for r in regions)
    max_x = max(r.x + r.width for r in regions)
    max_y = max(r.y + r.height for r in regions)
    return Region(min_x, min_y, max_x - min_x, max_y - min_y)


def _crop_svg_to_region(
    svg_path: Path,
    regions: list[Region],
    padding: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> None:
    """Rewrite the SVG's ``viewBox`` to expose only the cells inside ``regions``.

    A single region produces the obvious crop. Multiple regions produce a
    viewBox covering their bounding box, with strip-filtering removing any
    matrix content that doesn't intersect at least one of the regions —
    useful when a shot spans two non-contiguous widgets (e.g. a Select
    closed-state row plus its open dropdown overlay) and we want the dead
    zone between them blank rather than leaking adjacent widgets.

    Reads the matrix-group's ``translate(x, y)`` and the matrix style's
    ``font-size`` / ``line-height`` to derive grid offsets and per-cell
    pixel dimensions, then rewrites the root ``viewBox``. Other elements
    (Rich's outer chrome, the tab strip, the footer) are stripped from
    the file outright via :func:`_strip_outside_regions`.

    ``padding`` is a ``(top, right, bottom, left)`` tuple of cell counts
    added on each side of the bounding box. When any side is non-zero,
    the function also tightens the matrix clip-path to the bounding box
    and injects a background rect so the padding ring shows
    ``TERMINAL_BACKGROUND`` instead of leaking adjacent content.

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

    bbox = _bounding_region(regions)
    pad_top, pad_right, pad_bottom, pad_left = padding
    x_px = matrix_x + bbox.x * cell_w - pad_left * cell_w
    y_px = matrix_y + bbox.y * cell_h - pad_top * cell_h
    w_px = (bbox.width + pad_left + pad_right) * cell_w
    h_px = (bbox.height + pad_top + pad_bottom) * cell_h

    text = _strip_outside_regions(text, regions, cell_w, cell_h)

    if any(side > 0 for side in padding):
        clip_x = bbox.x * cell_w
        clip_y = bbox.y * cell_h
        clip_w = bbox.width * cell_w
        clip_h = bbox.height * cell_h
        text = re.sub(
            r'(<clipPath id="terminal-\d+-clip-terminal">\s*)<rect[^/]*/>',
            rf'\1<rect x="{clip_x:g}" y="{clip_y:g}" '
            rf'width="{clip_w:g}" height="{clip_h:g}"/>',
            text,
            count=1,
        )

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
    clip_regions: list[Region] | None = None
    async with capture_app.run_test(size=(shot.width, height)) as pilot:
        await _settle(pilot, shot.setup, expand=shot.height is None)
        if shot.focus is not None:
            shot.focus(capture_app).focus()
            await pilot.pause()
        capture_app.save_screenshot(filename=target.name, path=str(OUTPUT_DIR))
        if shot.clip is not None:
            result = shot.clip(capture_app)
            items = result if isinstance(result, list) else [result]
            clip_regions = [
                item if isinstance(item, Region) else item.region for item in items
            ]

    if clip_regions:
        _crop_svg_to_region(target, clip_regions, padding=shot.clip_padding)
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


def _make_select_with_overlay_setup(input_id: str) -> PilotSetup:
    """Setup that switches to the Output tab, focuses the select with the
    given id, and expands its dropdown overlay.

    Setting ``Select.expanded = True`` mounts the dropdown below the
    select. Subsequent ``pilot.pause()`` calls let layout settle so
    ``SelectOverlay.region`` returns a meaningful rect for clipping.
    """

    async def _setup(pilot: Any) -> None:
        pilot.app.query_one(TabbedContent).active = "output-tab"
        await pilot.pause()
        select = pilot.app.query_one(f"#{input_id}")
        select.focus()
        await pilot.pause()
        select.expanded = True
        await pilot.pause()

    return _setup


def _make_list_detail_field_setup(
    tab_setup: PilotSetup,
    pane_class: str,
    input_id: str,
) -> PilotSetup:
    """Setup that enters edit mode on a list-detail pane and focuses one field.

    Used for the detail-side fields of list-detail panes whose lists are
    pre-populated in the sample config (Layer roster, Layer Colours). The
    pane's ListView gets focus first, then ``Enter`` is pressed to enable
    the detail-side inputs; the requested input is then explicitly focused.
    """

    async def _setup(pilot: Any) -> None:
        await tab_setup(pilot)
        pane = pilot.app.query_one(pane_class)
        pane.query_one(".ldp-list").focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        widget = pilot.app.query_one(f"#{input_id}")
        if not getattr(widget, "disabled", False):
            widget.focus()
            await pilot.pause()

    return _setup


def _make_keycodes_detail_field_setup(
    pane_id: str,
    input_id: str,
) -> PilotSetup:
    """Setup that adds an entry to an empty keycodes list-detail pane.

    The sample config keeps the four keycodes lists empty, so there's no
    pre-existing entry to enter edit mode for. Pressing the pane's
    ``+ Add`` button creates a new entry with placeholder defaults and
    auto-enters edit mode; we then focus the requested detail-side input.
    """

    async def _setup(pilot: Any) -> None:
        await _switch_to_keycodes(pilot)
        pilot.app.query_one(f"#{pane_id}-add").press()
        await pilot.pause()
        widget = pilot.app.query_one(f"#{input_id}")
        if not getattr(widget, "disabled", False):
            widget.focus()
            await pilot.pause()

    return _setup


async def _setup_background_color_autocomplete(pilot: Any) -> None:
    """Switch to Output, drive the Background-color input until its
    autocomplete dropdown is visible.

    Focuses ``#palette-background-color``, sends backspaces to clear the
    pre-populated ``"white"`` value, then types ``"cyan"`` keystroke by
    keystroke so the AutoComplete widget receives ``Input.Changed`` events
    and shows its suggestion dropdown.
    """
    pilot.app.query_one(TabbedContent).active = "output-tab"
    await pilot.pause()
    color_input = pilot.app.query_one("#palette-background-color")
    color_input.focus()
    await pilot.pause()
    # Clear whatever was pre-populated by the sample config (and a few
    # extra in case the cursor isn't at the end).
    for _ in range(len(color_input.value) + 2):
        await pilot.press("backspace")
    await pilot.pause()
    for ch in "cyan":
        await pilot.press(ch)
    await pilot.pause()


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


def _make_select_with_overlay_clip(input_id: str) -> ClipTarget:
    """Clip target returning ``[field-row, SelectOverlay]`` for a Select.

    The crop helper takes the bounding box of both regions for the viewBox;
    the strip filter keeps only cells/texts inside one of the two regions,
    so the dead zone between (siblings of the field-row at the overlay's
    y-range, outside the overlay's x-range) is left blank rather than
    leaking adjacent labels / inputs.
    """

    def _resolver(app: SkimConfigApp) -> list[Any]:
        select = app.query_one(f"#{input_id}")
        return [select.parent, select.query_one(SelectOverlay)]

    return _resolver


def _background_color_with_autocomplete(app: SkimConfigApp) -> list[Any]:
    """Return ``[field-row, AutoComplete-popup]`` for the background-color shot.

    The AutoComplete widget is yielded as a sibling of the field-row (right
    after the row in the compose tree), targeting the row's ColorInput.
    Looking up the input by id and walking up to its parent gives the row;
    iterating ``ColorAutoComplete`` widgets and matching ``target`` finds
    the popup.
    """
    color_input = app.query_one("#palette-background-color")
    field_row = color_input.parent
    popup = next(
        ac
        for ac in app.query("ColorAutoComplete")
        if ac.target is color_input
    )
    return [field_row, popup]


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


def _make_simple_field_shot(
    help_key: str,
    tab_setup: PilotSetup,
    input_id: str,
    width: int,
    *,
    clip_padding: tuple[int, int, int, int] = (1, 3, 1, 3),
) -> Shot:
    """Build a Shot for a simple focused-state field row.

    The setup activates the field's tab, focuses the widget (if it isn't
    disabled), and pauses for layout to settle. Clip target is the
    field-row containing the widget; output filename is
    ``field-<help_key>``.
    """

    async def _setup(pilot: Any) -> None:
        await tab_setup(pilot)
        widget = pilot.app.query_one(f"#{input_id}")
        if not getattr(widget, "disabled", False):
            widget.focus()
            await pilot.pause()

    return Shot(
        f"field-{help_key}",
        _setup,
        width=width,
        clip=_field_row_for(input_id),
        clip_padding=clip_padding,
    )


def _make_list_pane_shot(
    help_key: str,
    tab_setup: PilotSetup,
    pane_selector: str,
    *,
    width: int = 95,
) -> Shot:
    """Build a Shot for a list-detail pane (the whole list + detail card)."""

    async def _setup(pilot: Any) -> None:
        await tab_setup(pilot)

    return Shot(
        f"field-{help_key}",
        _setup,
        width=width,
        clip=_widget(pane_selector),
        clip_padding=(1, 3, 1, 3),
    )


# Per-field specs for fields that follow the "switch tab → focus widget → clip
# to field-row" pattern. Each tuple is ``(help_key, tab_setup, input_id,
# width)``. Special-cased fields (with overlay, autocomplete, or in
# always-disabled detail panes) are defined explicitly below.
SIMPLE_FIELDS: list[tuple[str, PilotSetup, str, int]] = [
    # Keyboard → Info
    ("keyboard-info-title", _initial, "keymap-title-text", 50),
    ("keyboard-info-copyright", _initial, "copyright-text", 50),
    # Output → Page
    ("output-page-width", _switch_to_output, "layout-width", 50),
    ("output-page-margin", _switch_to_output, "layout-margin", 50),
    ("output-page-inset", _switch_to_output, "layout-inset", 50),
    ("output-page-border-enabled", _switch_to_output, "border-enabled", 35),
    ("output-page-border-width", _switch_to_output, "border-width", 50),
    ("output-page-border-radius", _switch_to_output, "border-radius", 50),
    # Output → Style
    ("output-style-use-system-fonts", _switch_to_output, "use-system-fonts", 40),
    ("output-style-use-layer-colors", _switch_to_output, "use-layer-colors", 45),
    ("output-style-show-layer-indicators", _switch_to_output, "show-layer-indicators", 45),
    ("output-style-show-layer-connectors", _switch_to_output, "show-layer-connectors", 45),
    ("output-style-show-transparent-fallthrough", _switch_to_output, "show-transparent-fallthrough", 50),
    ("output-style-show-special-keys-legend", _switch_to_output, "show-special-keys-legend", 50),
    ("output-style-show-symbol-legend", _switch_to_output, "show-symbol-legend", 45),
    # output-style-symbol-legend-flow is a Select — defined explicitly above
    # with the overlay open, matching the hold-symbol-position shot.
    # Output → Palette
    ("output-palette-background-color", _switch_to_output, "palette-background-color", 60),
    ("output-palette-text-color", _switch_to_output, "palette-text-color", 60),
    ("output-palette-border-color", _switch_to_output, "palette-border-color", 60),
    ("output-palette-neutral-color", _switch_to_output, "palette-neutral-color", 60),
    ("output-palette-key-label-color", _switch_to_output, "palette-key-label-color", 60),
    ("output-palette-macro-color", _switch_to_output, "palette-macro-color", 60),
    ("output-palette-tap-dance-color", _switch_to_output, "palette-tap-dance-color", 60),
]


SHOTS: list[Shot] = [
    # ---- Full Anatomy reference frame ----
    Shot("keyboard-tab", _initial, **ANATOMY_FRAME),
    Shot("keycodes-tab", _switch_to_keycodes),
    Shot("output-tab", _switch_to_output),
    Shot("output-style-tab", _switch_to_output_style),
    # ---- Anatomy crops (tab strip, scrolling area, status bar) ----
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
    # ---- Field shots with custom logic (overlay open, autocomplete shown,
    # list-detail panes, double-south on-state, etc.) ----
    Shot(
        # Double South switch flipped to the on-state for the screenshot.
        "field-keyboard-feature-double-south",
        _initial_double_south_on,
        width=35,
        clip=_widget("#features-row"),
        clip_padding=(1, 3, 1, 3),
        focus=_widget("#double-south"),
    ),
    Shot(
        # Hold Symbol Position select with the dropdown overlay expanded.
        "field-output-style-hold-symbol-position",
        _make_select_with_overlay_setup("hold-symbol-position"),
        width=60,
        clip=_make_select_with_overlay_clip("hold-symbol-position"),
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        # Symbol Legend Flow select with the dropdown overlay expanded.
        "field-output-style-symbol-legend-flow",
        _make_select_with_overlay_setup("symbol-legend-flow"),
        width=55,
        clip=_make_select_with_overlay_clip("symbol-legend-flow"),
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        # Background colour input with the autocomplete popup open after
        # typing ``"cyan"``. Used only as the "Colour input" example in
        # the Anatomy section — the Background-color field-reference
        # entry uses a plain shot generated from ``SIMPLE_FIELDS`` so it
        # matches the visual style of every other palette field.
        "anatomy-color-input",
        _setup_background_color_autocomplete,
        width=62,
        clip=_background_color_with_autocomplete,
        clip_padding=(1, 3, 1, 3),
    ),
    # ---- List-detail pane shots (the whole list + detail card) ----
    Shot(
        # Layer roster. Focus the ListView so the selected entry highlights;
        # the detail-side inputs stay disabled (they only enable in edit mode).
        "field-keyboard-layer-list",
        _initial,
        width=95,
        clip=_widget("LayerListPane"),
        clip_padding=(1, 3, 1, 3),
        focus=_widget("LayerListPane .ldp-list"),
    ),
    Shot(
        # Use ``skim-config.yaml`` (populated pre_process list) so the pane
        # renders real entries rather than the SvalCOLEMAK config's empty list.
        f"field-keycodes-pre-proc-list",
        _switch_to_keycodes,
        width=95,
        clip=_widget("PreProcessListPane"),
        clip_padding=(1, 3, 1, 3),
        config=SKIM_SAMPLE_CONFIG,
    ),
    Shot(
        f"field-keycodes-override-list",
        _switch_to_keycodes,
        width=95,
        clip=_widget("OverrideListPane"),
        clip_padding=(1, 3, 1, 3),
        config=SKIM_SAMPLE_CONFIG,
    ),
    Shot(
        # vial-sample.vil populates ``macro`` slots so the configurator
        # surfaces real entries instead of an empty list.
        "field-keycodes-macro-list",
        _switch_to_keycodes,
        width=95,
        clip=_widget("MacroListPane"),
        clip_padding=(1, 3, 1, 3),
        keymap=VIAL_SAMPLE_KEYMAP,
    ),
    Shot(
        "field-keycodes-tap-dance-list",
        _switch_to_keycodes,
        width=95,
        clip=_widget("TapDanceListPane"),
        clip_padding=(1, 3, 1, 3),
        keymap=VIAL_SAMPLE_KEYMAP,
    ),
    _make_list_pane_shot(
        "output-layer-color-list", _switch_to_output, "LayerColorListPane"
    ),
    # ---- List-detail children: focused-state shots of the per-entry editor
    # rows. Setup enters edit mode (or adds an entry for the empty
    # keycodes lists) and focuses the requested input.
    Shot(
        "field-keyboard-layer-index",
        _make_list_detail_field_setup(_initial, "LayerListPane", "layer-index"),
        width=80,
        clip=_field_row_for("layer-index"),
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        "field-keyboard-layer-id",
        _make_list_detail_field_setup(_initial, "LayerListPane", "layer-id"),
        width=80,
        clip=_field_row_for("layer-id"),
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        "field-keyboard-layer-name",
        _make_list_detail_field_setup(_initial, "LayerListPane", "layer-name"),
        width=80,
        clip=_field_row_for("layer-name"),
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        "field-keyboard-layer-variant",
        _make_list_detail_field_setup(_initial, "LayerListPane", "layer-variant"),
        width=80,
        clip=_field_row_for("layer-variant"),
        clip_padding=(1, 3, 1, 3),
    ),
    # Pre-process / Overrides per-field shots use the populated
    # ``skim-config.yaml`` so the editor can enter edit mode on an existing
    # entry (no need to ``+ Add`` and seed defaults).
    Shot(
        "field-keycodes-pre-proc-keycode",
        _make_list_detail_field_setup(_switch_to_keycodes, "PreProcessListPane", "pre-process-keycode"),
        width=80,
        clip=_field_row_for("pre-process-keycode"),
        clip_padding=(1, 3, 1, 3),
        config=SKIM_SAMPLE_CONFIG,
    ),
    Shot(
        "field-keycodes-pre-proc-target",
        _make_list_detail_field_setup(_switch_to_keycodes, "PreProcessListPane", "pre-process-target"),
        width=80,
        clip=_field_row_for("pre-process-target"),
        clip_padding=(1, 3, 1, 3),
        config=SKIM_SAMPLE_CONFIG,
    ),
    Shot(
        "field-keycodes-override-keycode",
        _make_list_detail_field_setup(_switch_to_keycodes, "OverrideListPane", "override-keycode"),
        width=80,
        clip=_field_row_for("override-keycode"),
        clip_padding=(1, 3, 1, 3),
        config=SKIM_SAMPLE_CONFIG,
    ),
    Shot(
        "field-keycodes-override-target",
        _make_list_detail_field_setup(_switch_to_keycodes, "OverrideListPane", "override-target"),
        width=80,
        clip=_field_row_for("override-target"),
        clip_padding=(1, 3, 1, 3),
        config=SKIM_SAMPLE_CONFIG,
    ),
    # Macros / Tap-dances per-field shots use the vial keymap so the
    # configurator can enter edit mode on a real entry rather than seeding
    # one with ``+ Add``.
    Shot(
        "field-keycodes-macro-id",
        _make_list_detail_field_setup(_switch_to_keycodes, "MacroListPane", "macro-id"),
        width=80,
        clip=_field_row_for("macro-id"),
        clip_padding=(1, 3, 1, 3),
        keymap=VIAL_SAMPLE_KEYMAP,
    ),
    Shot(
        "field-keycodes-macro-name",
        _make_list_detail_field_setup(_switch_to_keycodes, "MacroListPane", "macro-name"),
        width=80,
        clip=_field_row_for("macro-name"),
        clip_padding=(1, 3, 1, 3),
        keymap=VIAL_SAMPLE_KEYMAP,
    ),
    Shot(
        "field-keycodes-tap-dance-id",
        _make_list_detail_field_setup(_switch_to_keycodes, "TapDanceListPane", "tap-dance-id"),
        width=80,
        clip=_field_row_for("tap-dance-id"),
        clip_padding=(1, 3, 1, 3),
        keymap=VIAL_SAMPLE_KEYMAP,
    ),
    Shot(
        "field-keycodes-tap-dance-name",
        _make_list_detail_field_setup(_switch_to_keycodes, "TapDanceListPane", "tap-dance-name"),
        width=80,
        clip=_field_row_for("tap-dance-name"),
        clip_padding=(1, 3, 1, 3),
        keymap=VIAL_SAMPLE_KEYMAP,
    ),
    Shot(
        "field-output-layer-color-gradient-type",
        _make_list_detail_field_setup(_switch_to_output, "LayerColorListPane", "lc-gradient-type"),
        width=80,
        clip=_field_row_for("lc-gradient-type"),
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        "field-output-layer-color-color-index",
        _make_list_detail_field_setup(_switch_to_output, "LayerColorListPane", "lc-color-index"),
        width=80,
        clip=_field_row_for("lc-color-index"),
        clip_padding=(1, 3, 1, 3),
    ),
    Shot(
        # The lc-step-* rows only render when the LayerColorListPane is in
        # ``manual-mode`` — every layer in the sample config has an explicit
        # gradient list, so the pane initialises in manual-mode and the six
        # step inputs are visible. Clip to step 0 (the help text covers all
        # six side-by-side step inputs uniformly).
        "field-output-layer-color-step",
        _make_list_detail_field_setup(_switch_to_output, "LayerColorListPane", "lc-step-0"),
        width=80,
        clip=_field_row_for("lc-step-0"),
        clip_padding=(1, 3, 1, 3),
    ),
    # ---- Simple field shots (label + widget, focused state) ----
    *(_make_simple_field_shot(*spec) for spec in SIMPLE_FIELDS),
]


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config_cache: dict[Any, dict[str, Any]] = {}

    def _config_for(shot: Shot) -> dict[str, Any]:
        if shot.keymap is not None:
            key = ("keymap", shot.keymap)
            if key not in config_cache:
                config_cache[key] = _load_config_from_keymap(shot.keymap)
            return config_cache[key]
        path = shot.config or SAMPLE_CONFIG
        if path not in config_cache:
            config_cache[path] = _load_config(path)
        return config_cache[path]

    print(f"Generating {len(SHOTS)} screenshot(s); width and height per shot")
    for shot in SHOTS:
        target, height = await _capture(shot, _config_for(shot))
        size = target.stat().st_size
        print(f"  {target.relative_to(ROOT)} ({shot.width}x{height}, {size // 1024} KB)")


if __name__ == "__main__":
    asyncio.run(main())
