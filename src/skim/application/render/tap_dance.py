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
from .legend import _legend_key_label
from .primitives import Column, MetricsComponent, Point, Size
from .render_context import RenderContext, TextStyle
from .rich_text import RichText, parse_into_spans
from .section_stripe import SectionStripe, SectionStripeMetrics
from .styling import derive_accent_line
from .text import Font

if TYPE_CHECKING:
    from skim.domain import SvalboardTapDance, SvalboardTargetKey


# ---------------------------------------------------------------------------
# Per-doc-width ratios — owned by this module so :class:`TapDanceMetrics`
# doesn't reach into the legacy ``_LegendGeometry``. Mirror the same
# ratios in ``legend.py`` (which still uses them for the overview's
# imperative path); when the overview migrates the legend copies retire.
# ---------------------------------------------------------------------------

_CHIP_WIDTH_RATIO = 56.0 / 1600.0
_CHIP_STROKE_WIDTH_RATIO = 1.2 / 1600.0
_CHIP_CORNER_RADIUS_RATIO = 4.0 / 1600.0
_CHIP_INNER_FONT_SIZE_RATIO = 12.0 / 1600.0
_CHIP_INNER_TEXT_BASELINE_OFFSET_RATIO = 0.5 / 1600.0
_NAME_GAP_RATIO = 10.0 / 1600.0
_NAME_FONT_SIZE_RATIO = 12.0 / 1600.0
_NAME_W_RATIO = 200.0 / 1600.0
_CELL_W_RATIO = 80.0 / 1600.0
_CELL_LABEL_FONT_SIZE_RATIO = 12.0 / 1600.0
_ROW_HEIGHT_RATIO = 22.0 / 1600.0
_COLUMN_LABEL_FONT_SIZE_RATIO = 9.0 / 1600.0
_COLUMN_LABEL_LETTER_SPACING_RATIO = 1.5 / 1600.0
# Universal table-spacing ratios — mirror :class:`DocumentMetrics`'
# computation so :meth:`for_doc_width` (used by tests that don't push
# a render context) produces values identical to what
# :meth:`from_ctx` returns. Production code reads the spacings
# from :class:`DocumentMetrics` via :meth:`from_ctx`.
_TABLE_HEADER_SPACING_RATIO = 12.0 / 1600.0
_TABLE_COL_SPACING_RATIO = 6.0 / 1600.0
_TABLE_ROW_SPACING_RATIO = 9.0 / 1600.0


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

    Owns every measurement the tap-dance composables read — chip /
    cell / row / column-header dimensions plus the title-strip
    column-label typography. The three universal table spacings come
    from :class:`DocumentMetrics` so every table-shaped composable in
    the image agrees on rhythm; the chip / cell / row ratios live on
    this class so the tap-dance composables don't reach into the
    legacy ``_LegendGeometry``.
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
    # Cells (one per variant: TAP / HOLD / DOUBLE-TAP / TAP & HOLD).
    # ``cell_w`` is the visible cell rectangle's width.
    cell_w: float
    cell_label_font_size: float
    # Rows
    row_height: float
    # Column-header text typography. The strip's *height* is
    # dynamic (text_height + table_header_spacing) and computed
    # locally inside :func:`TapDanceColumnHeader`.
    column_label_font_size: float
    column_label_letter_spacing: float
    # Universal table spacings — mirror :class:`DocumentMetrics`'
    # unscaled fields, but populated at the (possibly body-scaled)
    # doc width this metrics instance was built for so the values
    # scale together with everything else here.
    table_header_spacing: float
    table_col_spacing: float
    table_row_spacing: float

    @classmethod
    def from_ctx(cls, ctx: RenderContext, *, scale: float = 1.0) -> TapDanceMetrics:
        """Resolve from the active context's document metrics.

        ``scale`` multiplies the underlying doc-width so the body of a
        body-scaled image (e.g. the standalone tap-dances image, which
        uses ``BODY_SCALE``) renders larger chips/cells while the
        chrome stays at its unscaled per-image size.
        """
        doc_m = ctx.document_metrics
        w = doc_m.doc_width * scale
        return cls(
            chip_width=w * _CHIP_WIDTH_RATIO,
            chip_stroke_width=w * _CHIP_STROKE_WIDTH_RATIO,
            chip_corner_radius=w * _CHIP_CORNER_RADIUS_RATIO,
            chip_inner_font_size=w * _CHIP_INNER_FONT_SIZE_RATIO,
            chip_inner_text_baseline_offset=w * _CHIP_INNER_TEXT_BASELINE_OFFSET_RATIO,
            name_gap=w * _NAME_GAP_RATIO,
            name_font_size=w * _NAME_FONT_SIZE_RATIO,
            name_w=w * _NAME_W_RATIO,
            cell_w=w * _CELL_W_RATIO,
            cell_label_font_size=w * _CELL_LABEL_FONT_SIZE_RATIO,
            row_height=w * _ROW_HEIGHT_RATIO,
            column_label_font_size=w * _COLUMN_LABEL_FONT_SIZE_RATIO,
            column_label_letter_spacing=w * _COLUMN_LABEL_LETTER_SPACING_RATIO,
            table_header_spacing=doc_m.table_header_spacing * scale,
            table_col_spacing=doc_m.table_col_spacing * scale,
            table_row_spacing=doc_m.table_row_spacing * scale,
        )

    @classmethod
    def for_doc_width(cls, doc_width: float) -> TapDanceMetrics:
        """Convenience factory for tests / call sites without a context.

        Produces values identical to what :meth:`from_ctx` would when
        the active context's ``document_metrics.doc_width`` equals
        ``doc_width`` and ``scale=1.0``.
        """
        return cls(
            chip_width=doc_width * _CHIP_WIDTH_RATIO,
            chip_stroke_width=doc_width * _CHIP_STROKE_WIDTH_RATIO,
            chip_corner_radius=doc_width * _CHIP_CORNER_RADIUS_RATIO,
            chip_inner_font_size=doc_width * _CHIP_INNER_FONT_SIZE_RATIO,
            chip_inner_text_baseline_offset=doc_width * _CHIP_INNER_TEXT_BASELINE_OFFSET_RATIO,
            name_gap=doc_width * _NAME_GAP_RATIO,
            name_font_size=doc_width * _NAME_FONT_SIZE_RATIO,
            name_w=doc_width * _NAME_W_RATIO,
            cell_w=doc_width * _CELL_W_RATIO,
            cell_label_font_size=doc_width * _CELL_LABEL_FONT_SIZE_RATIO,
            row_height=doc_width * _ROW_HEIGHT_RATIO,
            column_label_font_size=doc_width * _COLUMN_LABEL_FONT_SIZE_RATIO,
            column_label_letter_spacing=doc_width * _COLUMN_LABEL_LETTER_SPACING_RATIO,
            table_header_spacing=doc_width * _TABLE_HEADER_SPACING_RATIO,
            table_col_spacing=doc_width * _TABLE_COL_SPACING_RATIO,
            table_row_spacing=doc_width * _TABLE_ROW_SPACING_RATIO,
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

    The cell IS its visible rectangle — ``cell_width`` wide and
    ``td_row_height`` tall (filled when ``content`` is a key,
    dashed-empty otherwise). ``cell_width`` defaults to
    ``metrics.cell_w`` (the per-doc-width geom value) so the
    natural sizing is preserved. Adjacent cells inside a row /
    column-header are spaced by ``metrics.table_col_spacing`` —
    the gap is the parent's concern, not the cell's, so a cell's
    reported size contains no leading/trailing padding.

    ``scale`` matches the convention :func:`TapDanceTable` uses so
    standalone callers can size individual cells consistently with the
    rest of the table.
    """
    metrics = TapDanceMetrics.from_ctx(ctx, scale=scale)
    cell_w = cell_width if cell_width is not None else metrics.cell_w
    row_h = metrics.row_height
    size = Size(cell_w, row_h)

    # Pre-build the optional key label as a :func:`RichText`. Cell
    # labels can carry Nerd Font tokens (icon glyphs alongside text),
    # so :func:`parse_into_spans` splits the input into properly-
    # styled spans — plain-text fragments use ``Font.FINGER_KEY``,
    # tokens become single-character spans on ``Font.SYMBOLS``.
    # The parser strips whitespace from text fragments so
    # :func:`RichText`'s default ``separator=" "`` puts exactly one
    # space between every adjacent pair without doubling up on input-
    # encoded whitespace.
    label_style = TextStyle(
        font=Font.FINGER_KEY,
        size=metrics.cell_label_font_size,
        color=text_color,
    )
    label_el = (
        RichText(
            spans=parse_into_spans(_legend_key_label(content), label_style),
            style=label_style,
            max_width=cell_w,
            text_anchor="middle",
            dominant_baseline="central",
        )
        if content is not None
        else None
    )

    def draw_at(d, origin):
        rect_x = origin.x
        rect_y = origin.y
        if label_el is None:
            d.append(
                draw.Rectangle(
                    x=rect_x,
                    y=rect_y,
                    width=cell_w,
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
                width=cell_w,
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
            rect_y + row_h / 2 + metrics.chip_inner_text_baseline_offset - label_el.size.height / 2,
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
    section. ``cell_width`` overrides each variant cell's visible
    width (used by the standalone tap-dances image to stretch the
    table); the inter-cell gap stays at ``metrics.table_col_spacing``.

    ``scale`` matches the convention :func:`TapDanceTable` uses so
    standalone callers can size individual rows consistently with the
    rest of the table; it's forwarded to the per-variant
    :func:`TapDanceCell` instances.
    """
    metrics = TapDanceMetrics.from_ctx(ctx, scale=scale)
    if name_column_width is None:
        name_column_width = metrics.name_w - metrics.chip_width
    cell_w = cell_width if cell_width is not None else metrics.cell_w
    col_spacing = metrics.table_col_spacing
    header_spacing = metrics.table_header_spacing

    cells_offset = metrics.chip_width + name_column_width
    # The chip-with-name acts as the row's leading "row header" and
    # ``table_header_spacing`` separates it from the row's content
    # (the variant cells) — same gap a column header uses to separate
    # itself from the data rows below.
    cells_start_x = cells_offset + header_spacing
    # Cells stack with ``table_col_spacing`` between them — same
    # rhythm the macro section uses between pills. Reported width
    # ends at the last cell's right edge (no trailing slack).
    width = cells_start_x + 4 * cell_w + 3 * col_spacing
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
    # span. The ``" "`` between the token and the id is stripped at
    # the parser; :func:`RichText`'s default ``separator=" "`` adds
    # the inter-span gap back uniformly.
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
        # Four variant cells, stacked with ``table_col_spacing``
        # between them. Pass ``scale`` down so the cells derive the
        # same scaled geometry the row was built against.
        variants = (td.tap, td.hold, td.double_tap, td.tap_then_hold)
        for i, variant in enumerate(variants):
            cell = TapDanceCell(
                content=variant,
                text_color=text_color,
                scale=scale,
                cell_width=cell_w,
            )
            cell.draw_at(d, Point(x + cells_start_x + i * (cell_w + col_spacing), y))

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

    The strip's height is dynamic: ``label_text_height +
    table_header_spacing``. Labels paint with their bbox top at the
    strip top; the explicit ``table_header_spacing`` below the text
    is what separates the column header from the first data row,
    matching the universal "header → content" gap used everywhere
    else in the table-shaped composables.

    ``scale`` matches the convention :func:`TapDanceTable` uses so
    the header strip stays sized in step with the rows below.
    """
    metrics = TapDanceMetrics.from_ctx(ctx, scale=scale)
    if name_column_width is None:
        name_column_width = metrics.name_w - metrics.chip_width
    cell_w = cell_width if cell_width is not None else metrics.cell_w
    col_spacing = metrics.table_col_spacing
    header_spacing = metrics.table_header_spacing

    # Match :func:`TapDanceRow`'s ``cells_start_x`` so the column
    # labels line up with the cells they label.
    cells_start_x = metrics.chip_width + name_column_width + header_spacing
    width = cells_start_x + 4 * cell_w + 3 * col_spacing

    # Pre-build each column label as an :func:`AdjustableText`. Plain
    # text — no Nerd Font tokens — so the single-style base is the
    # right layer (no need for ``RichText``). ``letter_spacing`` is
    # threaded through so the painted strip keeps the same tracking
    # the legacy ``draw.Text`` call applied. Painted with
    # ``dominant_baseline="text-before-edge"`` so the bbox top sits
    # at the painted ``y`` — that lets the strip height be exactly
    # ``text_height + table_header_spacing``.
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
            dominant_baseline="text-before-edge",
            letter_spacing=metrics.column_label_letter_spacing,
        )
        for label in column_labels
    ]
    text_height = max((el.size.height for el in column_label_els), default=0.0)
    height = text_height + header_spacing
    size = Size(width, height)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        for i, el in enumerate(column_label_els):
            cell_centre_x = x + cells_start_x + i * (cell_w + col_spacing) + cell_w / 2
            label_origin = Point(cell_centre_x - el.size.width / 2, y)
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

    Vertical layout: the column header strip sits at the top
    (carrying its own ``table_header_spacing`` of empty space below
    the label text), then each row is followed by
    ``table_row_spacing``. That trailing row-spacing keeps the
    table's reported height stable as rows are added.

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
    metrics = TapDanceMetrics.from_ctx(ctx, scale=scale)
    cell_w = cell_width if cell_width is not None else metrics.cell_w
    col_spacing = metrics.table_col_spacing
    # The cells block ends at the LAST cell's right edge — four
    # cells with three ``table_col_spacing`` gaps between them,
    # plus the leading ``table_header_spacing`` that separates the
    # row header (chip) from the cells. Matches
    # :func:`TapDanceRow`'s reported width math.
    cells_block_w = metrics.table_header_spacing + 4 * cell_w + 3 * col_spacing

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
    row_spacing = metrics.table_row_spacing
    body_h = header.size.height + len(rows) * (metrics.row_height + row_spacing)
    size = Size(width, body_h)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        header.draw_at(d, Point(x, y))
        cursor_y = y + header.size.height
        for row in rows:
            row.draw_at(d, Point(x, cursor_y))
            cursor_y += metrics.row_height + row_spacing

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
        gap=ctx.document_metrics.section_spacing,
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
    Body-scale is read from ``config.output.style.tap_dances_scale``
    (the CLI ``--tap-dances-scale`` flag updates that field upstream).
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
                scale=config.output.style.tap_dances_scale,
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
