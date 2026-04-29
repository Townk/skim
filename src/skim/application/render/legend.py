# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Per-layer macro / tap-dance legend rendering.

Walks a layer's keys to collect the macro and tap-dance ids actually in
use, looks the definitions up in the parsed keymap, and lays out a
two-column legend below the keyboard. Both sections render side-by-side
when both are non-empty; a single section spans both columns and balances
its rows when only one type is in use.

Geometry mirrors ``docs/design/layer.jsx::Legend``.
"""

import math
from dataclasses import dataclass, field

import drawsvg as draw

from skim.application.render.styling import derive_accent_line
from skim.application.render.text import Font, Label
from skim.data import Palette, SvalboardLayout
from skim.domain import (
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardMacroActionKind,
    SvalboardTapDance,
)
from skim.domain.domain_types import SEPARATOR_CHAR, SvalboardTargetKey


def collect_used_ids(
    layer: SvalboardLayout[SvalboardTargetKey],
) -> tuple[set[str], set[str]]:
    """Return ``(macro_ids, tap_dance_ids)`` referenced anywhere on ``layer``.

    Transparent fallthroughs already carry the inherited ids (handled by
    :func:`KeymapTargetAdapter._substitute`), so a single pass over every
    key is enough.
    """
    macros: set[str] = set()
    tap_dances: set[str] = set()
    for key in layer:
        if key is None:
            continue
        if key.macro_id is not None:
            macros.add(key.macro_id)
        if key.tap_dance_id is not None:
            tap_dances.add(key.tap_dance_id)
    return macros, tap_dances


def _sort_key(id_: str) -> tuple[int, int | str]:
    """Numeric ids sort first (ascending) then named ids lex-ascending."""
    try:
        return (0, int(id_))
    except ValueError:
        return (1, id_)


def resolve_macros(
    used_ids: set[str],
    available: tuple[SvalboardMacro[SvalboardTargetKey], ...],
) -> list[SvalboardMacro[SvalboardTargetKey]]:
    """Filter ``available`` to ``used_ids`` and sort by id."""
    by_id = {m.id: m for m in available}
    return sorted(
        (by_id[i] for i in used_ids if i in by_id),
        key=lambda m: _sort_key(m.id),
    )


def resolve_tap_dances(
    used_ids: set[str],
    available: tuple[SvalboardTapDance[SvalboardTargetKey], ...],
) -> list[SvalboardTapDance[SvalboardTargetKey]]:
    """Filter ``available`` to ``used_ids`` and sort by id."""
    by_id = {t.id: t for t in available}
    return sorted(
        (by_id[i] for i in used_ids if i in by_id),
        key=lambda t: _sort_key(t.id),
    )


def all_macros(
    macros: tuple[SvalboardMacro[SvalboardTargetKey], ...]
) -> list[SvalboardMacro[SvalboardTargetKey]]:
    """Return all parsed macros sorted by id (no filter)."""
    return sorted(macros, key=lambda m: _sort_key(m.id))


def all_tap_dances(
    tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...]
) -> list[SvalboardTapDance[SvalboardTargetKey]]:
    """Return all parsed tap-dances sorted by id (no filter)."""
    return sorted(tap_dances, key=lambda t: _sort_key(t.id))


@dataclass(frozen=True, slots=True)
class LegendLayout:
    """Per-column row assignments for the legend block.

    When both sections are present, ``macro_left`` carries all macros and
    ``tap_dance_left`` carries all tap-dances; ``*_right`` are empty. When
    only one type is present, that section's rows are split across two
    balanced columns and the corresponding ``*_span_columns`` flag is True.
    """

    macro_left: list[SvalboardMacro[SvalboardTargetKey]] = field(default_factory=list)
    macro_right: list[SvalboardMacro[SvalboardTargetKey]] = field(default_factory=list)
    tap_dance_left: list[SvalboardTapDance[SvalboardTargetKey]] = field(default_factory=list)
    tap_dance_right: list[SvalboardTapDance[SvalboardTargetKey]] = field(default_factory=list)
    macros_span_columns: bool = False
    tap_dances_span_columns: bool = False


def plan_layout(
    macros: list[SvalboardMacro[SvalboardTargetKey]],
    tap_dances: list[SvalboardTapDance[SvalboardTargetKey]],
) -> LegendLayout | None:
    """Decide how rows fill the two-column legend.

    Returns ``None`` when both lists are empty (no legend block).
    """
    if not macros and not tap_dances:
        return None

    if macros and tap_dances:
        return LegendLayout(
            macro_left=list(macros),
            tap_dance_left=list(tap_dances),
        )

    if macros:
        # Single-type → balance across two columns.
        half = math.ceil(len(macros) / 2)
        return LegendLayout(
            macro_left=macros[:half],
            macro_right=macros[half:],
            macros_span_columns=True,
        )

    half = math.ceil(len(tap_dances) / 2)
    return LegendLayout(
        tap_dance_left=tap_dances[:half],
        tap_dance_right=tap_dances[half:],
        tap_dances_span_columns=True,
    )


def build_action_glyph(
    kind: SvalboardMacroActionKind, cx: float, cy: float, color: str
) -> draw.DrawingElement:
    """Return a tiny SVG primitive for the given action kind.

    - TAP   → filled circle (●).
    - DOWN  → filled down-triangle (▼) — "press".
    - UP    → filled up-triangle   (▲) — "release".
    - TEXT  → italic capital ``T``.
    - DELAY → small clock dial (circle + two hands).
    """
    if kind == SvalboardMacroActionKind.TAP:
        return draw.Circle(cx=cx, cy=cy, r=3, fill=color)
    if kind == SvalboardMacroActionKind.DOWN:
        return draw.Lines(
            cx - 3, cy - 3,
            cx + 3, cy - 3,
            cx,     cy + 3,
            close=True, fill=color,
        )
    if kind == SvalboardMacroActionKind.UP:
        return draw.Lines(
            cx - 3, cy + 3,
            cx + 3, cy + 3,
            cx,     cy - 3,
            close=True, fill=color,
        )
    if kind == SvalboardMacroActionKind.DELAY:
        g = draw.Group()
        g.append(draw.Circle(cx=cx, cy=cy, r=3.5, fill="none",
                             stroke=color, stroke_width=1.1))
        # Clock hands at 12 o'clock + 3 o'clock.
        g.append(draw.Line(sx=cx, sy=cy, ex=cx, ey=cy - 2.2,
                           stroke=color, stroke_width=1.1, stroke_linecap="round"))
        g.append(draw.Line(sx=cx, sy=cy, ex=cx + 1.6, ey=cy,
                           stroke=color, stroke_width=1.1, stroke_linecap="round"))
        return g
    # TEXT
    return draw.Text(
        "T", x=cx, y=cy, font_size=9, fill=color, font_weight="700",
        font_style="italic", text_anchor="middle", dominant_baseline="central",
        font_family="'Roboto', sans-serif",
    )


# --- Geometry constants (mirrors docs/design/layer.jsx Legend) -------------
TAG_W = 56
TAG_H = 22
HEADER_STRIP_HEIGHT = 28
CONTENT_STRIP_HEIGHT = 22
ROW_GAP = 18
PILL_GAP = 6
PILL_HEIGHT = 18
PILL_FONT_SIZE = 10

PILL_PAD_X = 8                # horizontal padding inside each pill
ICON_WIDTH = 6                # visual width of action glyphs (circle r=3, etc.)
ICON_TEXT_GAP = 10            # gap from icon's right edge to text's left edge
                              # (≤ 1.5 × PILL_PAD_X = 12)
PILL_CHROME_WIDTH = 2 * PILL_PAD_X + ICON_WIDTH + ICON_TEXT_GAP  # = 32


def _legend_key_label(key: SvalboardTargetKey) -> str:
    """Return the label string to display for ``key`` in the legend.

    For layer-only functions (``MO(N)``, ``TO(N)``, ``TG(N)`` …), the
    resolved label is just the layer glyph — ambiguous on its own. We
    append the target layer number so the reader can tell which layer is
    being switched to. Compound functions (``LT(N, KC_A)``, ``LM(N,
    mods)``) already embed the layer digit alongside the tap key via the
    ``|`` separator, so they pass through unchanged.
    """
    label = key.label
    if key.layer_switch is not None and SEPARATOR_CHAR not in label:
        return f"{label} {key.layer_switch}"
    return label


def _pill_width(label: str) -> float:
    """Compute the pill width to wrap ``label`` exactly.

    Uses :meth:`Label.measure_width` (PIL-based actual font metrics) so
    each pill is sized to its rendered glyph width, not the alias-string
    length.
    """
    text_width = Label(label, Font.FINGER_KEY, text_color="#000").measure_width(PILL_FONT_SIZE)
    text_width = max(text_width, 8.0)
    return max(28.0, text_width + PILL_CHROME_WIDTH)


def _macro_action_pill_labels(action: SvalboardMacroAction) -> list[str]:
    """Visible label per pill emitted by an action.

    TAP/DOWN/UP emit one pill per key in ``action.keys``. TEXT emits one
    pill with the literal text. DELAY emits one pill with ``"<duration>ms"``.
    """
    if action.kind in (
        SvalboardMacroActionKind.TAP,
        SvalboardMacroActionKind.DOWN,
        SvalboardMacroActionKind.UP,
    ):
        return [_legend_key_label(k) for k in action.keys]
    if action.kind == SvalboardMacroActionKind.TEXT:
        return [action.text]
    if action.kind == SvalboardMacroActionKind.DELAY:
        return [f"{action.duration_ms}ms"]
    return []


def _flatten_macro_pills(
    macro: SvalboardMacro[SvalboardTargetKey],
) -> list[tuple[SvalboardMacroActionKind, str]]:
    """Pre-flatten ``macro.actions`` into a (kind, label) sequence."""
    out: list[tuple[SvalboardMacroActionKind, str]] = []
    for action in macro.actions:
        for label in _macro_action_pill_labels(action):
            out.append((action.kind, label))
    return out


def _layout_pill_lines(
    pills: list[tuple[SvalboardMacroActionKind, str]],
    line_width: float,
) -> list[list[tuple[SvalboardMacroActionKind, str, float]]]:
    """Pack pills into lines, wrapping when the next pill would overflow.

    Returns a list of lines, each a list of ``(kind, label, width)``.
    """
    lines: list[list[tuple[SvalboardMacroActionKind, str, float]]] = [[]]
    cursor = 0.0
    for kind, label in pills:
        w = _pill_width(label)
        if lines[-1] and cursor + PILL_GAP + w > line_width:
            lines.append([])
            cursor = 0.0
        if lines[-1]:
            cursor += PILL_GAP
        lines[-1].append((kind, label, w))
        cursor += w
    return lines


def macro_row_height(
    macro: SvalboardMacro[SvalboardTargetKey], content_width: float
) -> float:
    """Total height of one macro row (header + content lines)."""
    pills = _flatten_macro_pills(macro)
    indent = TAG_W + 12
    lines = _layout_pill_lines(pills, content_width - indent)
    return HEADER_STRIP_HEIGHT + CONTENT_STRIP_HEIGHT * max(1, len(lines))


def build_macro_row(
    macro: SvalboardMacro[SvalboardTargetKey],
    x: float,
    y: float,
    content_width: float,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    use_system_fonts: bool = False,
) -> draw.Group:
    """Render a single macro row at ``(x, y)``."""
    g = draw.Group()
    # Header strip — tag chip + name + rule.
    g.append(draw.Rectangle(
        x=x, y=y, width=TAG_W, height=TAG_H, rx=4, ry=4,
        fill=accent_fill, stroke=accent_line, stroke_width=1.2,
    ))
    chip_label_text = f"%%nf-md-script_text_play_outline; {macro.id}"
    g.append(
        Label(
            chip_label_text,
            Font.FINGER_KEY,
            text_color="#FFF",
            background_color=accent_fill,
            text_anchor="middle",
            dominant_baseline="central",
        ).build_text(
            x + TAG_W / 2,
            y + TAG_H / 2 + 0.5,
            12,
            use_system_fonts,
        )
    )
    name = macro.name if macro.name else f"Macro {macro.id}"
    g.append(draw.Text(
        name, x=x + TAG_W + 10, y=y + TAG_H / 2 + 0.5,
        font_size=13, font_weight="500", dominant_baseline="central",
        font_family="'Roboto', sans-serif", fill=text_color,
    ))
    g.append(draw.Line(
        sx=x + TAG_W, sy=y + TAG_H - 0.5,
        ex=x + content_width, ey=y + TAG_H - 0.5,
        stroke="#000", stroke_opacity=0.08, stroke_width=1,
    ))

    # Content strip — pills with overflow wrap.
    pills = _flatten_macro_pills(macro)
    indent = TAG_W + 12
    lines = _layout_pill_lines(pills, content_width - indent)
    line_y = y + HEADER_STRIP_HEIGHT
    for line in lines:
        cx = x + indent
        for kind, label, w in line:
            # Pill background
            g.append(draw.Rectangle(
                x=cx, y=line_y + (CONTENT_STRIP_HEIGHT - PILL_HEIGHT) / 2,
                width=w, height=PILL_HEIGHT, rx=4, ry=4,
                fill="#FAFAF6", stroke=text_color, stroke_opacity=0.18,
            ))
            # Action glyph — icon centred at cx + PILL_PAD_X (so left padding
            # from pill edge to icon centre = PILL_PAD_X).
            g.append(build_action_glyph(
                kind, cx=cx + PILL_PAD_X, cy=line_y + CONTENT_STRIP_HEIGHT / 2,
                color=text_color,
            ))
            # Label — symmetric around the available text region.
            #   Text region: [cx + PILL_PAD_X + ICON_WIDTH/2 + ICON_TEXT_GAP, cx + w - PILL_PAD_X]
            #   Text region centre: cx + (PILL_PAD_X + ICON_WIDTH/2 + ICON_TEXT_GAP + w - PILL_PAD_X) / 2
            #                     = cx + (ICON_WIDTH/2 + ICON_TEXT_GAP + w) / 2
            text_centre_x = cx + (ICON_WIDTH / 2 + ICON_TEXT_GAP + w) / 2
            g.append(
                Label(
                    label,
                    Font.FINGER_KEY,
                    text_color=text_color,
                    background_color="#FAFAF6",
                    text_anchor="middle",
                    dominant_baseline="central",
                ).build_text(
                    text_centre_x,
                    line_y + CONTENT_STRIP_HEIGHT / 2 + 0.5,
                    PILL_FONT_SIZE,
                    use_system_fonts,
                )
            )
            cx += w + PILL_GAP
        line_y += CONTENT_STRIP_HEIGHT
    return g


# --- Tap-dance geometry constants -------------------------------------------
TD_ROW_HEIGHT = 22
TD_ROW_GAP = 16
TD_HEADER_HEIGHT = 32  # space reserved for the "TAP HOLD DOUBLE-TAP …" labels
TD_NAME_W = 200
TD_CELL_W = 110


def tap_dance_section_height(
    tap_dances: list[SvalboardTapDance[SvalboardTargetKey]],
) -> float:
    """Height of a tap-dance section (column header strip + rows).

    Returns 0 for an empty list so the legend's column-balanced height
    math does not overstate when only one column is populated.
    """
    if not tap_dances:
        return 0.0
    return TD_HEADER_HEIGHT + len(tap_dances) * (TD_ROW_HEIGHT + TD_ROW_GAP)


def _tap_dance_cell(
    x: float, y: float, content: SvalboardTargetKey | None,
    text_color: str,
    use_system_fonts: bool = False,
) -> draw.Group:
    """Render one of the four variant cells (TAP, HOLD, DOUBLE-TAP, TAP&HOLD).

    ``y`` is the vertical centre of the cell. An empty (``None``) cell
    renders as a dashed placeholder rect.
    """
    g = draw.Group()
    if content is None:
        g.append(draw.Rectangle(
            x=x, y=y - 11, width=80, height=22, rx=4, ry=4, fill="none",
            stroke=text_color, stroke_opacity=0.08, stroke_dasharray="3 3",
        ))
        return g
    g.append(draw.Rectangle(
        x=x, y=y - 11, width=80, height=22, rx=4, ry=4,
        fill="#FAFAF6", stroke=text_color, stroke_opacity=0.18,
    ))
    cell_label = Label(
        _legend_key_label(content),
        font=Font.FINGER_KEY,
        text_color=text_color,
        text_anchor="middle",
        dominant_baseline="central",
    )
    g.append(cell_label.build_text(
        x=x + 40, y=y + 0.5,
        font_size=12,
        use_system_fonts=use_system_fonts,
    ))
    return g


def build_tap_dance_row(
    td: SvalboardTapDance[SvalboardTargetKey],
    x: float,
    y: float,
    column_width: float,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    use_system_fonts: bool = False,
) -> draw.Group:
    """Render a single tap-dance row at ``(x, y)``.

    ``y`` is the vertical centre of the row.
    """
    g = draw.Group()
    # Title chip — left half accent fill, full chip outlined.
    g.append(draw.Rectangle(
        x=x, y=y - TD_ROW_HEIGHT / 2, width=TAG_W, height=TD_ROW_HEIGHT,
        fill=accent_fill,
    ))
    g.append(draw.Rectangle(
        x=x, y=y - TD_ROW_HEIGHT / 2, width=TD_NAME_W, height=TD_ROW_HEIGHT,
        rx=4, ry=4, fill="none", stroke=accent_line, stroke_width=1.2,
    ))
    td_chip_label_text = f"%%nf-md-keyboard_close; {td.id}"
    g.append(
        Label(
            td_chip_label_text,
            Font.FINGER_KEY,
            text_color="#FFF",
            background_color=accent_fill,
            text_anchor="middle",
            dominant_baseline="central",
        ).build_text(
            x + TAG_W / 2,
            y + 0.5,
            12,
            use_system_fonts,
        )
    )
    name = td.name if td.name else f"Tap-Dance {td.id}"
    g.append(draw.Text(
        name, x=x + TAG_W + 10, y=y + 0.5, font_size=12, font_weight="500",
        text_anchor="start", dominant_baseline="central",
        font_family="'Roboto', sans-serif", fill=text_color,
    ))
    # Four variant cells.
    cells_x = x + TD_NAME_W + 12
    for i, variant in enumerate((td.tap, td.hold, td.double_tap, td.tap_then_hold)):
        cell_x = cells_x + i * TD_CELL_W + TD_CELL_W / 2 - 40
        g.append(_tap_dance_cell(cell_x, y, variant, text_color, use_system_fonts))
    return g


def build_tap_dance_column_header(
    x: float, y: float, text_color: str
) -> draw.Group:
    """Render the once-per-column TAP/HOLD/DOUBLE-TAP/TAP&HOLD strip."""
    g = draw.Group()
    cells_x = x + TD_NAME_W + 12
    for i, label in enumerate(("TAP", "HOLD", "DOUBLE-TAP", "TAP & HOLD")):
        g.append(draw.Text(
            label, x=cells_x + i * TD_CELL_W + TD_CELL_W / 2,
            y=y, font_size=9, fill=text_color, letter_spacing=1.5,
            text_anchor="middle", font_family="'Roboto', sans-serif",
        ))
    return g


# --- Top-level legend renderer -----------------------------------------------
SECTION_HEADER_HEIGHT = 32
COLUMN_GAP = 40
ACTION_KEY_STRIP_HEIGHT = 22


def _column_widths(content_width: float) -> tuple[float, float]:
    col = (content_width - COLUMN_GAP) / 2
    return col, col


def _macro_section_height(
    rows: list[SvalboardMacro[SvalboardTargetKey]], col_width: float
) -> float:
    """Height of a macro section: title strip + rows + action-key footer.

    Returns 0 when ``rows`` is empty (no section to render).
    """
    if not rows:
        return 0.0
    h = SECTION_HEADER_HEIGHT
    for r in rows:
        h += macro_row_height(r, col_width) + ROW_GAP
    h += ACTION_KEY_STRIP_HEIGHT
    return h


def legend_height(layout: LegendLayout | None, content_width: float) -> float:
    """Total intrinsic height of the legend block.

    Returns 0 when ``layout is None`` (no specials on this layer).
    """
    if layout is None:
        return 0.0
    col_w, _ = _column_widths(content_width)
    if layout.macros_span_columns:
        h_left = _macro_section_height(layout.macro_left, col_w)
        h_right = (
            _macro_section_height(layout.macro_right, col_w)
            if layout.macro_right
            else 0.0
        )
        # Title is shared (one strip above both columns); both column
        # totals already include SECTION_HEADER_HEIGHT, so subtract one
        # and add it back at the top.
        inner_left = max(h_left - SECTION_HEADER_HEIGHT, 0.0)
        inner_right = max(h_right - SECTION_HEADER_HEIGHT, 0.0) if h_right else 0.0
        return SECTION_HEADER_HEIGHT + max(inner_left, inner_right)
    if layout.tap_dances_span_columns:
        h_left = tap_dance_section_height(layout.tap_dance_left)
        h_right = (
            tap_dance_section_height(layout.tap_dance_right)
            if layout.tap_dance_right
            else 0.0
        )
        return SECTION_HEADER_HEIGHT + max(h_left, h_right)
    # Both present — independent columns.
    h_macros = _macro_section_height(layout.macro_left, col_w)
    h_tds = SECTION_HEADER_HEIGHT + tap_dance_section_height(layout.tap_dance_left)
    return max(h_macros, h_tds)


def _draw_macro_title(
    g: draw.Group, x: float, y: float, width: float, accent_line: str, count: int,
) -> None:
    g.append(draw.Text(
        "MACROS", x=x, y=y + 12, font_size=11, font_weight="700",
        letter_spacing=3, text_anchor="start",
        font_family="'Roboto', sans-serif", fill=accent_line,
    ))
    g.append(draw.Text(
        f"{count} ENTRIES", x=x + width, y=y + 12, font_size=10,
        text_anchor="end", fill="#888", font_weight="400", letter_spacing=1,
        font_family="'Roboto', sans-serif",
    ))
    g.append(draw.Line(
        sx=x, sy=y + 20, ex=x + width, ey=y + 20,
        stroke=accent_line, stroke_opacity=0.5, stroke_width=1.2,
    ))


def _draw_td_title(
    g: draw.Group, x: float, y: float, width: float, accent_line: str, count: int,
) -> None:
    g.append(draw.Text(
        "TAP-DANCE", x=x, y=y + 12, font_size=11, font_weight="700",
        letter_spacing=3, text_anchor="start",
        font_family="'Roboto', sans-serif", fill=accent_line,
    ))
    g.append(draw.Text(
        f"{count} ENTRIES", x=x + width, y=y + 12, font_size=10,
        text_anchor="end", fill="#888", font_weight="400", letter_spacing=1,
        font_family="'Roboto', sans-serif",
    ))
    g.append(draw.Line(
        sx=x, sy=y + 20, ex=x + width, ey=y + 20,
        stroke=accent_line, stroke_opacity=0.5, stroke_width=1.2,
    ))


def _action_key_strip(x: float, y: float, text_color: str) -> draw.Group:
    """The 'tap | press | release | text | delay' key below macros."""
    g = draw.Group()
    g.append(draw.Text(
        "ACTION KEY", x=x, y=y + 6, font_size=9, fill="#999", letter_spacing=1.5,
        dominant_baseline="central", font_family="'Roboto', sans-serif",
    ))
    cx = x + 90
    items = [
        (SvalboardMacroActionKind.TAP, "tap"),
        (SvalboardMacroActionKind.DOWN, "press"),
        (SvalboardMacroActionKind.UP, "release"),
        (SvalboardMacroActionKind.TEXT, "text"),
        (SvalboardMacroActionKind.DELAY, "delay"),
    ]
    for kind, label in items:
        g.append(build_action_glyph(kind, cx=cx + 6, cy=y + 6, color=text_color))
        g.append(draw.Text(
            label, x=cx + 16, y=y + 6, font_size=10, fill="#666",
            dominant_baseline="central", font_family="'Roboto', sans-serif",
        ))
        cx += 14 + len(label) * 6 + 14
    return g


def _draw_macro_column(
    g: draw.Group,
    rows: list[SvalboardMacro[SvalboardTargetKey]],
    col_x: float,
    start_y: float,
    col_w: float,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    use_system_fonts: bool = False,
) -> float:
    """Stamp ``rows`` into one column starting at ``start_y``.

    Returns the y position immediately after the last row (no action-key
    footer applied here — the caller emits a single shared footer).
    """
    cursor = start_y
    for m in rows:
        g.append(build_macro_row(
            m, x=col_x, y=cursor, content_width=col_w,
            accent_fill=accent_fill, accent_line=accent_line,
            text_color=text_color, use_system_fonts=use_system_fonts,
        ))
        cursor += macro_row_height(m, col_w) + ROW_GAP
    return cursor


def _draw_td_column(
    g: draw.Group,
    rows: list[SvalboardTapDance[SvalboardTargetKey]],
    col_x: float,
    start_y: float,
    col_w: float,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    use_system_fonts: bool = False,
) -> None:
    g.append(build_tap_dance_column_header(
        x=col_x, y=start_y + 12, text_color=text_color,
    ))
    cursor = start_y + TD_HEADER_HEIGHT
    for t in rows:
        g.append(build_tap_dance_row(
            t, x=col_x, y=cursor + TD_ROW_HEIGHT / 2,
            column_width=col_w,
            accent_fill=accent_fill, accent_line=accent_line,
            text_color=text_color, use_system_fonts=use_system_fonts,
        ))
        cursor += TD_ROW_HEIGHT + TD_ROW_GAP


def build_legend(
    layout: LegendLayout | None,
    x: float,
    y: float,
    content_width: float,
    palette: Palette,
    use_system_fonts: bool = False,
) -> draw.Group | None:
    """Render the full legend block at ``(x, y)``.

    Returns ``None`` when ``layout`` is ``None`` (no specials on the layer).
    """
    if layout is None:
        return None
    macro_line = derive_accent_line(palette.macro_color)
    td_line = derive_accent_line(palette.tap_dance_color)
    col_w, _ = _column_widths(content_width)
    g = draw.Group()

    if layout.macros_span_columns:
        _draw_macro_title(
            g, x, y, content_width, macro_line,
            count=len(layout.macro_left) + len(layout.macro_right),
        )
        rows_top = y + SECTION_HEADER_HEIGHT
        end_left = _draw_macro_column(
            g, layout.macro_left, x, rows_top, col_w,
            palette.macro_color, macro_line, palette.text_color,
            use_system_fonts=use_system_fonts,
        )
        end_right = _draw_macro_column(
            g, layout.macro_right, x + col_w + COLUMN_GAP, rows_top, col_w,
            palette.macro_color, macro_line, palette.text_color,
            use_system_fonts=use_system_fonts,
        )
        g.append(_action_key_strip(
            x=x, y=max(end_left, end_right), text_color=palette.text_color,
        ))
        return g

    if layout.tap_dances_span_columns:
        _draw_td_title(
            g, x, y, content_width, td_line,
            count=len(layout.tap_dance_left) + len(layout.tap_dance_right),
        )
        rows_top = y + SECTION_HEADER_HEIGHT
        _draw_td_column(
            g, layout.tap_dance_left, x, rows_top, col_w,
            palette.tap_dance_color, td_line, palette.text_color,
            use_system_fonts=use_system_fonts,
        )
        if layout.tap_dance_right:
            _draw_td_column(
                g, layout.tap_dance_right, x + col_w + COLUMN_GAP, rows_top, col_w,
                palette.tap_dance_color, td_line, palette.text_color,
                use_system_fonts=use_system_fonts,
            )
        return g

    # Both present — independent columns.
    _draw_macro_title(
        g, x, y, col_w, macro_line, count=len(layout.macro_left),
    )
    end_left = _draw_macro_column(
        g, layout.macro_left, x, y + SECTION_HEADER_HEIGHT, col_w,
        palette.macro_color, macro_line, palette.text_color,
        use_system_fonts=use_system_fonts,
    )
    g.append(_action_key_strip(x=x, y=end_left, text_color=palette.text_color))

    _draw_td_title(
        g, x + col_w + COLUMN_GAP, y, col_w, td_line,
        count=len(layout.tap_dance_left),
    )
    _draw_td_column(
        g, layout.tap_dance_left, x + col_w + COLUMN_GAP,
        y + SECTION_HEADER_HEIGHT, col_w,
        palette.tap_dance_color, td_line, palette.text_color,
        use_system_fonts=use_system_fonts,
    )
    return g
