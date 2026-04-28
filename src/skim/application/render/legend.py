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
from skim.domain import SvalboardMacro, SvalboardMacroActionKind, SvalboardTapDance
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
