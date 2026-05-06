# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The macros section composables.

* :class:`MacroMetrics` — sizing constants for the macro rows. Owns
  every chip / pill / row pixel metric the composables consume.
* :func:`MacroChip` — the colored ID tag with the script-glyph + id.
* :func:`MacroPill` — one action pill: rounded rect with action icon
  on the left and a label centred in the post-icon region.
* :func:`MacroPillRow` — pills wrapping over multiple lines based on
  ``max_width``.
* :func:`MacroRow` — chip + (optional) name strip + pill row, the
  per-macro composable.
* :func:`MacroTable` — stacked :func:`MacroRow` instances with a
  ``section_spacing`` split between the named- and unnamed-macro
  sub-blocks.
* :func:`MacroSection` — a ``MACROS`` :func:`SectionStripe` followed
  by a :func:`MacroTable`, laid out in a Column with the section's
  standard inter-strip / body gap. Owns the natural-width pre-pass
  internally so the document layer just passes a ``max_width``
  budget.
"""

from __future__ import annotations

from dataclasses import dataclass

import drawsvg as draw

from skim.data import resolve_spacing
from skim.domain import (
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardMacroActionKind,
    SvalboardTargetKey,
)

from .adjustable_text import AdjustableText
from .composable import Composable
from .font import Font
from .primitives import Column, Component, MetricsComponent, Point, Size
from .render_context import RenderContext, TextStyle
from .rich_text import RichText
from .section_data import format_key_label
from .section_stripe import SectionStripe, SectionStripeMetrics
from .styling import derive_accent_line

# ---------------------------------------------------------------------------
# Per-doc-width ratios — chip / pill / row pixel metrics expressed as
# fractions of the document width so the macros section stays visually
# proportional across canvas sizes.
# ---------------------------------------------------------------------------

_CHIP_WIDTH_RATIO = 56.0 / 1600.0
_CORNER_RADIUS_RATIO = 4.0 / 1600.0
# Default proportion (of doc width) for ``chip_outline`` when
# ``Strokes.chip_outline`` is left at ``None``.
_CHIP_STROKE_WIDTH_RATIO = 1.2 / 1600.0
_CHIP_INNER_FONT_SIZE_RATIO = 12.0 / 1600.0
_CHIP_INNER_TEXT_BASELINE_OFFSET_RATIO = 0.5 / 1600.0
_NAME_FONT_SIZE_RATIO = 13.0 / 1600.0
# Default proportion (of doc width) for ``chip_padding`` when the
# user leaves ``Spacing.chip_padding`` at ``None``. Symmetric
# horizontal inset inside any chip-shaped element. Vertical padding
# is ``chip_padding * 0.25``; ``chip_height`` derives as
# ``font_size + 2 * vertical_padding``.
_CHIP_PADDING_RATIO = 20.0 / 1600.0
_CHIP_VERTICAL_PADDING_PROPORTION_OF_CHIP_PADDING = 0.25
# Default proportion (of doc width) for the named-macro hairline
# stroke when ``Strokes.header_rule`` is left at ``None``. Unified
# with the section-stripe rule at 1.2/1600 (was 1.0/1600 in the
# legacy code).
_RULE_STROKE_RATIO = 1.2 / 1600.0
_PILL_ROW_HEIGHT_RATIO = 22.0 / 1600.0
_PILL_HEIGHT_RATIO = 18.0 / 1600.0
_PILL_FONT_SIZE_RATIO = 10.0 / 1600.0
# Default proportion (of doc width) for ``macro_action_inset`` when
# the user leaves ``Spacing.macro_action_inset`` at ``None``. A
# single uniform inset governs every gap inside a macro action pill:
# pill edge → icon centre, icon centre → text start, text end → pill
# edge. One configurable value keeps the pill's internal rhythm
# consistent without exposing three knobs that have to move together.
_MACRO_ACTION_INSET_RATIO = 10.0 / 1600.0
_PILL_ICON_WIDTH_RATIO = 6.0 / 1600.0
_PILL_MIN_TEXT_WIDTH_RATIO = 8.0 / 1600.0
_PILL_MIN_TOTAL_WIDTH_RATIO = 28.0 / 1600.0

# Action-glyph primitive sizing — read inside :func:`build_action_glyph`.
# Expressed as fractions of the document width so the glyphs stay
# visually proportional across canvas sizes.
_GLYPH_DOT_RADIUS_RATIO = 3 / 1600
_GLYPH_TRIANGLE_HALF_RATIO = 3 / 1600
_GLYPH_DELAY_DIAL_RADIUS_RATIO = 3.5 / 1600
_GLYPH_DELAY_HOUR_HAND_RATIO = 2.2 / 1600
_GLYPH_DELAY_MINUTE_HAND_RATIO = 1.6 / 1600
_GLYPH_DELAY_STROKE_RATIO = 1.1 / 1600
_GLYPH_TEXT_FONT_SIZE_RATIO = 9 / 1600


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class MacroSectionMetrics:
    """Metrics exposed by a built :func:`MacroSection`.

    The single field is the section title strip's ``rule_offset`` —
    surfaced so the parent document doesn't need to import
    :class:`SectionStripeMetrics` just to compute the gap that
    should sit above and below the section. Document composables
    use ``section.metrics.rule_offset * 0.5`` as the inter-sibling
    gap, matching the legacy positional-layout breathing constant.
    """

    rule_offset: float


@dataclass(frozen=True, slots=True, kw_only=True)
class MacroMetrics:
    """Sizing constants for the macros composables.

    Owns every chip/pill/row pixel metric the macro composables read.
    The three universal table spacings (``table_col_spacing``,
    ``table_header_spacing``, ``table_row_spacing``) come from
    :class:`DocumentMetrics` so every table-shaped composable in the
    image agrees on rhythm.
    """

    # Universal table spacings — sourced from ``DocumentMetrics``.
    table_col_spacing: float
    table_header_spacing: float
    table_row_spacing: float

    # Chip (the colored ID tag at the row header).
    chip_width: float
    chip_height: float
    """Derived as ``chip_inner_font_size + 2 * chip_padding * 0.25``."""
    chip_corner_radius: float
    chip_stroke_width: float
    chip_inner_font_size: float
    chip_inner_text_baseline_offset: float
    chip_padding: float
    """Symmetric horizontal inset inside any chip-shaped element.
    Used today for the leading gap between the chip body and the
    named-macro name text."""

    # Named-header extras (chip + name + horizontal rule).
    name_font_size: float
    rule_inset: float
    """Vertical offset that pulls the hairline rule up by half a
    stroke so its centred path visually aligns with the chip's
    stroked bottom edge. Derived: ``rule_stroke / 2``."""
    rule_stroke: float

    # Pills (action steps painted to the right of each chip).
    pill_row_height: float
    pill_height: float
    pill_corner_radius: float
    pill_font_size: float
    macro_action_inset: float
    """Uniform inset inside a pill — pill edge → icon centre,
    icon centre → text start, and text end → pill edge all use this
    same value."""
    pill_icon_width: float
    pill_min_text_width: float
    pill_min_total_width: float
    pill_chrome_width: float

    @classmethod
    def from_ctx(cls, ctx: RenderContext, *, scale: float = 1.0) -> MacroMetrics:
        """Resolve from the active context's document metrics.

        ``scale`` multiplies the underlying doc-width so the body of a
        body-scaled image (e.g. the standalone macros image, which
        uses ``BODY_SCALE``) renders larger chips/pills while the
        chrome stays at its unscaled per-image size.
        """
        doc_m = ctx.document_metrics
        spacing = ctx.config.output.layout.spacing
        strokes = ctx.config.output.style.strokes
        w = doc_m.doc_width * scale
        rule_stroke = (
            resolve_spacing(
                strokes.header_rule,
                base=doc_m.doc_width,
                default_proportion=_RULE_STROKE_RATIO,
            )
            * scale
        )
        action_inset = (
            resolve_spacing(
                spacing.macro_action_inset,
                base=doc_m.doc_width,
                default_proportion=_MACRO_ACTION_INSET_RATIO,
            )
            * scale
        )
        icon_w = w * _PILL_ICON_WIDTH_RATIO
        chip_padding = (
            resolve_spacing(
                spacing.chip_padding,
                base=doc_m.doc_width,
                default_proportion=_CHIP_PADDING_RATIO,
            )
            * scale
        )
        chip_inner_font_size = w * _CHIP_INNER_FONT_SIZE_RATIO
        chip_height = chip_inner_font_size + 2 * (
            chip_padding * _CHIP_VERTICAL_PADDING_PROPORTION_OF_CHIP_PADDING
        )
        return cls(
            table_col_spacing=doc_m.table_col_spacing * scale,
            table_header_spacing=doc_m.table_header_spacing * scale,
            table_row_spacing=doc_m.table_row_spacing * scale,
            chip_width=w * _CHIP_WIDTH_RATIO,
            chip_height=chip_height,
            chip_corner_radius=w * _CORNER_RADIUS_RATIO,
            chip_stroke_width=resolve_spacing(
                strokes.chip_outline,
                base=doc_m.doc_width,
                default_proportion=_CHIP_STROKE_WIDTH_RATIO,
            )
            * scale,
            chip_inner_font_size=chip_inner_font_size,
            chip_inner_text_baseline_offset=w * _CHIP_INNER_TEXT_BASELINE_OFFSET_RATIO,
            chip_padding=chip_padding,
            name_font_size=w * _NAME_FONT_SIZE_RATIO,
            rule_inset=rule_stroke / 2.0,
            rule_stroke=rule_stroke,
            pill_row_height=w * _PILL_ROW_HEIGHT_RATIO,
            pill_height=w * _PILL_HEIGHT_RATIO,
            pill_corner_radius=w * _CORNER_RADIUS_RATIO,
            pill_font_size=w * _PILL_FONT_SIZE_RATIO,
            macro_action_inset=action_inset,
            pill_icon_width=icon_w,
            pill_min_text_width=w * _PILL_MIN_TEXT_WIDTH_RATIO,
            pill_min_total_width=w * _PILL_MIN_TOTAL_WIDTH_RATIO,
            # Total non-text width: leading inset + icon + icon-text
            # inset + trailing inset.
            pill_chrome_width=3 * action_inset + icon_w,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pill_width(label: str, *, metrics: MacroMetrics) -> float:
    """Compute the pill width that wraps ``label`` exactly.

    Same math :func:`MacroPill` uses, lifted into a free function so
    the section-level :func:`_macro_natural_widths` pre-pass can
    measure pill rows without instantiating each pill's composable
    chain. Builds a throwaway :func:`RichText` to get the natural
    label width — the rich-text element reports its own size, so
    going through it keeps measurement behaviour identical to what
    the painted pill uses.
    """
    label_style = TextStyle(font=Font.FINGER_KEY, size=metrics.pill_font_size)
    natural = RichText(text=label, style=label_style).size.width
    text_width = max(natural, metrics.pill_min_text_width)
    return max(metrics.pill_min_total_width, text_width + metrics.pill_chrome_width)


def build_action_glyph(
    kind: SvalboardMacroActionKind,
    cx: float,
    cy: float,
    color: str,
    doc_width: float = 1600.0,
) -> draw.DrawingElement:
    """Return a tiny SVG primitive for the given macro action kind.

    - TAP   → filled circle (●).
    - DOWN  → filled down-triangle (▼) — "press".
    - UP    → filled up-triangle   (▲) — "release".
    - TEXT  → italic capital ``T``.
    - DELAY → small clock dial (circle + two hands).

    Glyph dimensions scale with ``doc_width`` so the icons stay
    visually consistent across output sizes. Reads its sizing
    constants directly from the ``_GLYPH_*_RATIO`` constants at the
    top of the module.
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


def _macro_action_pill_labels(action: SvalboardMacroAction) -> list[str]:
    """Visible label per pill emitted by an action.

    TAP/DOWN/UP emit one pill per key in ``action.keys``. TEXT emits
    one pill with the literal text. DELAY emits one pill with
    ``"<duration>ms"``.
    """
    if action.kind in (
        SvalboardMacroActionKind.TAP,
        SvalboardMacroActionKind.DOWN,
        SvalboardMacroActionKind.UP,
    ):
        return [format_key_label(k) for k in action.keys]
    if action.kind == SvalboardMacroActionKind.TEXT:
        return [action.text.replace("\n", " ")]
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


# ---------------------------------------------------------------------------
# Macro composables
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def MacroChip(
    ctx,
    *,
    macro_id: str,
    accent_fill: str,
    accent_line: str,
    scale: float = 1.0,
):
    """The colored ID tag at the head of a macro row.

    Rounded filled rectangle with a centred ``%%nf-md-script_text_play_outline; <id>``
    label rendered as a :func:`RichText` (so the Nerd Font glyph and
    the id text share a single line with the right per-span fonts).
    """
    metrics = MacroMetrics.from_ctx(ctx, scale=scale)
    label_style = TextStyle(
        font=Font.FINGER_KEY,
        size=metrics.chip_inner_font_size,
        color="#FFF",
    )
    label_el = RichText(
        text=f"%%nf-md-script_text_play_outline; {macro_id}",
        style=label_style,
        text_anchor="start",
        dominant_baseline="central",
    )
    size = Size(metrics.chip_width, metrics.chip_height)

    def draw_at(d, origin):
        d.append(
            draw.Rectangle(
                x=origin.x,
                y=origin.y,
                width=metrics.chip_width,
                height=metrics.chip_height,
                rx=metrics.chip_corner_radius,
                ry=metrics.chip_corner_radius,
                fill=accent_fill,
                stroke=accent_line,
                stroke_width=metrics.chip_stroke_width,
            )
        )
        # Centre the RichText bbox horizontally and vertically inside
        # the chip; the ``chip_inner_text_baseline_offset`` is the
        # same magic central-baseline tweak the TD chip and cell
        # labels apply.
        cx = origin.x + metrics.chip_width / 2
        cy = origin.y + metrics.chip_height / 2 + metrics.chip_inner_text_baseline_offset
        label_origin = Point(cx - label_el.size.width / 2, cy - label_el.size.height / 2)
        label_el.draw_at(d, label_origin)

    return size, draw_at


@Composable(use_context=True)
def MacroPill(
    ctx,
    *,
    kind: SvalboardMacroActionKind,
    label: str,
    text_color: str,
    scale: float = 1.0,
):
    """One action pill: rounded rect background + icon + label.

    Reports ``Size(pill_width, pill_row_height)`` — the pill's visible
    rectangle is ``pill_height`` tall and centred vertically within
    the row-height bounding box, matching the legacy layout. The
    label is rendered as a :func:`RichText` (so labels containing Nerd
    Font tokens render with the right per-span fonts) and centred
    around the post-icon text region.
    """
    metrics = MacroMetrics.from_ctx(ctx, scale=scale)
    doc_width = ctx.document_metrics.doc_width * scale

    label_style = TextStyle(
        font=Font.FINGER_KEY,
        size=metrics.pill_font_size,
        color=text_color,
    )
    label_el = RichText(
        text=label,
        style=label_style,
        text_anchor="start",
        dominant_baseline="central",
    )
    text_width = max(label_el.size.width, metrics.pill_min_text_width)
    pill_w = max(metrics.pill_min_total_width, text_width + metrics.pill_chrome_width)
    size = Size(pill_w, metrics.pill_row_height)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        # Pill background — visible rect centred vertically in the
        # row-height bbox.
        d.append(
            draw.Rectangle(
                x=x,
                y=y + (metrics.pill_row_height - metrics.pill_height) / 2,
                width=pill_w,
                height=metrics.pill_height,
                rx=metrics.pill_corner_radius,
                ry=metrics.pill_corner_radius,
                fill="#FAFAF6",
                stroke=text_color,
                stroke_opacity=0.18,
            )
        )
        # Action glyph — icon's LEFT EDGE sits at ``x +
        # macro_action_inset`` so the visible whitespace before the
        # icon equals the same configurable value the icon → text
        # gap and trailing pad use. Painted at the centre point
        # ``inset + icon_width/2`` because :func:`build_action_glyph`
        # is centre-anchored.
        d.append(
            build_action_glyph(
                kind,
                cx=x + metrics.macro_action_inset + metrics.pill_icon_width / 2,
                cy=y + metrics.pill_row_height / 2,
                color=text_color,
                doc_width=doc_width,
            )
        )
        # Label — centred in the available text region:
        #   left  = x + macro_action_inset + icon_width + macro_action_inset
        #   right = x + pill_w - macro_action_inset
        #   centre = x + (icon_width + macro_action_inset + pill_w) / 2
        text_centre_x = x + (metrics.pill_icon_width + metrics.macro_action_inset + pill_w) / 2
        cy = y + metrics.pill_row_height / 2 + metrics.chip_inner_text_baseline_offset
        label_el.draw_at(
            d,
            Point(text_centre_x - label_el.size.width / 2, cy - label_el.size.height / 2),
        )

    return size, draw_at


@Composable(use_context=True)
def MacroPillRow(
    ctx,
    *,
    pills: list[tuple[SvalboardMacroActionKind, str]],
    text_color: str,
    max_width: float,
    scale: float = 1.0,
):
    """Lay out ``pills`` over one or more lines wrapping at ``max_width``.

    Each line is ``pill_row_height`` tall; lines stack with no extra
    vertical gap — the legacy macro section painted lines flush since
    pills are visually thinner than the row. Pills inside a line are
    separated by ``table_col_spacing``.
    """
    metrics = MacroMetrics.from_ctx(ctx, scale=scale)
    pill_els = [
        MacroPill(kind=kind, label=label, text_color=text_color, scale=scale)
        for kind, label in pills
    ]

    # Pack pills into lines. Same wrap logic as the legacy
    # ``_layout_pill_lines`` — append to the current line until adding
    # the next pill (plus the inter-pill spacing) would exceed
    # ``max_width``, then start a fresh line.
    lines: list[list[Component]] = [[]]
    cursor = 0.0
    for pill in pill_els:
        if lines[-1] and cursor + metrics.table_col_spacing + pill.size.width > max_width:
            lines.append([])
            cursor = 0.0
        if lines[-1]:
            cursor += metrics.table_col_spacing
        lines[-1].append(pill)
        cursor += pill.size.width

    line_widths = [
        sum(p.size.width for p in line) + max(0, len(line) - 1) * metrics.table_col_spacing
        for line in lines
    ]
    width = max(line_widths) if line_widths else 0.0
    height = len(lines) * metrics.pill_row_height if pill_els else 0.0
    size = Size(width, height)

    def draw_at(d, origin):
        line_y = origin.y
        for line in lines:
            cx = origin.x
            for pill in line:
                pill.draw_at(d, Point(cx, line_y))
                cx += pill.size.width + metrics.table_col_spacing
            line_y += metrics.pill_row_height

    return size, draw_at


@Composable(use_context=True)
def MacroRow(
    ctx,
    *,
    macro: SvalboardMacro[SvalboardTargetKey],
    accent_fill: str,
    accent_line: str,
    text_color: str,
    content_width: float,
    scale: float = 1.0,
):
    """One macro row: chip + (optional) name strip + pill row.

    Named macros render with a header strip — chip top-left, name
    text just to the right of the chip, and a horizontal rule
    extending from the chip's right edge to ``content_width`` —
    followed by ``table_header_spacing`` of breathing room and then
    the pill row. Unnamed macros render single-line: the chip sits on
    the left and the pill row flows to the right, both vertically
    centred on the same line (the chip and the pill row share
    ``pill_row_height``).
    """
    metrics = MacroMetrics.from_ctx(ctx, scale=scale)

    chip = MacroChip(
        macro_id=macro.id,
        accent_fill=accent_fill,
        accent_line=accent_line,
        scale=scale,
    )
    pills = _flatten_macro_pills(macro)
    indent = metrics.chip_width + metrics.table_header_spacing
    pill_row = MacroPillRow(
        pills=pills,
        text_color=text_color,
        max_width=max(0.0, content_width - indent),
        scale=scale,
    )

    if macro.name:
        # Header strip is ``chip_height`` tall; pill row sits below
        # with a ``table_header_spacing`` gap.
        height = metrics.chip_height + metrics.table_header_spacing + pill_row.size.height
        # Pre-build the name as :func:`AdjustableText` so a long name
        # would shrink to fit before overflowing the rule's right edge.
        # The text slot starts at ``chip_width + chip_padding`` from
        # the row's left and ends at ``content_width``.
        name_max_width = max(0.0, content_width - metrics.chip_width - metrics.chip_padding)
        name_el = AdjustableText(
            text=macro.name,
            style=TextStyle(font=Font.FINGER_KEY, size=metrics.name_font_size, color=text_color),
            max_width=name_max_width,
            text_anchor="start",
            dominant_baseline="central",
        )
    else:
        height = pill_row.size.height
        name_el = None

    size = Size(content_width, height)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        if macro.name:
            # Chip at top-left of the header strip.
            chip.draw_at(d, Point(x, y))
            # Name to the right of the chip, vertically centred on
            # the header strip.
            assert name_el is not None
            name_origin = Point(
                x + metrics.chip_width + metrics.chip_padding,
                y
                + metrics.chip_height / 2
                + metrics.chip_inner_text_baseline_offset
                - name_el.size.height / 2,
            )
            name_el.draw_at(d, name_origin)
            # Horizontal rule under the header strip — a hair inside
            # the chip's bottom edge so the chip's outlined stroke and
            # the rule visually align.
            rule_y = y + metrics.chip_height - metrics.rule_inset
            d.append(
                draw.Line(
                    sx=x + metrics.chip_width,
                    sy=rule_y,
                    ex=x + content_width,
                    ey=rule_y,
                    stroke="#000",
                    stroke_opacity=0.08,
                    stroke_width=metrics.rule_stroke,
                )
            )
            pill_row.draw_at(
                d,
                Point(x + indent, y + metrics.chip_height + metrics.table_header_spacing),
            )
        else:
            # Chip on the left, pill row to the right; both occupy
            # the same ``pill_row_height``-tall line. Chip is
            # ``chip_height`` tall, so vertically centre it within
            # the row-height bounding box.
            chip_y = y + (metrics.pill_row_height - metrics.chip_height) / 2
            chip.draw_at(d, Point(x, chip_y))
            pill_row.draw_at(d, Point(x + indent, y))

    return size, draw_at


# ---------------------------------------------------------------------------
# Internal pre-pass helper used by :func:`MacroSection` to decide
# whether the canvas can snug to the macros' natural single-line
# width (no pill wrapping) or has to spend the full max_width budget.
# ---------------------------------------------------------------------------


def _macro_natural_widths(macros: list, *, metrics: MacroMetrics) -> list[float]:
    """Width each macro would render at if every pill sat on a single line.

    Mirrors what :func:`MacroPillRow` would lay out against an
    unbounded width: per-pill widths summed plus inter-pill
    ``table_col_spacing``, then offset by the chip indent.
    """
    indent = metrics.chip_width + metrics.table_header_spacing
    widths: list[float] = []
    for macro in macros:
        pills = _flatten_macro_pills(macro)
        if not pills:
            widths.append(indent)
            continue
        pill_widths = [_pill_width(label, metrics=metrics) for _kind, label in pills]
        line_w = sum(pill_widths) + (len(pill_widths) - 1) * metrics.table_col_spacing
        widths.append(indent + line_w)
    return widths


# ---------------------------------------------------------------------------
# MacroTable + MacroSection
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def MacroTable(
    ctx,
    *,
    macros: list,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    content_width: float,
    scale: float = 1.0,
):
    """Stacked :func:`MacroRow` instances with the section's row rhythm.

    Per-row height respects ``content_width`` (pills wrap to additional
    lines when they don't fit). ``scale`` is forwarded to each row so
    body-scaled images render larger chips/pills uniformly.
    """
    metrics = MacroMetrics.from_ctx(ctx, scale=scale)
    section_spacing = ctx.document_metrics.section_spacing

    rows = [
        MacroRow(
            macro=m,
            accent_fill=accent_fill,
            accent_line=accent_line,
            text_color=text_color,
            content_width=content_width,
            scale=scale,
        )
        for m in macros
    ]

    # Named macros sort first (see ``all_macros``); a single named→unnamed
    # transition splits the table into a "named" and "unnamed" sub-block,
    # separated by ``section_spacing`` instead of the usual row gap. The TD
    # table doesn't get this treatment — its rows are uniform.
    def _gap_before(i: int) -> float:
        if i == 0:
            return 0.0
        if macros[i - 1].name and not macros[i].name:
            return section_spacing
        return metrics.table_row_spacing

    total_h = sum(r.size.height for r in rows) + sum(_gap_before(i) for i in range(len(rows)))
    size = Size(content_width, total_h)

    def draw_at(d, origin):
        cursor = origin.y
        for i, row in enumerate(rows):
            cursor += _gap_before(i)
            row.draw_at(d, Point(origin.x, cursor))
            cursor += row.size.height

    return size, draw_at


@Composable(use_context=True)
def MacroSection(
    ctx,
    *,
    macros: list,
    max_width: float,
    wrap_content: bool = False,
    scale: float = 1.0,
):
    """The MACROS section — :func:`SectionStripe` + :func:`MacroTable`.

    Encapsulates the title strip, the section's accent colours
    (derived from the theme's macro palette colour) and the standard
    inter-strip / body gap. Both the standalone macros image and the
    combined special-keys image render this composable directly.

    ``max_width`` is the layout budget the section may spend. The
    section runs a natural-width pre-pass internally so the standalone
    case (``wrap_content=True``) snugs to the longest macro's
    single-line width when it fits, falling back to the full budget
    when it doesn't (pills then wrap inside the table).
    ``wrap_content=False`` keeps the table at the full ``max_width``
    so the parent column gets the slot width it asked for; pills wrap
    inside as needed.

    ``scale`` is forwarded to the underlying :func:`MacroTable` so the
    chips / pills enlarge while the section title strip stays at the
    unscaled per-image size.
    """
    palette = ctx.theme.palette
    accent_fill = palette.macro_color
    accent_line = derive_accent_line(accent_fill)
    stripe_metrics = SectionStripeMetrics.from_ctx(ctx)

    if wrap_content:
        table_metrics = MacroMetrics.from_ctx(ctx, scale=scale)
        natural_widths = _macro_natural_widths(macros, metrics=table_metrics)
        longest_natural = max(natural_widths) if natural_widths else 0.0
        snug = 0.0 < longest_natural <= max_width
        content_width = longest_natural if snug else max_width
    else:
        content_width = max_width

    table = MacroTable(
        macros=macros,
        accent_fill=accent_fill,
        accent_line=accent_line,
        text_color=palette.text_color,
        content_width=content_width,
        scale=scale,
    )
    stripe_width = table.size.width if wrap_content else content_width
    inner = Column(
        [
            SectionStripe(
                title="MACROS",
                count=len(macros),
                width=stripe_width,
                accent_line=accent_line,
            ),
            table,
        ],
        gap=ctx.document_metrics.section_spacing,
        align="start",
    )
    return MetricsComponent(
        size=inner.size,
        draw_fn=inner.draw_fn,
        metrics=MacroSectionMetrics(rule_offset=stripe_metrics.rule_offset),
    )


__all__ = ["MacroSection"]
