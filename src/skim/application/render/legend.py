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

from dataclasses import dataclass, field

import drawsvg as draw

from skim.application.render.composable import Point
from skim.application.render.styling import derive_accent_line
from skim.application.render.text import Font, Label, TextPart
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
    consistent across output sizes.
    """
    geom = _LegendGeometry.for_doc_width(doc_width)
    r = geom.glyph_dot_radius
    half = geom.glyph_triangle_half
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
        g = draw.Group()
        g.append(
            draw.Circle(
                cx=cx,
                cy=cy,
                r=geom.glyph_delay_dial_radius,
                fill="none",
                stroke=color,
                stroke_width=geom.glyph_delay_stroke,
            )
        )
        # Clock hands at 12 o'clock + 3 o'clock.
        g.append(
            draw.Line(
                sx=cx,
                sy=cy,
                ex=cx,
                ey=cy - geom.glyph_delay_hour_hand,
                stroke=color,
                stroke_width=geom.glyph_delay_stroke,
                stroke_linecap="round",
            )
        )
        g.append(
            draw.Line(
                sx=cx,
                sy=cy,
                ex=cx + geom.glyph_delay_minute_hand,
                ey=cy,
                stroke=color,
                stroke_width=geom.glyph_delay_stroke,
                stroke_linecap="round",
            )
        )
        return g
    # TEXT
    return draw.Text(
        "T",
        x=cx,
        y=cy,
        font_size=geom.glyph_text_font_size,
        fill=color,
        font_weight="700",
        font_style="italic",
        text_anchor="middle",
        dominant_baseline="central",
        font_family="'Roboto', sans-serif",
    )


# --- Geometry ratios (mirrors docs/design/layer.jsx Legend) -----------------
# Every visual size is expressed as a fraction of the document width so the
# legend block keeps the same proportions across output sizes. The pixel value
# on the right of each ``/ 1600`` reproduces the canonical sizing at the
# default 1600-unit document width.
_TAG_W_RATIO = 56 / 1600
_TAG_H_RATIO = 22 / 1600
_HEADER_STRIP_HEIGHT_RATIO = 28 / 1600
_CONTENT_STRIP_HEIGHT_RATIO = 22 / 1600
_ROW_GAP_RATIO = 9 / 1600
_PILL_GAP_RATIO = 6 / 1600
_PILL_HEIGHT_RATIO = 18 / 1600
_PILL_FONT_SIZE_RATIO = 10 / 1600

_PILL_PAD_X_RATIO = 8 / 1600  # horizontal padding inside each pill
_ICON_WIDTH_RATIO = 6 / 1600  # visual width of action glyphs (circle r=3, etc.)
_ICON_TEXT_GAP_RATIO = 10 / 1600  # gap from icon's right edge to text's left edge

_PILL_MIN_TEXT_WIDTH_RATIO = 8 / 1600  # floor for measured text width inside a pill
_PILL_MIN_TOTAL_WIDTH_RATIO = 28 / 1600  # absolute minimum pill width

# Action-glyph primitives — coordinates inside ``build_action_glyph``.
_GLYPH_DOT_RADIUS_RATIO = 3 / 1600
_GLYPH_TRIANGLE_HALF_RATIO = 3 / 1600
_GLYPH_DELAY_DIAL_RADIUS_RATIO = 3.5 / 1600
_GLYPH_DELAY_HOUR_HAND_RATIO = 2.2 / 1600
_GLYPH_DELAY_MINUTE_HAND_RATIO = 1.6 / 1600
_GLYPH_DELAY_STROKE_RATIO = 1.1 / 1600
_GLYPH_TEXT_FONT_SIZE_RATIO = 9 / 1600

# Macro/TD row chrome
_ROW_CONTENT_INDENT_GAP_RATIO = 12 / 1600  # gap between TAG_W and the indent column
_PILL_CORNER_RADIUS_RATIO = 4 / 1600
_TAG_STROKE_WIDTH_RATIO = 1.2 / 1600
_TAG_NAME_GAP_RATIO = 10 / 1600  # gap between the chip and the macro/TD name text
_TAG_NAME_FONT_SIZE_RATIO = 13 / 1600
_TAG_INNER_FONT_SIZE_RATIO = 12 / 1600  # font size for the chip's inline label
_TAG_INNER_TEXT_BASELINE_OFFSET_RATIO = 0.5 / 1600  # tweak so glyphs visually centre
_TAG_HEADER_RULE_INSET_RATIO = 0.5 / 1600  # rule sits just inside the chip's bottom edge
_TAG_HEADER_RULE_STROKE_RATIO = 1 / 1600

# Macro column header / 'MACRO ACTIONS' label
_MACRO_COLUMN_HEADER_HEIGHT_RATIO = 32 / 1600
_MACRO_COLUMN_LABEL_FONT_SIZE_RATIO = 9 / 1600
_MACRO_COLUMN_LABEL_LETTER_SPACING_RATIO = 1.5 / 1600

# Tap-dance section
_TD_ROW_HEIGHT_RATIO = 22 / 1600
_TD_ROW_GAP_RATIO = 9 / 1600
_TD_HEADER_HEIGHT_RATIO = 32 / 1600
_TD_NAME_W_RATIO = 200 / 1600
_TD_CELL_W_RATIO = 110 / 1600
_TD_CELL_INNER_W_RATIO = 80 / 1600  # width of the dashed/filled rect inside a cell
_TD_CELL_HALF_HEIGHT_RATIO = 11 / 1600  # cell rect extends ±this from row centre
_TD_CELL_LABEL_FONT_SIZE_RATIO = 12 / 1600
_TD_CELL_LABEL_HALF_WIDTH_RATIO = 40 / 1600  # cell label x is centred at this offset
_TD_NAME_FONT_SIZE_RATIO = 12 / 1600

# Top-level legend
_SECTION_HEADER_HEIGHT_RATIO = 32 / 1600
_COLUMN_GAP_RATIO = 40 / 1600
_ACTION_KEY_STRIP_HEIGHT_RATIO = 22 / 1600
_ACTION_KEY_PRE_GAP_RATIO = 18 / 1600

# Section title strip ("MACROS" / "TAP-DANCE" + count + rule)
_TITLE_FONT_SIZE_RATIO = 11 / 1600
_TITLE_LETTER_SPACING_RATIO = 3 / 1600
_TITLE_BASELINE_OFFSET_RATIO = 12 / 1600
_TITLE_COUNT_FONT_SIZE_RATIO = 10 / 1600
_TITLE_COUNT_LETTER_SPACING_RATIO = 1 / 1600
_TITLE_RULE_OFFSET_RATIO = 20 / 1600
_TITLE_RULE_STROKE_RATIO = 1.2 / 1600

# Action-key footer strip
_ACTION_KEY_LABEL_FONT_SIZE_RATIO = 9 / 1600
_ACTION_KEY_LABEL_LETTER_SPACING_RATIO = 1.5 / 1600
_ACTION_KEY_LABEL_OFFSET_RATIO = 6 / 1600
_ACTION_KEY_LEGEND_LEFT_RATIO = 90 / 1600  # left edge of the legend swatches
_ACTION_KEY_GLYPH_INSET_RATIO = 6 / 1600  # x offset of glyph centre inside its swatch
_ACTION_KEY_TEXT_INSET_RATIO = 16 / 1600  # x offset of label text from glyph centre
_ACTION_KEY_LABEL_FONT_SIZE_INNER_RATIO = 10 / 1600
_ACTION_KEY_SLOT_LEAD_RATIO = 14 / 1600  # padding before the next swatch
_ACTION_KEY_SLOT_TRAIL_RATIO = 14 / 1600  # padding after the label
_ACTION_KEY_LABEL_CHAR_WIDTH_RATIO = 6 / 1600  # rough advance per character

# Default document width — used as the fallback when callers do not supply one.
_DEFAULT_DOC_WIDTH = 1600.0


@dataclass(frozen=True, slots=True)
class _LegendGeometry:
    """All pixel sizes for the macro/tap-dance legend, derived from ``doc_width``."""

    tag_w: float
    tag_h: float
    header_strip_height: float
    content_strip_height: float
    row_gap: float
    pill_gap: float
    pill_height: float
    pill_font_size: float
    pill_pad_x: float
    icon_width: float
    icon_text_gap: float
    pill_chrome_width: float
    pill_min_text_width: float
    pill_min_total_width: float
    glyph_dot_radius: float
    glyph_triangle_half: float
    glyph_delay_dial_radius: float
    glyph_delay_hour_hand: float
    glyph_delay_minute_hand: float
    glyph_delay_stroke: float
    glyph_text_font_size: float
    row_content_indent_gap: float
    pill_corner_radius: float
    tag_stroke_width: float
    tag_name_gap: float
    tag_name_font_size: float
    tag_inner_font_size: float
    tag_inner_text_baseline_offset: float
    tag_header_rule_inset: float
    tag_header_rule_stroke: float
    macro_column_header_height: float
    macro_column_label_font_size: float
    macro_column_label_letter_spacing: float
    td_row_height: float
    td_row_gap: float
    td_header_height: float
    td_name_w: float
    td_cell_w: float
    td_cell_inner_w: float
    td_cell_half_height: float
    td_cell_label_font_size: float
    td_cell_label_half_width: float
    td_name_font_size: float
    section_header_height: float
    column_gap: float
    action_key_strip_height: float
    action_key_pre_gap: float
    title_font_size: float
    title_letter_spacing: float
    title_baseline_offset: float
    title_count_font_size: float
    title_count_letter_spacing: float
    title_rule_offset: float
    title_rule_stroke: float
    action_key_label_font_size: float
    action_key_label_letter_spacing: float
    action_key_label_offset: float
    action_key_legend_left: float
    action_key_glyph_inset: float
    action_key_text_inset: float
    action_key_label_font_size_inner: float
    action_key_slot_lead: float
    action_key_slot_trail: float
    action_key_label_char_width: float

    @classmethod
    def for_doc_width(cls, doc_width: float) -> "_LegendGeometry":
        pill_pad_x = doc_width * _PILL_PAD_X_RATIO
        icon_width = doc_width * _ICON_WIDTH_RATIO
        icon_text_gap = doc_width * _ICON_TEXT_GAP_RATIO
        return cls(
            tag_w=doc_width * _TAG_W_RATIO,
            tag_h=doc_width * _TAG_H_RATIO,
            header_strip_height=doc_width * _HEADER_STRIP_HEIGHT_RATIO,
            content_strip_height=doc_width * _CONTENT_STRIP_HEIGHT_RATIO,
            row_gap=doc_width * _ROW_GAP_RATIO,
            pill_gap=doc_width * _PILL_GAP_RATIO,
            pill_height=doc_width * _PILL_HEIGHT_RATIO,
            pill_font_size=doc_width * _PILL_FONT_SIZE_RATIO,
            pill_pad_x=pill_pad_x,
            icon_width=icon_width,
            icon_text_gap=icon_text_gap,
            pill_chrome_width=2 * pill_pad_x + icon_width + icon_text_gap,
            pill_min_text_width=doc_width * _PILL_MIN_TEXT_WIDTH_RATIO,
            pill_min_total_width=doc_width * _PILL_MIN_TOTAL_WIDTH_RATIO,
            glyph_dot_radius=doc_width * _GLYPH_DOT_RADIUS_RATIO,
            glyph_triangle_half=doc_width * _GLYPH_TRIANGLE_HALF_RATIO,
            glyph_delay_dial_radius=doc_width * _GLYPH_DELAY_DIAL_RADIUS_RATIO,
            glyph_delay_hour_hand=doc_width * _GLYPH_DELAY_HOUR_HAND_RATIO,
            glyph_delay_minute_hand=doc_width * _GLYPH_DELAY_MINUTE_HAND_RATIO,
            glyph_delay_stroke=doc_width * _GLYPH_DELAY_STROKE_RATIO,
            glyph_text_font_size=doc_width * _GLYPH_TEXT_FONT_SIZE_RATIO,
            row_content_indent_gap=doc_width * _ROW_CONTENT_INDENT_GAP_RATIO,
            pill_corner_radius=doc_width * _PILL_CORNER_RADIUS_RATIO,
            tag_stroke_width=doc_width * _TAG_STROKE_WIDTH_RATIO,
            tag_name_gap=doc_width * _TAG_NAME_GAP_RATIO,
            tag_name_font_size=doc_width * _TAG_NAME_FONT_SIZE_RATIO,
            tag_inner_font_size=doc_width * _TAG_INNER_FONT_SIZE_RATIO,
            tag_inner_text_baseline_offset=doc_width * _TAG_INNER_TEXT_BASELINE_OFFSET_RATIO,
            tag_header_rule_inset=doc_width * _TAG_HEADER_RULE_INSET_RATIO,
            tag_header_rule_stroke=doc_width * _TAG_HEADER_RULE_STROKE_RATIO,
            macro_column_header_height=doc_width * _MACRO_COLUMN_HEADER_HEIGHT_RATIO,
            macro_column_label_font_size=doc_width * _MACRO_COLUMN_LABEL_FONT_SIZE_RATIO,
            macro_column_label_letter_spacing=doc_width * _MACRO_COLUMN_LABEL_LETTER_SPACING_RATIO,
            td_row_height=doc_width * _TD_ROW_HEIGHT_RATIO,
            td_row_gap=doc_width * _TD_ROW_GAP_RATIO,
            td_header_height=doc_width * _TD_HEADER_HEIGHT_RATIO,
            td_name_w=doc_width * _TD_NAME_W_RATIO,
            td_cell_w=doc_width * _TD_CELL_W_RATIO,
            td_cell_inner_w=doc_width * _TD_CELL_INNER_W_RATIO,
            td_cell_half_height=doc_width * _TD_CELL_HALF_HEIGHT_RATIO,
            td_cell_label_font_size=doc_width * _TD_CELL_LABEL_FONT_SIZE_RATIO,
            td_cell_label_half_width=doc_width * _TD_CELL_LABEL_HALF_WIDTH_RATIO,
            td_name_font_size=doc_width * _TD_NAME_FONT_SIZE_RATIO,
            section_header_height=doc_width * _SECTION_HEADER_HEIGHT_RATIO,
            column_gap=doc_width * _COLUMN_GAP_RATIO,
            action_key_strip_height=doc_width * _ACTION_KEY_STRIP_HEIGHT_RATIO,
            action_key_pre_gap=doc_width * _ACTION_KEY_PRE_GAP_RATIO,
            title_font_size=doc_width * _TITLE_FONT_SIZE_RATIO,
            title_letter_spacing=doc_width * _TITLE_LETTER_SPACING_RATIO,
            title_baseline_offset=doc_width * _TITLE_BASELINE_OFFSET_RATIO,
            title_count_font_size=doc_width * _TITLE_COUNT_FONT_SIZE_RATIO,
            title_count_letter_spacing=doc_width * _TITLE_COUNT_LETTER_SPACING_RATIO,
            title_rule_offset=doc_width * _TITLE_RULE_OFFSET_RATIO,
            title_rule_stroke=doc_width * _TITLE_RULE_STROKE_RATIO,
            action_key_label_font_size=doc_width * _ACTION_KEY_LABEL_FONT_SIZE_RATIO,
            action_key_label_letter_spacing=doc_width * _ACTION_KEY_LABEL_LETTER_SPACING_RATIO,
            action_key_label_offset=doc_width * _ACTION_KEY_LABEL_OFFSET_RATIO,
            action_key_legend_left=doc_width * _ACTION_KEY_LEGEND_LEFT_RATIO,
            action_key_glyph_inset=doc_width * _ACTION_KEY_GLYPH_INSET_RATIO,
            action_key_text_inset=doc_width * _ACTION_KEY_TEXT_INSET_RATIO,
            action_key_label_font_size_inner=doc_width * _ACTION_KEY_LABEL_FONT_SIZE_INNER_RATIO,
            action_key_slot_lead=doc_width * _ACTION_KEY_SLOT_LEAD_RATIO,
            action_key_slot_trail=doc_width * _ACTION_KEY_SLOT_TRAIL_RATIO,
            action_key_label_char_width=doc_width * _ACTION_KEY_LABEL_CHAR_WIDTH_RATIO,
        )


# Backwards-compatible module-level constants — these mirror what the legend
# renders at the canonical 1600-unit document width and are kept primarily for
# tests and any external consumers that snapshotted the previous public names.
# Production code should derive sizes from a ``_LegendGeometry`` (or pass
# ``doc_width`` to the public functions) so the legend scales with the canvas.
_DEFAULT_GEOM = _LegendGeometry.for_doc_width(_DEFAULT_DOC_WIDTH)
TAG_W = _DEFAULT_GEOM.tag_w
TAG_H = _DEFAULT_GEOM.tag_h
HEADER_STRIP_HEIGHT = _DEFAULT_GEOM.header_strip_height
CONTENT_STRIP_HEIGHT = _DEFAULT_GEOM.content_strip_height
ROW_GAP = _DEFAULT_GEOM.row_gap
PILL_GAP = _DEFAULT_GEOM.pill_gap
PILL_HEIGHT = _DEFAULT_GEOM.pill_height
PILL_FONT_SIZE = _DEFAULT_GEOM.pill_font_size
PILL_PAD_X = _DEFAULT_GEOM.pill_pad_x
ICON_WIDTH = _DEFAULT_GEOM.icon_width
ICON_TEXT_GAP = _DEFAULT_GEOM.icon_text_gap
PILL_CHROME_WIDTH = _DEFAULT_GEOM.pill_chrome_width
MACRO_COLUMN_HEADER_HEIGHT = _DEFAULT_GEOM.macro_column_header_height
TD_ROW_HEIGHT = _DEFAULT_GEOM.td_row_height
TD_ROW_GAP = _DEFAULT_GEOM.td_row_gap
TD_HEADER_HEIGHT = _DEFAULT_GEOM.td_header_height
TD_NAME_W = _DEFAULT_GEOM.td_name_w
TD_CELL_W = _DEFAULT_GEOM.td_cell_w
SECTION_HEADER_HEIGHT = _DEFAULT_GEOM.section_header_height
COLUMN_GAP = _DEFAULT_GEOM.column_gap
ACTION_KEY_STRIP_HEIGHT = _DEFAULT_GEOM.action_key_strip_height
ACTION_KEY_PRE_GAP = _DEFAULT_GEOM.action_key_pre_gap


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


def _pill_width(label: str, geom: _LegendGeometry) -> float:
    """Compute the pill width to wrap ``label`` exactly.

    Walks the parsed :class:`Label` parts and measures each at its actual
    rendered case. ``TextPart.measure_width`` uppercases the text — that
    matches keymap-key conventions but overstates legend pills, where
    ``Label.build_text`` emits the literal text. Bypass the uppercase
    override for plain text parts; defer to each non-text part's own
    measurement so symbol and separator parts keep their tuned widths.
    """
    label_obj = Label(label, Font.FINGER_KEY, text_color="#000")
    text_width = 0.0
    for part in label_obj.parts:
        font = part.font.load(geom.pill_font_size)
        if isinstance(part, TextPart):
            text_width += font.getlength(part.text)
        else:
            text_width += part.measure_width(font)
    text_width = max(text_width, geom.pill_min_text_width)
    return max(geom.pill_min_total_width, text_width + geom.pill_chrome_width)


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


def _layout_pill_lines(
    pills: list[tuple[SvalboardMacroActionKind, str]],
    line_width: float,
    geom: _LegendGeometry,
) -> list[list[tuple[SvalboardMacroActionKind, str, float]]]:
    """Pack pills into lines, wrapping when the next pill would overflow.

    Returns a list of lines, each a list of ``(kind, label, width)``.
    """
    lines: list[list[tuple[SvalboardMacroActionKind, str, float]]] = [[]]
    cursor = 0.0
    for kind, label in pills:
        w = _pill_width(label, geom)
        if lines[-1] and cursor + geom.pill_gap + w > line_width:
            lines.append([])
            cursor = 0.0
        if lines[-1]:
            cursor += geom.pill_gap
        lines[-1].append((kind, label, w))
        cursor += w
    return lines


def macro_row_height(
    macro: SvalboardMacro[SvalboardTargetKey],
    content_width: float,
    doc_width: float = 1600.0,
) -> float:
    """Total height of one macro row.

    Named macros: header strip + content lines (each pill-line is one
    ``CONTENT_STRIP_HEIGHT`` tall).
    Unnamed macros: just content lines — chip and first pill share the
    first line.
    """
    geom = _LegendGeometry.for_doc_width(doc_width)
    pills = _flatten_macro_pills(macro)
    indent = geom.tag_w + geom.row_content_indent_gap
    lines = _layout_pill_lines(pills, content_width - indent, geom)
    line_count = max(1, len(lines))
    if macro.name:
        return geom.header_strip_height + geom.content_strip_height * line_count
    return geom.content_strip_height * line_count


def build_macro_row(
    macro: SvalboardMacro[SvalboardTargetKey],
    x: float,
    y: float,
    content_width: float,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    use_system_fonts: bool = False,
    doc_width: float = 1600.0,
) -> draw.Group:
    """Render a single macro row at ``(x, y)``.

    Named macros render with a header strip (chip + name + rule) above the
    content strip (pills).  Unnamed macros render single-line: the chip sits
    on the left, vertically centred on the first content strip line, and pills
    flow to the right.
    """
    geom = _LegendGeometry.for_doc_width(doc_width)
    g = draw.Group()
    chip_label_text = f"%%nf-md-script_text_play_outline; {macro.id}"
    indent = geom.tag_w + geom.row_content_indent_gap

    if macro.name:
        # Named layout — header strip (chip top-left at y) + content strip below.
        g.append(
            draw.Rectangle(
                x=x,
                y=y,
                width=geom.tag_w,
                height=geom.tag_h,
                rx=geom.pill_corner_radius,
                ry=geom.pill_corner_radius,
                fill=accent_fill,
                stroke=accent_line,
                stroke_width=geom.tag_stroke_width,
            )
        )
        g.append(
            Label(
                chip_label_text,
                Font.FINGER_KEY,
                text_color="#FFF",
                background_color=accent_fill,
                text_anchor="middle",
                dominant_baseline="central",
            ).build_text(
                x + geom.tag_w / 2,
                y + geom.tag_h / 2 + geom.tag_inner_text_baseline_offset,
                geom.tag_inner_font_size,
                use_system_fonts,
            )
        )
        g.append(
            draw.Text(
                macro.name,
                x=x + geom.tag_w + geom.tag_name_gap,
                y=y + geom.tag_h / 2 + geom.tag_inner_text_baseline_offset,
                font_size=geom.tag_name_font_size,
                font_weight="500",
                dominant_baseline="central",
                font_family="'Roboto', sans-serif",
                fill=text_color,
            )
        )
        g.append(
            draw.Line(
                sx=x + geom.tag_w,
                sy=y + geom.tag_h - geom.tag_header_rule_inset,
                ex=x + content_width,
                ey=y + geom.tag_h - geom.tag_header_rule_inset,
                stroke="#000",
                stroke_opacity=0.08,
                stroke_width=geom.tag_header_rule_stroke,
            )
        )
        line_y = y + geom.header_strip_height
    else:
        # Unnamed layout — chip vertically centred on the first content line.
        chip_y = y + (geom.content_strip_height - geom.tag_h) / 2
        g.append(
            draw.Rectangle(
                x=x,
                y=chip_y,
                width=geom.tag_w,
                height=geom.tag_h,
                rx=geom.pill_corner_radius,
                ry=geom.pill_corner_radius,
                fill=accent_fill,
                stroke=accent_line,
                stroke_width=geom.tag_stroke_width,
            )
        )
        g.append(
            Label(
                chip_label_text,
                Font.FINGER_KEY,
                text_color="#FFF",
                background_color=accent_fill,
                text_anchor="middle",
                dominant_baseline="central",
            ).build_text(
                x + geom.tag_w / 2,
                chip_y + geom.tag_h / 2 + geom.tag_inner_text_baseline_offset,
                geom.tag_inner_font_size,
                use_system_fonts,
            )
        )
        line_y = y

    # Content strip — pills with overflow wrap.
    pills = _flatten_macro_pills(macro)
    lines = _layout_pill_lines(pills, content_width - indent, geom)
    for line in lines:
        cx = x + indent
        for kind, label, w in line:
            # Pill background
            g.append(
                draw.Rectangle(
                    x=cx,
                    y=line_y + (geom.content_strip_height - geom.pill_height) / 2,
                    width=w,
                    height=geom.pill_height,
                    rx=geom.pill_corner_radius,
                    ry=geom.pill_corner_radius,
                    fill="#FAFAF6",
                    stroke=text_color,
                    stroke_opacity=0.18,
                )
            )
            # Action glyph — icon centred at cx + pill_pad_x (so left padding
            # from pill edge to icon centre = pill_pad_x).
            g.append(
                build_action_glyph(
                    kind,
                    cx=cx + geom.pill_pad_x,
                    cy=line_y + geom.content_strip_height / 2,
                    color=text_color,
                    doc_width=doc_width,
                )
            )
            # Label — symmetric around the available text region.
            #   Text region: [cx + pill_pad_x + icon_width/2 + icon_text_gap, cx + w - pill_pad_x]
            #   Text region centre: cx + (pill_pad_x + icon_width/2 + icon_text_gap + w - pill_pad_x) / 2
            #                     = cx + (icon_width/2 + icon_text_gap + w) / 2
            text_centre_x = cx + (geom.icon_width / 2 + geom.icon_text_gap + w) / 2
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
                    line_y + geom.content_strip_height / 2 + geom.tag_inner_text_baseline_offset,
                    geom.pill_font_size,
                    use_system_fonts,
                )
            )
            cx += w + geom.pill_gap
        line_y += geom.content_strip_height
    return g


def build_macro_column_header(
    x: float, y: float, text_color: str, doc_width: float = 1600.0
) -> draw.Group:
    """Render the once-per-column 'MACRO ACTIONS' label.

    Positioned at the indent where pills begin so the label aligns with
    the action column rather than with the chip column.
    """
    geom = _LegendGeometry.for_doc_width(doc_width)
    g = draw.Group()
    g.append(
        draw.Text(
            "MACRO ACTIONS",
            x=x + geom.tag_w + geom.row_content_indent_gap,
            y=y,
            font_size=geom.macro_column_label_font_size,
            fill=text_color,
            letter_spacing=geom.macro_column_label_letter_spacing,
            text_anchor="start",
            font_family="'Roboto', sans-serif",
        )
    )
    return g


def tap_dance_section_height(
    tap_dances: list[SvalboardTapDance[SvalboardTargetKey]],
    doc_width: float = 1600.0,
) -> float:
    """Height of a tap-dance section (column header strip + rows).

    Returns 0 for an empty list so the legend's column-balanced height
    math does not overstate when only one column is populated.
    """
    if not tap_dances:
        return 0.0
    geom = _LegendGeometry.for_doc_width(doc_width)
    return geom.td_header_height + len(tap_dances) * (geom.td_row_height + geom.td_row_gap)


def build_tap_dance_row(
    td: SvalboardTapDance[SvalboardTargetKey],
    x: float,
    y: float,
    column_width: float,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    use_system_fonts: bool = False,
    name_column_width: float | None = None,
    doc_width: float = 1600.0,
    cell_width: float | None = None,
) -> draw.Group:
    """Render a single tap-dance row at ``(x, y)``.

    Imperative wrapper around :func:`legend_components.TapDanceRow` —
    same SVG output, ``y`` here is still the vertical centre of the
    row (the composable's origin is the top-left, so the wrapper
    converts).

    See :func:`legend_components.TapDanceRow` for the full layout
    contract; ``column_width`` is unused (kept for backward
    compatibility with the legacy signature).
    """
    del column_width  # unused — historical part of the API
    from .legend_components import TapDanceRow

    geom = _LegendGeometry.for_doc_width(doc_width)
    component = TapDanceRow(
        td=td,
        accent_fill=accent_fill,
        accent_line=accent_line,
        text_color=text_color,
        geom=geom,
        use_system_fonts=use_system_fonts,
        name_column_width=name_column_width,
        cell_width=cell_width,
    )
    g = draw.Group()
    component.draw_at(g, Point(x, y - geom.td_row_height / 2))
    return g


def build_tap_dance_column_header(
    x: float,
    y: float,
    text_color: str,
    name_column_width: float | None = None,
    doc_width: float = 1600.0,
    cell_width: float | None = None,
) -> draw.Group:
    """Render the once-per-column TAP/HOLD/DOUBLE-TAP/TAP&HOLD strip.

    Imperative wrapper around
    :func:`legend_components.TapDanceColumnHeader`. ``y`` here is the
    text baseline (legacy contract); the composable's origin is the
    top of its bounding box, so the wrapper subtracts
    ``title_baseline_offset`` to land the labels at the same y as
    before.
    """
    from .legend_components import TapDanceColumnHeader

    geom = _LegendGeometry.for_doc_width(doc_width)
    component = TapDanceColumnHeader(
        text_color=text_color,
        geom=geom,
        name_column_width=name_column_width,
        cell_width=cell_width,
    )
    g = draw.Group()
    component.draw_at(g, Point(x, y - geom.title_baseline_offset))
    return g


def _column_widths(content_width: float, geom: _LegendGeometry) -> tuple[float, float]:
    col = (content_width - geom.column_gap) / 2
    return col, col


def _macro_section_height(
    rows: list[SvalboardMacro[SvalboardTargetKey]],
    col_width: float,
    doc_width: float = _DEFAULT_DOC_WIDTH,
) -> float:
    """Height of a macro section: title strip + column header + rows + action-key footer.

    Returns 0 when ``rows`` is empty (no section to render).
    """
    if not rows:
        return 0.0
    geom = _LegendGeometry.for_doc_width(doc_width)
    h = geom.section_header_height + geom.macro_column_header_height
    for i, r in enumerate(rows):
        if i > 0:
            h += geom.row_gap
        h += macro_row_height(r, col_width, doc_width=doc_width)
    h += geom.action_key_pre_gap + geom.action_key_strip_height
    return h


def legend_height(
    layout: LegendLayout | None, content_width: float, doc_width: float = 1600.0
) -> float:
    """Total intrinsic height of the legend block.

    Each section (macros, tap-dances) occupies its own column at half
    the content width. Returns the height of the taller section so the
    caller reserves enough space for both. Returns 0 when ``layout is
    None`` (no specials on this layer).
    """
    if layout is None:
        return 0.0
    geom = _LegendGeometry.for_doc_width(doc_width)
    col_w, _ = _column_widths(content_width, geom)
    h_macros = _macro_section_height(layout.macro_left, col_w, doc_width)
    h_tds = (
        geom.section_header_height + tap_dance_section_height(layout.tap_dance_left, doc_width)
        if layout.tap_dance_left
        else 0.0
    )
    return max(h_macros, h_tds)


def _draw_section_title(
    g: draw.Group,
    title: str,
    x: float,
    y: float,
    width: float,
    accent_line: str,
    count: int,
    geom: _LegendGeometry,
) -> None:
    """Render a section title strip ('MACROS' or 'TAP-DANCE') with rule below."""
    g.append(
        draw.Text(
            title,
            x=x,
            y=y + geom.title_baseline_offset,
            font_size=geom.title_font_size,
            font_weight="700",
            letter_spacing=geom.title_letter_spacing,
            text_anchor="start",
            font_family="'Roboto', sans-serif",
            fill=accent_line,
        )
    )
    g.append(
        draw.Text(
            f"{count} ENTRIES",
            x=x + width,
            y=y + geom.title_baseline_offset,
            font_size=geom.title_count_font_size,
            text_anchor="end",
            fill="#888",
            font_weight="400",
            letter_spacing=geom.title_count_letter_spacing,
            font_family="'Roboto', sans-serif",
        )
    )
    g.append(
        draw.Line(
            sx=x,
            sy=y + geom.title_rule_offset,
            ex=x + width,
            ey=y + geom.title_rule_offset,
            stroke=accent_line,
            stroke_opacity=0.5,
            stroke_width=geom.title_rule_stroke,
        )
    )


def _draw_macro_title(
    g: draw.Group,
    x: float,
    y: float,
    width: float,
    accent_line: str,
    count: int,
    geom: _LegendGeometry,
) -> None:
    _draw_section_title(g, "MACROS", x, y, width, accent_line, count, geom)


def _draw_td_title(
    g: draw.Group,
    x: float,
    y: float,
    width: float,
    accent_line: str,
    count: int,
    geom: _LegendGeometry,
) -> None:
    _draw_section_title(g, "TAP-DANCE", x, y, width, accent_line, count, geom)


def _action_key_strip(x: float, y: float, text_color: str, doc_width: float = 1600.0) -> draw.Group:
    """The 'tap | press | release | text | delay' key below macros."""
    geom = _LegendGeometry.for_doc_width(doc_width)
    g = draw.Group()
    g.append(
        draw.Text(
            "ACTION KEY",
            x=x,
            y=y + geom.action_key_label_offset,
            font_size=geom.action_key_label_font_size,
            fill="#999",
            letter_spacing=geom.action_key_label_letter_spacing,
            dominant_baseline="central",
            font_family="'Roboto', sans-serif",
        )
    )
    cx = x + geom.action_key_legend_left
    items = [
        (SvalboardMacroActionKind.TAP, "tap"),
        (SvalboardMacroActionKind.DOWN, "press"),
        (SvalboardMacroActionKind.UP, "release"),
        (SvalboardMacroActionKind.TEXT, "text"),
        (SvalboardMacroActionKind.DELAY, "delay"),
    ]
    for kind, label in items:
        g.append(
            build_action_glyph(
                kind,
                cx=cx + geom.action_key_glyph_inset,
                cy=y + geom.action_key_label_offset,
                color=text_color,
                doc_width=doc_width,
            )
        )
        g.append(
            draw.Text(
                label,
                x=cx + geom.action_key_text_inset,
                y=y + geom.action_key_label_offset,
                font_size=geom.action_key_label_font_size_inner,
                fill="#666",
                dominant_baseline="central",
                font_family="'Roboto', sans-serif",
            )
        )
        cx += (
            geom.action_key_slot_lead
            + len(label) * geom.action_key_label_char_width
            + geom.action_key_slot_trail
        )
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
    geom: _LegendGeometry,
    doc_width: float,
    use_system_fonts: bool = False,
) -> float:
    """Stamp ``rows`` into one column starting at ``start_y``.

    Returns the y position immediately after the last row (no action-key
    footer applied here — the caller emits a single shared footer).
    """
    cursor = start_y
    for i, m in enumerate(rows):
        if i > 0:
            cursor += geom.row_gap
        g.append(
            build_macro_row(
                m,
                x=col_x,
                y=cursor,
                content_width=col_w,
                accent_fill=accent_fill,
                accent_line=accent_line,
                text_color=text_color,
                use_system_fonts=use_system_fonts,
                doc_width=doc_width,
            )
        )
        cursor += macro_row_height(m, col_w, doc_width=doc_width)
    return cursor


def _td_name_column_width(
    geom: _LegendGeometry,
    *row_groups: list[SvalboardTapDance[SvalboardTargetKey]],
) -> float:
    """Reserve the name area only when at least one row has a name.

    All passed groups share the same compact decision so left/right
    columns of a span-columns section align consistently.
    """
    has_any_name = any(td.name for group in row_groups for td in group)
    return (geom.td_name_w - geom.tag_w) if has_any_name else 0.0


def _draw_td_column(
    g: draw.Group,
    rows: list[SvalboardTapDance[SvalboardTargetKey]],
    col_x: float,
    start_y: float,
    col_w: float,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    geom: _LegendGeometry,
    doc_width: float,
    use_system_fonts: bool = False,
    name_column_width: float | None = None,
) -> None:
    if name_column_width is None:
        name_column_width = geom.td_name_w - geom.tag_w
    g.append(
        build_tap_dance_column_header(
            x=col_x,
            y=start_y + geom.title_baseline_offset,
            text_color=text_color,
            name_column_width=name_column_width,
            doc_width=doc_width,
        )
    )
    cursor = start_y + geom.td_header_height
    for t in rows:
        g.append(
            build_tap_dance_row(
                t,
                x=col_x,
                y=cursor + geom.td_row_height / 2,
                column_width=col_w,
                accent_fill=accent_fill,
                accent_line=accent_line,
                text_color=text_color,
                use_system_fonts=use_system_fonts,
                name_column_width=name_column_width,
                doc_width=doc_width,
            )
        )
        cursor += geom.td_row_height + geom.td_row_gap


def build_legend(
    layout: LegendLayout | None,
    x: float,
    y: float,
    content_width: float,
    palette: Palette,
    use_system_fonts: bool = False,
    doc_width: float = 1600.0,
) -> draw.Group | None:
    """Render the full legend block at ``(x, y)``.

    Returns ``None`` when ``layout`` is ``None`` (no specials on the layer).
    """
    if layout is None:
        return None
    geom = _LegendGeometry.for_doc_width(doc_width)
    macro_line = derive_accent_line(palette.macro_color)
    td_line = derive_accent_line(palette.tap_dance_color)
    col_w, _ = _column_widths(content_width, geom)
    g = draw.Group()

    if layout.macro_left:
        _draw_macro_title(
            g,
            x,
            y,
            col_w,
            macro_line,
            count=len(layout.macro_left),
            geom=geom,
        )
        g.append(
            build_macro_column_header(
                x=x,
                y=y + geom.section_header_height + geom.title_baseline_offset,
                text_color=palette.text_color,
                doc_width=doc_width,
            )
        )
        end_left = _draw_macro_column(
            g,
            layout.macro_left,
            x,
            y + geom.section_header_height + geom.macro_column_header_height,
            col_w,
            palette.macro_color,
            macro_line,
            palette.text_color,
            geom,
            doc_width,
            use_system_fonts=use_system_fonts,
        )
        g.append(
            _action_key_strip(
                x=x,
                y=end_left + geom.action_key_pre_gap,
                text_color=palette.text_color,
                doc_width=doc_width,
            )
        )

    if layout.tap_dance_left:
        _draw_td_title(
            g,
            x + col_w + geom.column_gap,
            y,
            col_w,
            td_line,
            count=len(layout.tap_dance_left),
            geom=geom,
        )
        td_name_w = _td_name_column_width(geom, layout.tap_dance_left)
        _draw_td_column(
            g,
            layout.tap_dance_left,
            x + col_w + geom.column_gap,
            y + geom.section_header_height,
            col_w,
            palette.tap_dance_color,
            td_line,
            palette.text_color,
            geom,
            doc_width,
            use_system_fonts=use_system_fonts,
            name_column_width=td_name_w,
        )
    return g
