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

from skim.data import SvalboardLayout
from skim.domain import (
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardMacroActionKind,
    SvalboardTapDance,
)
from skim.domain.domain_types import SvalboardTargetKey


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
TAG_W = 48
TAG_H = 22
HEADER_STRIP_HEIGHT = 28
CONTENT_STRIP_HEIGHT = 28
ROW_GAP = 18
PILL_GAP = 6
PILL_HEIGHT = 24
PILL_FONT_SIZE = 11


def _pill_width(label: str) -> float:
    """Approximate the pill width given its visible label.

    Mirrors the JSX rule: ``v.length > 3 ? max(110, len*7 + 28) : 50``. We
    accept a small margin of error — the rendered text is short enough
    that the approximation never causes wrapping problems in practice.
    """
    if len(label) > 3:
        return max(110.0, len(label) * 7.0 + 28.0)
    return 50.0


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
        return [k.label for k in action.keys]
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
) -> draw.Group:
    """Render a single macro row at ``(x, y)``."""
    g = draw.Group()
    # Header strip — tag chip + name + rule.
    g.append(draw.Rectangle(
        x=x, y=y, width=TAG_W, height=TAG_H, rx=4, ry=4,
        fill=accent_fill, stroke=accent_line, stroke_width=1.2,
    ))
    g.append(draw.Text(
        f"M{macro.id}", x=x + TAG_W / 2, y=y + TAG_H / 2 + 0.5,
        font_size=12, font_weight="700", text_anchor="middle",
        dominant_baseline="central", font_family="'Roboto', sans-serif",
        fill="#FFF",
    ))
    name = macro.name if macro.name else f"Macro {macro.id}"
    g.append(draw.Text(
        name, x=x + TAG_W + 10, y=y + TAG_H / 2 + 0.5,
        font_size=13, font_weight="500", dominant_baseline="central",
        font_family="'Roboto', sans-serif", fill=text_color,
    ))
    g.append(draw.Line(
        sx=x + TAG_W, sy=y + TAG_H - 0.5,
        ex=x + content_width, ey=y + TAG_H - 0.5,
        stroke=accent_line, stroke_opacity=0.55, stroke_width=1,
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
            # Action glyph at left
            g.append(build_action_glyph(
                kind, cx=cx + 9, cy=line_y + CONTENT_STRIP_HEIGHT / 2, color=text_color,
            ))
            # Label
            g.append(draw.Text(
                label, x=cx + (w + 14) / 2 + 4,
                y=line_y + CONTENT_STRIP_HEIGHT / 2 + 0.5,
                font_size=PILL_FONT_SIZE, fill=text_color,
                text_anchor="middle", dominant_baseline="central",
                font_family="'Roboto', sans-serif",
            ))
            cx += w + PILL_GAP
        line_y += CONTENT_STRIP_HEIGHT
    return g
