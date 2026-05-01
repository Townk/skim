# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable building blocks for the tap-dance section.

Five composables that nest:

* :func:`TapDanceCell` — one variant slot (``TAP``, ``HOLD``,
  ``DOUBLE-TAP``, ``TAP & HOLD``).
* :func:`TapDanceRow` — chip + optional name + four cells.
* :func:`TapDanceColumnHeader` — the strip of column labels above
  the rows.
* :func:`TapDanceTable` — column header + N rows.
* :func:`TapDanceSection` — a ``TAP-DANCE`` section title strip
  followed by a :func:`TapDanceTable`, laid out in a Column with the
  section's standard inter-strip / body gap. Both the standalone
  tap-dances image and the combined special-keys image render this
  composable directly.

Plus the section's chip-shape helper (``_filled_chip_path``), the
name-column-width resolver (``_resolve_name_column_width``) and the
standalone tap-dance image entry point :func:`draw_tap_dances_image`.

Tap-dance name rendering and truncation go through
:func:`AdjustableText`, so this module no longer carries its own
ellipsis-trim / text-measurement helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import drawsvg as draw

from .adjustable_text import AdjustableText, measure_text_width
from .composable import Composable
from .legend import _legend_key_label, _LegendGeometry
from .primitives import Column, MetricsComponent, Point, Size
from .render_context import TextStyle
from .rich_text import RichText, parse_into_spans
from .section_stripe import SectionStripe, SectionStripeMetrics
from .styling import derive_accent_line
from .text import Font

if TYPE_CHECKING:
    from skim.domain import SvalboardTapDance, SvalboardTargetKey


@dataclass(frozen=True, slots=True, kw_only=True)
class TapDanceSectionMetrics:
    """Metrics exposed by a built :func:`TapDanceSection`.

    The single field is the section title strip's ``rule_offset`` —
    surfaced so the parent document doesn't need to import
    :class:`SectionStripeMetrics` just to compute the gap that
    should sit above and below the section. Document composables
    use ``section.metrics.rule_offset * 0.5`` as the inter-sibling
    gap, matching the legacy positional-layout breathing constant.
    """

    rule_offset: float


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class TapDanceMetrics:
    """Sizing constants for the tap-dance composables.

    Owns every measurement the four tap-dance composables read —
    chip / cell / row / column-header dimensions plus the
    title-strip column-label typography. Built from a (possibly
    scaled) document width via :meth:`for_doc_width`.

    Currently delegates to the shared ``_LegendGeometry`` for the
    ratios so values stay aligned across the codebase; when the
    legacy legend module retires the ratios can move here directly.
    """

    # Chip (the colored tag with the keyboard-close icon + id)
    chip_width: float
    chip_stroke_width: float
    chip_corner_radius: float
    chip_inner_font_size: float
    chip_inner_text_baseline_offset: float
    name_gap: float
    name_font_size: float
    name_w: float
    # Cells (one per variant: TAP / HOLD / DOUBLE-TAP / TAP & HOLD)
    cell_w: float
    cell_inner_w: float
    cell_label_font_size: float
    # Rows
    row_height: float
    row_gap: float
    # Column-header strip + content layout
    header_height: float
    column_label_font_size: float
    column_label_letter_spacing: float
    column_label_baseline_offset: float
    row_content_indent_gap: float

    @classmethod
    def for_doc_width(cls, doc_width: float) -> TapDanceMetrics:
        geom = _LegendGeometry.for_doc_width(doc_width)
        return cls(
            chip_width=geom.tag_w,
            chip_stroke_width=geom.tag_stroke_width,
            chip_corner_radius=geom.pill_corner_radius,
            chip_inner_font_size=geom.tag_inner_font_size,
            chip_inner_text_baseline_offset=geom.tag_inner_text_baseline_offset,
            name_gap=geom.tag_name_gap,
            name_font_size=geom.td_name_font_size,
            name_w=geom.td_name_w,
            cell_w=geom.td_cell_w,
            cell_inner_w=geom.td_cell_inner_w,
            cell_label_font_size=geom.td_cell_label_font_size,
            row_height=geom.td_row_height,
            row_gap=geom.td_row_gap,
            header_height=geom.td_header_height,
            column_label_font_size=geom.macro_column_label_font_size,
            column_label_letter_spacing=geom.macro_column_label_letter_spacing,
            column_label_baseline_offset=geom.title_baseline_offset,
            row_content_indent_gap=geom.row_content_indent_gap,
        )


# ---------------------------------------------------------------------------
# Internal shape helpers
# ---------------------------------------------------------------------------


def _filled_chip_path(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
    round_right: bool,
    fill: str,
) -> draw.Path:
    """A filled rectangle with always-rounded left corners.

    The right corners round only when ``round_right`` is true. Used as
    the chip background under the rounded outlined stroke so the
    filled area follows the same rounded silhouette and never pokes
    past it at the corners.

    Built as an SVG ``<path>`` because ``<rect rx>`` rounds all four
    corners uniformly — we need the right edge to stay flush when the
    chip's outline extends across a name area beyond the chip.
    """
    tr = radius if round_right else 0.0
    br = radius if round_right else 0.0
    tl = radius
    bl = radius

    p = draw.Path(fill=fill)
    p.M(x + tl, y)
    p.L(x + width - tr, y)
    if tr:
        p.A(tr, tr, 0, 0, 1, x + width, y + tr)
    p.L(x + width, y + height - br)
    if br:
        p.A(br, br, 0, 0, 1, x + width - br, y + height)
    p.L(x + bl, y + height)
    if bl:
        p.A(bl, bl, 0, 0, 1, x, y + height - bl)
    p.L(x, y + tl)
    if tl:
        p.A(tl, tl, 0, 0, 1, x + tl, y)
    p.Z()
    return p


# ---------------------------------------------------------------------------
# Tap-dance composables
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def TapDanceCell(
    ctx,
    *,
    content: SvalboardTargetKey | None,
    text_color: str,
    scale: float = 1.0,
    cell_width: float | None = None,
):
    """One tap-dance variant cell (``TAP`` / ``HOLD`` / ``DOUBLE-TAP`` / ``TAP & HOLD``).

    The cell occupies a ``cell_width × td_row_height`` slot; the inner
    rect (filled when ``content`` is a key, dashed-empty otherwise) is
    centred horizontally within the slot. ``cell_width`` defaults to
    the scaled ``geom.td_cell_w`` so the natural geom-driven sizing is
    preserved. The inner rect's width tracks ``cell_width``
    proportionally so a stretched cell stretches its rect too — same
    rule the legacy helper applies.

    ``scale`` matches the convention :func:`TapDanceTable` uses so
    standalone callers can size individual cells consistently with the
    rest of the table.
    """
    metrics = TapDanceMetrics.for_doc_width(ctx.config.output.layout.width * scale)
    cell_w = cell_width if cell_width is not None else metrics.cell_w
    inner_w = metrics.cell_inner_w * (cell_w / metrics.cell_w)
    row_h = metrics.row_height
    size = Size(cell_w, row_h)
    rect_x_offset = (cell_w - inner_w) / 2.0

    # Pre-build the optional key label as a :func:`RichText`. Cell
    # labels can carry Nerd Font tokens (icon glyphs alongside text),
    # so :func:`parse_into_spans` splits the input into properly-
    # styled spans — plain-text fragments use ``Font.FINGER_KEY``,
    # tokens become single-character spans on ``Font.SYMBOLS``.
    # ``separator=""`` because the parser preserves any whitespace
    # already in the input string; we don't want an extra space
    # between adjacent fragments.
    label_style = TextStyle(
        font=Font.FINGER_KEY,
        size=metrics.cell_label_font_size,
        color=text_color,
    )
    label_el = (
        RichText(
            spans=parse_into_spans(_legend_key_label(content), label_style),
            style=label_style,
            max_width=inner_w,
            text_anchor="middle",
            dominant_baseline="central",
            separator="",
        )
        if content is not None
        else None
    )

    def draw_at(d, origin):
        rect_x = origin.x + rect_x_offset
        rect_y = origin.y
        if label_el is None:
            d.append(
                draw.Rectangle(
                    x=rect_x,
                    y=rect_y,
                    width=inner_w,
                    height=row_h,
                    rx=metrics.chip_corner_radius,
                    ry=metrics.chip_corner_radius,
                    fill="none",
                    stroke=text_color,
                    stroke_opacity=0.08,
                    stroke_dasharray="3 3",
                )
            )
            return
        d.append(
            draw.Rectangle(
                x=rect_x,
                y=rect_y,
                width=inner_w,
                height=row_h,
                rx=metrics.chip_corner_radius,
                ry=metrics.chip_corner_radius,
                fill="#FAFAF6",
                stroke=text_color,
                stroke_opacity=0.18,
            )
        )
        # Place the bbox top-left so the bbox vertical centre lands
        # at the inner rect's vertical centre + the historical
        # ``chip_inner_text_baseline_offset`` tweak (compensates for
        # SVG ``central`` baseline not matching the font's visual
        # centre — same magic offset the chip glyph and TD name use).
        label_origin = Point(
            rect_x,
            rect_y + row_h / 2 + metrics.chip_inner_text_baseline_offset
            - label_el.size.height / 2,
        )
        label_el.draw_at(d, label_origin)

    return size, draw_at


@Composable(use_context=True)
def TapDanceRow(
    ctx,
    *,
    td: SvalboardTapDance[SvalboardTargetKey],
    accent_fill: str,
    accent_line: str,
    text_color: str,
    scale: float = 1.0,
    name_column_width: float | None = None,
    cell_width: float | None = None,
):
    """One tap-dance row: chip [+ optional name] + four variant cells.

    The row's origin is the top-left of its bounding box (so a parent
    ``Column`` can simply stack rows). The legacy ``build_tap_dance_row``
    helper anchors at the row's vertical centre — its wrapper converts
    by passing ``origin = Point(x, center_y - row_height / 2)``.

    ``name_column_width`` defaults to ``td_name_w - tag_w`` so a chip
    with no name still leaves room consistent with the rest of the
    section. ``cell_width`` overrides each variant cell's slot width
    (used by the standalone tap-dances image to stretch the table).

    ``scale`` matches the convention :func:`TapDanceTable` uses so
    standalone callers can size individual rows consistently with the
    rest of the table; it's forwarded to the per-variant
    :func:`TapDanceCell` instances.
    """
    metrics = TapDanceMetrics.for_doc_width(ctx.config.output.layout.width * scale)
    if name_column_width is None:
        name_column_width = metrics.name_w - metrics.chip_width
    cell_w = cell_width if cell_width is not None else metrics.cell_w

    inner_w = metrics.cell_inner_w * (cell_w / metrics.cell_w)
    cells_offset = metrics.chip_width + name_column_width
    cells_start_x = cells_offset + metrics.row_content_indent_gap
    # Reported width tracks the last inner rect's right edge — each cell
    # slot reserves ``(cell_w - inner_w) / 2`` of empty padding on each
    # side of its inner rect, and the trailing slack on the right of the
    # last cell would otherwise stretch the bounding box past the
    # visible content (e.g. the section stripe rule would extend past
    # the rightmost cell rather than aligning with it).
    width = cells_start_x + 4 * cell_w - (cell_w - inner_w) / 2.0
    height = metrics.row_height
    size = Size(width, height)

    # Pre-build the optional name element so :func:`AdjustableText`
    # handles per-row truncation if the natural rendered width
    # overflows the column's text slot. The name area reserves
    # symmetric ``name_gap`` padding inside the chip outline (leading
    # and trailing), so the text slot is the column width minus those
    # two gaps.
    name_text_width = max(0.0, name_column_width - 2 * metrics.name_gap)
    name_el = (
        AdjustableText(
            text=td.name,
            style=TextStyle(font=Font.FINGER_KEY, size=metrics.name_font_size, color=text_color),
            max_width=name_text_width,
            text_anchor="start",
            dominant_baseline="central",
        )
        if td.name
        else None
    )

    # Pre-build the chip glyph as a :func:`RichText`. The label
    # carries a Nerd Font icon token (the ``keyboard_close`` glyph)
    # followed by the tap-dance id text; :func:`parse_into_spans`
    # splits it into a symbols-font icon span and a plain-text id
    # span. ``separator=""`` because the ``" "`` between the token
    # and the id is already encoded in the input string and comes
    # out as part of the trailing text span — no need to insert
    # another gap.
    chip_label_style = TextStyle(
        font=Font.FINGER_KEY,
        size=metrics.chip_inner_font_size,
        color="#FFF",
    )
    chip_glyph_el = RichText(
        spans=parse_into_spans(f"%%nf-md-keyboard_close; {td.id}", chip_label_style),
        style=chip_label_style,
        text_anchor="middle",
        dominant_baseline="central",
        separator="",
    )

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        cy = y + height / 2  # vertical centre of the row

        # Filled chip — rounds its corners to match the outlined rect that
        # sits on top of it (the outline always has rounded corners). When
        # the chip stands alone (no name), every corner rounds. When the
        # outline extends across a name area, only the chip's LEFT corners
        # round; the right edge is interior to the outline and stays flush
        # so it abuts the name area cleanly.
        d.append(
            _filled_chip_path(
                x=x,
                y=y,
                width=metrics.chip_width,
                height=height,
                radius=metrics.chip_corner_radius,
                round_right=not td.name,
                fill=accent_fill,
            )
        )
        # Outlined chip — extends across the name area when ``td.name`` is set.
        chip_outline_width = cells_offset if td.name else metrics.chip_width
        d.append(
            draw.Rectangle(
                x=x,
                y=y,
                width=chip_outline_width,
                height=height,
                rx=metrics.chip_corner_radius,
                ry=metrics.chip_corner_radius,
                fill="none",
                stroke=accent_line,
                stroke_width=metrics.chip_stroke_width,
            )
        )
        # Chip glyph (the keyboard-close icon + id) centred in the
        # chip. Position the bbox top-left so its centre lands at the
        # chip's centre + ``chip_inner_text_baseline_offset`` (same
        # central-baseline tweak the cell labels and TD name use).
        chip_origin = Point(
            x + metrics.chip_width / 2 - chip_glyph_el.size.width / 2,
            cy + metrics.chip_inner_text_baseline_offset - chip_glyph_el.size.height / 2,
        )
        chip_glyph_el.draw_at(d, chip_origin)
        # Optional name in the chip's outlined extension. The
        # ``AdjustableText`` element handles per-row truncation when the
        # natural rendered width overflows the column's text slot. The
        # bbox is positioned so its vertical centre lands at ``cy +
        # chip_inner_text_baseline_offset`` — same visual placement as
        # the previous direct ``draw.Text`` call (the offset compensates
        # for SVG ``central`` baseline not perfectly matching the
        # font's visual centre).
        if name_el is not None:
            name_origin = Point(
                x + metrics.chip_width + metrics.name_gap,
                cy - name_el.size.height / 2 + metrics.chip_inner_text_baseline_offset,
            )
            name_el.draw_at(d, name_origin)
        # Four variant cells. Pass ``scale`` down so the cells derive
        # the same scaled geometry the row was built against.
        variants = (td.tap, td.hold, td.double_tap, td.tap_then_hold)
        for i, variant in enumerate(variants):
            cell = TapDanceCell(
                content=variant,
                text_color=text_color,
                scale=scale,
                cell_width=cell_w,
            )
            cell.draw_at(d, Point(x + cells_start_x + i * cell_w, y))

    return size, draw_at


@Composable(use_context=True)
def TapDanceColumnHeader(
    ctx,
    *,
    text_color: str,
    scale: float = 1.0,
    name_column_width: float | None = None,
    cell_width: float | None = None,
):
    """The once-per-column ``TAP / HOLD / DOUBLE-TAP / TAP & HOLD`` strip.

    Sized to ``td_header_height`` so the strip's bounding box matches
    the vertical space the existing layout reserves for it; the four
    labels are baseline-aligned at ``title_baseline_offset`` from the
    top, mirroring the legacy ``build_tap_dance_column_header`` call.

    ``scale`` matches the convention :func:`TapDanceTable` uses so
    the header strip stays sized in step with the rows below.
    """
    metrics = TapDanceMetrics.for_doc_width(ctx.config.output.layout.width * scale)
    if name_column_width is None:
        name_column_width = metrics.name_w - metrics.chip_width
    cell_w = cell_width if cell_width is not None else metrics.cell_w
    inner_w = metrics.cell_inner_w * (cell_w / metrics.cell_w)

    cells_start_x = metrics.chip_width + name_column_width + metrics.row_content_indent_gap
    # See :func:`TapDanceRow` — the reported width matches the rows so
    # the section stripe rule aligns with the last inner rect.
    width = cells_start_x + 4 * cell_w - (cell_w - inner_w) / 2.0
    height = metrics.header_height
    size = Size(width, height)

    # Pre-build each column label as an :func:`AdjustableText`. Plain
    # text — no Nerd Font tokens — so the single-style base is the
    # right layer (no need for ``RichText``). ``letter_spacing`` is
    # threaded through so the painted strip keeps the same tracking
    # the legacy ``draw.Text`` call applied.
    column_label_style = TextStyle(
        font=Font.FINGER_KEY,
        size=metrics.column_label_font_size,
        color=text_color,
    )
    column_labels = ("TAP", "HOLD", "DOUBLE-TAP", "TAP & HOLD")
    column_label_els = [
        AdjustableText(
            text=label,
            style=column_label_style,
            text_anchor="middle",
            dominant_baseline="alphabetic",
            letter_spacing=metrics.column_label_letter_spacing,
        )
        for label in column_labels
    ]

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        # Each label paints with ``dominant_baseline="alphabetic"`` so
        # its baseline lands at the painted ``y``. We want every
        # column's baseline at ``y + column_label_baseline_offset`` —
        # the SVG y for an alphabetic-baseline element equals the
        # baseline directly, so the bbox-top origin must be at
        # ``baseline_y - bbox_height``.
        for i, el in enumerate(column_label_els):
            cell_centre_x = x + cells_start_x + i * cell_w + cell_w / 2
            label_origin = Point(
                cell_centre_x - el.size.width / 2,
                y + metrics.column_label_baseline_offset - el.size.height,
            )
            el.draw_at(d, label_origin)

    return size, draw_at


@Composable(use_context=True)
def TapDanceTable(
    ctx,
    *,
    tap_dances: list[SvalboardTapDance[SvalboardTargetKey]],
    accent_fill: str,
    accent_line: str,
    text_color: str,
    scale: float = 1.0,
    name_column_width: float | None = None,
    cell_width: float | None = None,
    max_width: float | None = None,
):
    """The full tap-dance body: column header strip + N tap-dance rows.

    Vertical layout matches the legacy ``_draw_td_column`` helper
    exactly — the column header sits flush at the top (no gap before
    the first row) and each row is followed by ``td_row_gap``,
    including the trailing gap after the last row. That trailing gap
    keeps :func:`TapDanceTable.size.height` consistent with
    :func:`legend.tap_dance_section_height`.

    ``scale`` multiplies the doc-width the table's geometry is built
    against — the standalone tap-dances image passes ``1.5`` so chips,
    cells, paddings and the column header strip render larger than
    they would in an inline appearance, leaving the surrounding title
    and footer at their unscaled sizes.

    When ``max_width`` is supplied (and ``name_column_width`` is not
    pinned by the caller) the name column is sized dynamically so the
    table never overflows that budget:

      1. The base layout is "no name area" — chip flush against the
         four variant cells.
      2. If at least one tap-dance has a name, measure the longest one
         and grow the name column to fit it, shifting the cell block
         right.
      3. If the longest natural name doesn't fit even when the cell
         block sits flush against the right edge of ``max_width``, the
         name column is capped at the maximum room available; per-row
         ellipsis truncation of any names that still overflow happens
         inside :func:`AdjustableText` at render time.

    When ``max_width`` is ``None`` the legacy behaviour is preserved:
    a caller-supplied ``name_column_width`` wins, otherwise the column
    is the geom-derived ``td_name_w - tag_w`` when at least one TD has
    a name and ``0`` when none do.
    """
    metrics = TapDanceMetrics.for_doc_width(ctx.config.output.layout.width * scale)
    cell_w = cell_width if cell_width is not None else metrics.cell_w
    inner_w = metrics.cell_inner_w * (cell_w / metrics.cell_w)
    # The cells block ends at the LAST inner rect's right edge — the
    # trailing slack in the last cell slot is excluded so the budget
    # math agrees with :func:`TapDanceRow`'s reported ``size.width``.
    cells_block_w = metrics.row_content_indent_gap + 4 * cell_w - (cell_w - inner_w) / 2.0

    # Resolve the name column width. Three branches:
    #
    #   * caller-pinned width (``name_column_width`` supplied) — pass
    #     through as-is.
    #   * ``max_width`` budget given — measure names and pick the
    #     tightest column that fits the longest, capped at the budget.
    #   * neither — fall back to the metrics-derived legacy default.
    if name_column_width is not None:
        resolved_name_column_width = name_column_width
    elif max_width is not None:
        resolved_name_column_width = _resolve_name_column_width(
            tap_dances=tap_dances,
            metrics=metrics,
            cells_block_w=cells_block_w,
            max_width=max_width,
        )
    else:
        resolved_name_column_width = (
            metrics.name_w - metrics.chip_width if any(td.name for td in tap_dances) else 0.0
        )

    header = TapDanceColumnHeader(
        text_color=text_color,
        scale=scale,
        name_column_width=resolved_name_column_width,
        cell_width=cell_width,
    )
    rows = [
        TapDanceRow(
            td=td,
            accent_fill=accent_fill,
            accent_line=accent_line,
            text_color=text_color,
            scale=scale,
            name_column_width=resolved_name_column_width,
            cell_width=cell_width,
        )
        for td in tap_dances
    ]

    width = max(header.size.width, *(row.size.width for row in rows)) if rows else header.size.width
    body_h = metrics.header_height + len(rows) * (metrics.row_height + metrics.row_gap)
    size = Size(width, body_h)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        header.draw_at(d, Point(x, y))
        cursor_y = y + metrics.header_height
        for row in rows:
            row.draw_at(d, Point(x, cursor_y))
            cursor_y += metrics.row_height + metrics.row_gap

    return size, draw_at


def _resolve_name_column_width(
    *,
    tap_dances: list[SvalboardTapDance[SvalboardTargetKey]],
    metrics: TapDanceMetrics,
    cells_block_w: float,
    max_width: float,
) -> float:
    """Compute the dynamic name column width.

    Implements the sizing rule documented on :func:`TapDanceTable`:
    measure each name, give the longest the smallest column that fits
    it, capped at the available budget. Per-row ellipsis truncation
    of names that still overflow the capped column is handled inside
    :func:`AdjustableText` at render time, not here.

    The name area reserves SYMMETRIC padding inside the chip outline —
    a leading gap between the chip and the name text, and a matching
    trailing gap between the name text and the outline's right edge.
    Without the trailing gap the rightmost glyph reads as "drawn on
    top" of the chip's rounded right border.
    """
    named = [td for td in tap_dances if td.name]
    if not named:
        return 0.0

    name_font_size = metrics.name_font_size
    leading_gap = metrics.name_gap
    trailing_gap = leading_gap  # symmetric padding inside the chip outline
    # Tap-dance names are plain text (no Nerd Font tokens), so the
    # single-style ``measure_text_width`` matches what the rendered
    # ``AdjustableText`` paints. Routes through the canonical
    # measurement primitive in :mod:`adjustable_text` rather than
    # :class:`Label.measure_rendered_width` directly.
    longest_natural = max(
        measure_text_width(td.name or "", Font.FINGER_KEY, name_font_size) for td in named
    )

    # The name area reserves leading + text + trailing inside the chip
    # outline. Solve for the text width that keeps the table — chip,
    # name area, indent gap, four cells — within ``max_width``.
    available_for_text = max(
        0.0,
        max_width - metrics.chip_width - leading_gap - trailing_gap - cells_block_w,
    )
    name_text_width = min(longest_natural, available_for_text)
    return leading_gap + name_text_width + trailing_gap


# ---------------------------------------------------------------------------
# TAP-DANCE section composable
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def TapDanceSection(
    ctx,
    *,
    tap_dances: list[SvalboardTapDance[SvalboardTargetKey]],
    width: float | None = None,
    scale: float = 1.0,
    name_column_width: float | None = None,
    max_width: float | None = None,
):
    """The TAP-DANCE section — :func:`SectionStripe` + :func:`TapDanceTable`.

    Encapsulates the title strip, the section's accent colours
    (derived from the theme's tap-dance palette colour) and the
    standard inter-strip / body gap. Both the standalone tap-dances
    image and the combined special-keys image render this composable
    directly.

    ``width`` is the section's slot width — it sets the
    :func:`SectionStripe`'s extent (where the count text lands and
    where the rule ends). When ``None`` (standalone-image case) the
    stripe snugs to the table's natural width so the rule lines up
    with the rightmost cell. When given (combined-image case) the
    stripe spans the slot, even if the table is narrower.

    ``scale`` is forwarded to the underlying :func:`TapDanceTable` so
    the chips / cells enlarge while the section title strip stays at
    the unscaled per-image size. ``name_column_width`` and
    ``max_width`` pass through too so the combined image can pin a
    fixed column and the standalone image can cap the table at the
    canvas budget.
    """
    palette = ctx.theme.palette
    accent_line = derive_accent_line(palette.tap_dance_color)
    stripe_metrics = SectionStripeMetrics.for_doc_width(ctx.config.output.layout.width)

    table = TapDanceTable(
        tap_dances=tap_dances,
        accent_fill=palette.tap_dance_color,
        accent_line=accent_line,
        text_color=palette.text_color,
        scale=scale,
        name_column_width=name_column_width,
        max_width=max_width,
    )
    stripe_width = width if width is not None else table.size.width
    inner = Column(
        [
            SectionStripe(
                title="TAP-DANCE",
                count=len(tap_dances),
                width=stripe_width,
                accent_line=accent_line,
            ),
            table,
        ],
        gap=2 * stripe_metrics.title_baseline_offset,
        align="start",
    )
    return MetricsComponent(
        size=inner.size,
        draw_fn=inner.draw_fn,
        metrics=TapDanceSectionMetrics(rule_offset=stripe_metrics.rule_offset),
    )


# ---------------------------------------------------------------------------
# Standalone image entry point
# ---------------------------------------------------------------------------


def draw_tap_dances_image(config, keymap):
    """Render the standalone tap-dances image.

    Reduces to: build a :func:`KeymapTapDanceDocument`, hand it to
    :func:`render`. All the table sizing, name-column resolution,
    canvas-shrink and chrome assembly live inside the composable.
    """
    # Local imports — :mod:`keymap_document` lazy-imports from this
    # module, so importing it eagerly would create a cycle.
    # ``_resolve_title`` lives next to :func:`draw_macros_image` since
    # it's an entry-point concern (config → title binding) shared by
    # every standalone-image entry point.
    from .composable import render
    from .keymap_document import KeymapTapDanceDocument
    from .legend import all_tap_dances
    from .macros import _resolve_title
    from .render_context import RenderContext, using_render_context

    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapTapDanceDocument(
                tap_dances=all_tap_dances(keymap.tap_dances),
                title=_resolve_title(config),
                copyright=config.output.copyright,
            )
        )


__all__ = [
    "TapDanceCell",
    "TapDanceColumnHeader",
    "TapDanceRow",
    "TapDanceSection",
    "TapDanceSectionMetrics",
    "TapDanceTable",
    "draw_tap_dances_image",
]
