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

The file is split in two by a clear ``LEGACY OVERVIEW PATH`` marker. The
top half holds data utilities, the action-glyph builder and the shared
geometry that the composable framework still consumes; the bottom half
holds the imperative renderers the overview / per-layer image path
still needs. The bottom half retires once the overview migrates to
composables.
"""

from dataclasses import dataclass, field

import drawsvg as draw

from skim.data import SvalboardLayout
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


def _id_sort_key(id_: str) -> tuple[int, int | str]:
    """Numeric ids sort first (ascending), then named ids lex-ascending."""
    try:
        return (0, int(id_))
    except ValueError:
        return (1, id_)


def _named_first_sort_key(
    entry: SvalboardMacro[SvalboardTargetKey] | SvalboardTapDance[SvalboardTargetKey],
) -> tuple[int, int, int | str]:
    """Sort entries with a user-defined ``name`` first, then by id.

    Within each "named" / "unnamed" group, numeric ids precede named ids,
    and within each kind they sort ascending.
    """
    has_no_name = 0 if entry.name else 1
    id_kind, id_value = _id_sort_key(entry.id)
    return (has_no_name, id_kind, id_value)


def resolve_macros(
    used_ids: set[str],
    available: tuple[SvalboardMacro[SvalboardTargetKey], ...],
) -> list[SvalboardMacro[SvalboardTargetKey]]:
    """Filter ``available`` to ``used_ids`` and sort named entries first, then by id."""
    by_id = {m.id: m for m in available}
    return sorted(
        (by_id[i] for i in used_ids if i in by_id),
        key=_named_first_sort_key,
    )


def resolve_tap_dances(
    used_ids: set[str],
    available: tuple[SvalboardTapDance[SvalboardTargetKey], ...],
) -> list[SvalboardTapDance[SvalboardTargetKey]]:
    """Filter ``available`` to ``used_ids`` and sort named entries first, then by id."""
    by_id = {t.id: t for t in available}
    return sorted(
        (by_id[i] for i in used_ids if i in by_id),
        key=_named_first_sort_key,
    )


def all_macros(
    macros: tuple[SvalboardMacro[SvalboardTargetKey], ...],
) -> list[SvalboardMacro[SvalboardTargetKey]]:
    """Return all parsed macros sorted named-first, then by id (no filter)."""
    return sorted(macros, key=_named_first_sort_key)


def all_tap_dances(
    tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...],
) -> list[SvalboardTapDance[SvalboardTargetKey]]:
    """Return all parsed tap-dances sorted named-first, then by id (no filter)."""
    return sorted(tap_dances, key=_named_first_sort_key)


@dataclass(frozen=True, slots=True)
class LegendLayout:
    """Per-column row assignments for the legend block.

    When both sections are present, ``macro_left`` carries all macros and
    ``tap_dance_left`` carries all tap-dances. When only one type is
    present, the other type's left list is empty.
    """

    macro_left: list[SvalboardMacro[SvalboardTargetKey]] = field(default_factory=list)
    tap_dance_left: list[SvalboardTapDance[SvalboardTargetKey]] = field(default_factory=list)


def plan_layout(
    macros: list[SvalboardMacro[SvalboardTargetKey]],
    tap_dances: list[SvalboardTapDance[SvalboardTargetKey]],
) -> LegendLayout | None:
    """Decide how rows fill the legend.

    Returns ``None`` when both lists are empty (no legend block).
    Otherwise both types share the layout: each gets one column, with
    macros on the left and tap-dances on the right (right is empty if
    only macros, left is empty for the macro slot if only tap-dances).
    """
    if not macros and not tap_dances:
        return None
    return LegendLayout(
        macro_left=list(macros),
        tap_dance_left=list(tap_dances),
    )


def build_action_glyph(
    kind: SvalboardMacroActionKind,
    cx: float,
    cy: float,
    color: str,
    doc_width: float = 1600.0,
) -> draw.DrawingElement:
    """Return a tiny SVG primitive for the given action kind.

    - TAP   → filled circle (●).
    - DOWN  → filled down-triangle (▼) — "press".
    - UP    → filled up-triangle   (▲) — "release".
    - TEXT  → italic capital ``T``.
    - DELAY → small clock dial (circle + two hands).

    Glyph dimensions scale with ``doc_width`` so the legend stays visually
    consistent across output sizes. Reads its sizing constants directly
    from the ``_GLYPH_*_RATIO`` constants below — no consult of the
    legacy ``_LegendGeometry`` god-object — so the call site stays
    self-contained.
    """
    r = doc_width * _GLYPH_DOT_RADIUS_RATIO
    half = doc_width * _GLYPH_TRIANGLE_HALF_RATIO
    if kind == SvalboardMacroActionKind.TAP:
        return draw.Circle(cx=cx, cy=cy, r=r, fill=color)
    if kind == SvalboardMacroActionKind.DOWN:
        return draw.Lines(
            cx - half,
            cy - half,
            cx + half,
            cy - half,
            cx,
            cy + half,
            close=True,
            fill=color,
        )
    if kind == SvalboardMacroActionKind.UP:
        return draw.Lines(
            cx - half,
            cy + half,
            cx + half,
            cy + half,
            cx,
            cy - half,
            close=True,
            fill=color,
        )
    if kind == SvalboardMacroActionKind.DELAY:
        dial_r = doc_width * _GLYPH_DELAY_DIAL_RADIUS_RATIO
        stroke_w = doc_width * _GLYPH_DELAY_STROKE_RATIO
        hour_hand = doc_width * _GLYPH_DELAY_HOUR_HAND_RATIO
        minute_hand = doc_width * _GLYPH_DELAY_MINUTE_HAND_RATIO
        g = draw.Group()
        g.append(
            draw.Circle(
                cx=cx,
                cy=cy,
                r=dial_r,
                fill="none",
                stroke=color,
                stroke_width=stroke_w,
            )
        )
        # Clock hands at 12 o'clock + 3 o'clock.
        g.append(
            draw.Line(
                sx=cx,
                sy=cy,
                ex=cx,
                ey=cy - hour_hand,
                stroke=color,
                stroke_width=stroke_w,
                stroke_linecap="round",
            )
        )
        g.append(
            draw.Line(
                sx=cx,
                sy=cy,
                ex=cx + minute_hand,
                ey=cy,
                stroke=color,
                stroke_width=stroke_w,
                stroke_linecap="round",
            )
        )
        return g
    # TEXT
    return draw.Text(
        "T",
        x=cx,
        y=cy,
        font_size=doc_width * _GLYPH_TEXT_FONT_SIZE_RATIO,
        fill=color,
        font_weight="700",
        font_style="italic",
        text_anchor="middle",
        dominant_baseline="central",
        font_family="'Roboto', sans-serif",
    )


# Action-glyph primitives — coordinates inside ``build_action_glyph``.
# Lives here (above the LEGACY marker) because :func:`build_action_glyph`
# itself is still consumed by the active :func:`MacroPill` composable.
_GLYPH_DOT_RADIUS_RATIO = 3 / 1600
_GLYPH_TRIANGLE_HALF_RATIO = 3 / 1600
_GLYPH_DELAY_DIAL_RADIUS_RATIO = 3.5 / 1600
_GLYPH_DELAY_HOUR_HAND_RATIO = 2.2 / 1600
_GLYPH_DELAY_MINUTE_HAND_RATIO = 1.6 / 1600
_GLYPH_DELAY_STROKE_RATIO = 1.1 / 1600
_GLYPH_TEXT_FONT_SIZE_RATIO = 9 / 1600


def _one_line(text: str) -> str:
    """Collapse newlines to spaces so legend pills/cells stay single-line.

    Multi-line key labels (and macro text actions) work fine on the
    keymap proper but break legend rendering — the chip/cell is sized
    for one line of text and additional lines spill outside the rounded
    rect. The legend treats labels as inline strings.
    """
    return text.replace("\n", " ")


def _legend_key_label(key: SvalboardTargetKey) -> str:
    """Return the label string to display for ``key`` in the legend.

    For layer-only functions (``MO(N)``, ``TO(N)``, ``TG(N)`` …), the
    resolved label is just the layer glyph — ambiguous on its own. We
    append the target layer number so the reader can tell which layer is
    being switched to. Compound functions (``LT(N, KC_A)``, ``LM(N,
    mods)``) already embed the layer digit alongside the tap key via the
    ``|`` separator, so they pass through unchanged.

    Newlines are collapsed to spaces — see :func:`_one_line`.
    """
    label = _one_line(key.label)
    if key.layer_switch is not None and SEPARATOR_CHAR not in label:
        return f"{label} {key.layer_switch}"
    return label


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
        return [_one_line(action.text)]
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
