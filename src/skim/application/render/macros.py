# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The macros section composables and standalone-image entry point.

* :class:`MacroMetrics` — sizing constants for the macro rows. Owns
  every chip/pill/row pixel metric so the composables don't reach into
  the legacy ``_LegendGeometry``.
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
  standard inter-strip / body gap.
* :func:`macro_natural_widths` — pre-pass helper that reports each
  macro's natural single-line width; used by image entry points to
  decide whether to shrink the canvas to wrap content.
* :func:`draw_macros_image` — the standalone macros image entry point.
"""

from __future__ import annotations

from dataclasses import dataclass

import drawsvg as draw

from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import SvalboardMacro, SvalboardMacroActionKind, SvalboardTargetKey

from .adjustable_text import AdjustableText, measure_text_width
from .composable import Composable, render
from .legend import _flatten_macro_pills, all_macros, build_action_glyph
from .primitives import Column, Component, MetricsComponent, Point, Size
from .render_context import (
    RenderContext,
    TextStyle,
    current_render_context,
    using_render_context,
)
from .rich_text import RichText, parse_into_spans
from .section_stripe import SectionStripe, SectionStripeMetrics
from .styling import derive_accent_line
from .text import Font

# ---------------------------------------------------------------------------
# Per-doc-width ratios — owned by this module so the macros composables
# don't need to consult the legacy ``_LegendGeometry``. Values mirror
# the same ratios in ``legend.py`` (which still uses them for the
# overview's imperative path); when the overview migrates the legend
# copies retire and these stay.
# ---------------------------------------------------------------------------

_CHIP_WIDTH_RATIO = 56.0 / 1600.0
_CHIP_HEIGHT_RATIO = 22.0 / 1600.0
_CORNER_RADIUS_RATIO = 4.0 / 1600.0
_CHIP_STROKE_WIDTH_RATIO = 1.2 / 1600.0
_CHIP_INNER_FONT_SIZE_RATIO = 12.0 / 1600.0
_CHIP_INNER_TEXT_BASELINE_OFFSET_RATIO = 0.5 / 1600.0
_NAME_FONT_SIZE_RATIO = 13.0 / 1600.0
_NAME_GAP_RATIO = 10.0 / 1600.0
_RULE_INSET_RATIO = 0.5 / 1600.0
_RULE_STROKE_RATIO = 1.0 / 1600.0
_PILL_ROW_HEIGHT_RATIO = 22.0 / 1600.0
_PILL_HEIGHT_RATIO = 18.0 / 1600.0
_PILL_FONT_SIZE_RATIO = 10.0 / 1600.0
_PILL_PAD_X_RATIO = 8.0 / 1600.0
_PILL_ICON_WIDTH_RATIO = 6.0 / 1600.0
_PILL_ICON_TEXT_GAP_RATIO = 10.0 / 1600.0
_PILL_MIN_TEXT_WIDTH_RATIO = 8.0 / 1600.0
_PILL_MIN_TOTAL_WIDTH_RATIO = 28.0 / 1600.0


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
    image agrees on rhythm. The chip and pill ratios live on this
    class so the macros composables don't reach into the legacy
    ``_LegendGeometry``.
    """

    # Universal table spacings — sourced from ``DocumentMetrics``.
    table_col_spacing: float
    table_header_spacing: float
    table_row_spacing: float

    # Chip (the colored ID tag at the row header).
    chip_width: float
    chip_height: float
    chip_corner_radius: float
    chip_stroke_width: float
    chip_inner_font_size: float
    chip_inner_text_baseline_offset: float

    # Named-header extras (chip + name + horizontal rule).
    name_font_size: float
    name_gap: float
    rule_inset: float
    rule_stroke: float

    # Pills (action steps painted to the right of each chip).
    pill_row_height: float
    pill_height: float
    pill_corner_radius: float
    pill_font_size: float
    pill_pad_x: float
    pill_icon_width: float
    pill_icon_text_gap: float
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
        w = doc_m.doc_width * scale
        pad_x = w * _PILL_PAD_X_RATIO
        icon_w = w * _PILL_ICON_WIDTH_RATIO
        icon_text_gap = w * _PILL_ICON_TEXT_GAP_RATIO
        return cls(
            table_col_spacing=doc_m.table_col_spacing * scale,
            table_header_spacing=doc_m.table_header_spacing * scale,
            table_row_spacing=doc_m.table_row_spacing * scale,
            chip_width=w * _CHIP_WIDTH_RATIO,
            chip_height=w * _CHIP_HEIGHT_RATIO,
            chip_corner_radius=w * _CORNER_RADIUS_RATIO,
            chip_stroke_width=w * _CHIP_STROKE_WIDTH_RATIO,
            chip_inner_font_size=w * _CHIP_INNER_FONT_SIZE_RATIO,
            chip_inner_text_baseline_offset=w * _CHIP_INNER_TEXT_BASELINE_OFFSET_RATIO,
            name_font_size=w * _NAME_FONT_SIZE_RATIO,
            name_gap=w * _NAME_GAP_RATIO,
            rule_inset=w * _RULE_INSET_RATIO,
            rule_stroke=w * _RULE_STROKE_RATIO,
            pill_row_height=w * _PILL_ROW_HEIGHT_RATIO,
            pill_height=w * _PILL_HEIGHT_RATIO,
            pill_corner_radius=w * _CORNER_RADIUS_RATIO,
            pill_font_size=w * _PILL_FONT_SIZE_RATIO,
            pill_pad_x=pad_x,
            pill_icon_width=icon_w,
            pill_icon_text_gap=icon_text_gap,
            pill_min_text_width=w * _PILL_MIN_TEXT_WIDTH_RATIO,
            pill_min_total_width=w * _PILL_MIN_TOTAL_WIDTH_RATIO,
            pill_chrome_width=2 * pad_x + icon_w + icon_text_gap,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pill_width(label: str, *, metrics: MacroMetrics) -> float:
    """Compute the pill width that wraps ``label`` exactly.

    Mirrors what :func:`MacroPill` produces so wrap-detection
    (:func:`macro_natural_widths`) and the painted pills agree on
    width without instantiating composables. Walks the spans
    :func:`parse_into_spans` would emit for the label and sums each
    span's PIL-measured width at the pill's font size; ``Font.SYMBOLS``
    spans use the same path so glyph widths come out right too.
    """
    label_style = TextStyle(font=Font.FINGER_KEY, size=metrics.pill_font_size)
    spans = parse_into_spans(label, label_style)
    text_width = sum(
        measure_text_width(
            span.text,
            (span.style or label_style).font,
            (span.style or label_style).size,
        )
        for span in spans
    )
    text_width = max(text_width, metrics.pill_min_text_width)
    return max(metrics.pill_min_total_width, text_width + metrics.pill_chrome_width)


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
        spans=parse_into_spans(f"%%nf-md-script_text_play_outline; {macro_id}", label_style),
        style=label_style,
        text_anchor="start",
        dominant_baseline="central",
        separator="",
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

    pill_w = _pill_width(label, metrics=metrics)
    label_style = TextStyle(
        font=Font.FINGER_KEY,
        size=metrics.pill_font_size,
        color=text_color,
    )
    label_el = RichText(
        spans=parse_into_spans(label, label_style),
        style=label_style,
        text_anchor="start",
        dominant_baseline="central",
        separator="",
    )
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
        # Action glyph — icon centred at ``x + pill_pad_x`` so the
        # left padding from pill edge to icon centre = ``pill_pad_x``.
        d.append(
            build_action_glyph(
                kind,
                cx=x + metrics.pill_pad_x,
                cy=y + metrics.pill_row_height / 2,
                color=text_color,
                doc_width=doc_width,
            )
        )
        # Label — centred in the available text region:
        #   left  = x + pill_pad_x + icon_width/2 + icon_text_gap
        #   right = x + pill_w - pill_pad_x
        #   centre = x + (icon_width/2 + icon_text_gap + pill_w) / 2
        text_centre_x = x + (metrics.pill_icon_width / 2 + metrics.pill_icon_text_gap + pill_w) / 2
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
        # The text slot starts at ``chip_width + name_gap`` from the
        # row's left and ends at ``content_width``.
        name_max_width = max(0.0, content_width - metrics.chip_width - metrics.name_gap)
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
                x + metrics.chip_width + metrics.name_gap,
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
# Pre-pass helper
# ---------------------------------------------------------------------------


def macro_natural_widths(macros: list, *, scale: float = 1.0) -> list[float]:
    """Width each macro would render at if every pill sat on a single line.

    Used by image entry points to decide whether the canvas can shrink
    to wrap content. Mirrors what :func:`MacroPillRow` would lay out
    against an unbounded width: per-pill widths summed plus
    inter-pill ``table_col_spacing``, then offset by the chip indent.

    Reads the active :class:`RenderContext` so the values match what
    :func:`MacroTable` will lay out — caller doesn't pass ``doc_width``.
    """
    ctx = current_render_context()
    metrics = MacroMetrics.from_ctx(ctx, scale=scale)
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
    content_width: float,
    width: float | None = None,
    scale: float = 1.0,
):
    """The MACROS section — :func:`SectionStripe` + :func:`MacroTable`.

    Encapsulates the title strip, the section's accent colours
    (derived from the theme's macro palette colour) and the standard
    inter-strip / body gap. Both the standalone macros image and the
    combined special-keys image render this composable directly.

    ``content_width`` is the layout budget passed to :func:`MacroTable`
    for pill-wrap detection — pills wrap to extra lines when they
    don't fit. ``width`` sets the :func:`SectionStripe`'s extent
    (where the count text lands and where the rule ends); when
    ``None`` (standalone-image case) the stripe snugs to the table's
    actual width, when given (combined-image case) it spans the slot.

    ``scale`` is forwarded to the underlying :func:`MacroTable` so the
    chips / pills enlarge while the section title strip stays at the
    unscaled per-image size.
    """
    palette = ctx.theme.palette
    accent_fill = palette.macro_color
    accent_line = derive_accent_line(accent_fill)
    stripe_metrics = SectionStripeMetrics.for_doc_width(ctx.config.output.layout.width)

    table = MacroTable(
        macros=macros,
        accent_fill=accent_fill,
        accent_line=accent_line,
        text_color=palette.text_color,
        content_width=content_width,
        scale=scale,
    )
    stripe_width = width if width is not None else table.size.width
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


# ---------------------------------------------------------------------------
# Image entry point
# ---------------------------------------------------------------------------


def _resolve_title(config: SkimConfig) -> str:
    """Pick the keymap title to render in the top-left of the image.

    Lives at the entry-point layer (next to :func:`draw_macros_image`)
    rather than inside the document composable so the binding from
    config to the rendered title string sits at the boundary where
    config is consumed; the document composable just receives the
    final string. The other two image entry points
    (:func:`tap_dance.draw_tap_dances_image`,
    :func:`special_keys.draw_special_keys_image`) import from here so
    every standalone-image render goes through the same resolver.
    """
    if config.output.keymap_title:
        return config.output.keymap_title
    if config.keyboard.layers:
        first = config.keyboard.layers[0]
        return f"{first.variant or first.name} Layers Layout"
    return "Keymap Layout"


def draw_macros_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the standalone macros image."""
    # Local import — :mod:`keymap_document` lazy-imports from this
    # module, so importing it eagerly would create a cycle.
    from .keymap_document import KeymapMacroDocument

    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapMacroDocument(
                macros=all_macros(keymap.macros),
                title=_resolve_title(config),
                copyright=config.output.copyright,
            )
        )


__all__ = [
    "MacroChip",
    "MacroMetrics",
    "MacroPill",
    "MacroPillRow",
    "MacroRow",
    "MacroSection",
    "MacroSectionMetrics",
    "MacroTable",
    "draw_macros_image",
    "macro_natural_widths",
]
