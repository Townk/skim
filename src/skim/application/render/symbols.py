# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SYMBOLS section composables.

* :func:`SymbolEntry` — one row: a centred glyph cell + a left-aligned
  description.
* :func:`SymbolTable` — entries packed into a multi-column grid sized
  to fit a ``max_width`` budget.
* :func:`SymbolSection` — the ``SYMBOLS`` :func:`SectionStripe`
  followed by a :func:`SymbolTable`, laid out in a Column with the
  section's standard inter-strip / body gap.

The data layer that turns raw keycodes into :class:`SymbolLegendEntry`
rows lives in :mod:`section_data` (alongside the macro / tap-dance
data utilities).

The symbol legend's accent line is a fixed neutral gray rather than a
palette colour — symbols don't belong to either macros or tap-dances,
so the title strip stays visually neutral. ``column``-major flow is
the default and matches the historical legacy behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .adjustable_text import AdjustableText, measure_text_width
from .composable import Composable
from .primitives import Column, Component, MetricsComponent, Point, Size
from .render_context import RenderContext, TextStyle
from .rich_text import RichText
from .section_data import SymbolLegendEntry
from .section_stripe import SectionStripe, SectionStripeMetrics
from .text import Font

# ---------------------------------------------------------------------------
# Per-doc-width ratios — entry-row / glyph / description typography.
# Expressed as fractions of the document width so the symbols section
# stays visually proportional across canvas sizes.
# ---------------------------------------------------------------------------

_ENTRY_ROW_HEIGHT_RATIO = 20.0 / 1600.0
_SYMBOL_FONT_SIZE_RATIO = 13.0 / 1600.0
_DESC_FONT_SIZE_RATIO = 13.0 / 1600.0
_MIN_GLYPH_CELL_RATIO = 4.0 / 1600.0  # measurement floor for blank glyph cells

# Neutral accent — the SYMBOLS title strip is independent of any per-layer
# colour, so the rule and title text use a fixed gray.
_ACCENT_LINE = "#888888"

# Description text is rendered slightly faded so the glyph reads as the
# primary content of each row.
_DESC_OPACITY = 0.75

FlowDirection = Literal["row", "column"]
"""Where adjacent entries in the multi-column grid sit relative to each other.

* ``"row"`` — fill rows left-to-right (row-major). Adjacent indices
  sit in the same row, the next row starts when the current one fills.
* ``"column"`` — fill columns top-to-bottom (column-major; the
  default). Adjacent indices sit in the same column.
"""


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolSectionMetrics:
    """Metrics exposed by a built :func:`SymbolSection`.

    The single field is the section title strip's ``rule_offset`` —
    surfaced so the parent document doesn't need to import
    :class:`SectionStripeMetrics` just to compute the gap that
    should sit above and below the section.
    """

    rule_offset: float


@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolMetrics:
    """Sizing constants for the symbols composables.

    Owns the entry-level pixel metrics (row height, glyph / description
    font sizes, the glyph cell measurement floor). The four universal
    table spacings (``table_col_spacing`` between columns,
    ``table_row_spacing`` between rows, ``table_header_spacing``
    between the glyph cell and the description, ``section_spacing``
    between the title strip and the table) come from
    :class:`DocumentMetrics` so the symbols section participates in the
    same rhythm every other table-shaped composable uses.
    """

    # Universal table spacings — sourced from ``DocumentMetrics``.
    table_col_spacing: float
    table_header_spacing: float
    table_row_spacing: float

    # Symbol-entry specifics.
    entry_row_height: float
    symbol_font_size: float
    desc_font_size: float
    min_glyph_cell: float

    @classmethod
    def from_ctx(cls, ctx: RenderContext, *, scale: float = 1.0) -> SymbolMetrics:
        """Resolve from the active context's document metrics.

        ``scale`` multiplies the underlying doc-width so the body of a
        body-scaled image (the standalone symbols image, which uses
        ``BODY_SCALE``) renders larger glyphs / text while the chrome
        stays at its unscaled per-image size.
        """
        doc_m = ctx.document_metrics
        w = doc_m.doc_width * scale
        return cls(
            table_col_spacing=doc_m.table_col_spacing * scale,
            table_header_spacing=doc_m.table_header_spacing * scale,
            table_row_spacing=doc_m.table_row_spacing * scale,
            entry_row_height=w * _ENTRY_ROW_HEIGHT_RATIO,
            symbol_font_size=w * _SYMBOL_FONT_SIZE_RATIO,
            desc_font_size=w * _DESC_FONT_SIZE_RATIO,
            min_glyph_cell=w * _MIN_GLYPH_CELL_RATIO,
        )


# ---------------------------------------------------------------------------
# Symbol composables
# ---------------------------------------------------------------------------


def _measure_glyph_width(label: str, *, metrics: SymbolMetrics, color: str) -> float:
    """Width the glyph cell needs to render ``label`` exactly.

    Builds a throwaway :func:`RichText` with no width budget — the
    element reports its own natural size, so going through it keeps
    the column-width pre-pass identical to what the painted entry
    uses. Floors at ``min_glyph_cell`` so blank or whitespace-only
    labels never collapse the column.
    """
    style = TextStyle(font=Font.FINGER_KEY, size=metrics.symbol_font_size, color=color)
    natural = RichText(text=label, style=style).size.width
    return max(natural, metrics.min_glyph_cell)


@Composable(use_context=True)
def SymbolEntry(
    ctx,
    *,
    entry: SymbolLegendEntry,
    text_color: str,
    glyph_cell_width: float,
    scale: float = 1.0,
):
    """One symbol-legend row: glyph cell + description.

    The glyph cell is ``glyph_cell_width`` wide (passed in by the parent
    :func:`SymbolTable` so every entry's glyph centres at the same x);
    the description sits to the right, separated by
    ``table_header_spacing``. Reported width covers both. The glyph
    is rendered through :func:`RichText` so labels carrying Nerd Font
    tokens render with the right per-span fonts.
    """
    metrics = SymbolMetrics.from_ctx(ctx, scale=scale)

    glyph_style = TextStyle(
        font=Font.FINGER_KEY,
        size=metrics.symbol_font_size,
        weight=700,
        color=text_color,
    )
    glyph_el = RichText(
        text=entry.display_label,
        style=glyph_style,
        text_anchor="start",
        dominant_baseline="central",
    )
    desc_el = AdjustableText(
        text=entry.description,
        style=TextStyle(
            font=Font.FINGER_KEY,
            size=metrics.desc_font_size,
            color=text_color,
        ),
        opacity=_DESC_OPACITY,
        text_anchor="start",
        dominant_baseline="central",
    )

    width = glyph_cell_width + metrics.table_header_spacing + desc_el.size.width
    height = metrics.entry_row_height
    size = Size(width, height)

    def draw_at(d, origin):
        cy = origin.y + height / 2
        # Glyph centred horizontally inside the uniform glyph cell.
        glyph_origin = Point(
            origin.x + glyph_cell_width / 2 - glyph_el.size.width / 2,
            cy - glyph_el.size.height / 2,
        )
        glyph_el.draw_at(d, glyph_origin)
        # Description left-aligned immediately after the glyph cell.
        desc_origin = Point(
            origin.x + glyph_cell_width + metrics.table_header_spacing,
            cy - desc_el.size.height / 2,
        )
        desc_el.draw_at(d, desc_origin)

    return size, draw_at


@Composable(use_context=True)
def SymbolTable(
    ctx,
    *,
    entries: list[SymbolLegendEntry],
    text_color: str,
    max_width: float,
    wrap_content: bool = False,
    column_count: int | None = None,
    flow: FlowDirection = "column",
    scale: float = 1.0,
):
    """Multi-column grid of :func:`SymbolEntry` instances.

    The table never exceeds ``max_width``. ``wrap_content`` chooses
    between the two layout policies the canvas needs:

    * ``False`` (default) — fill the budget. Pick the most columns
      that fit at natural width; if column-major flow would leave
      trailing slots empty, snug ``col_count`` to the row count
      actually needed (e.g. 13 entries naturally fitting 10 cols
      → 2 rows → only 7 cols actually populated, so report 7 cols);
      then inflate each column slot so the painted grid spans
      ``max_width`` exactly. Use for sections sharing a parent
      column with a peer that drives the canvas width — the per-
      layer image's symbols section drops here.
    * ``True`` — snug to natural. Pick the most columns that fit
      and report the natural ``col_count * natural_entry_w + gaps``
      width with no inflation. Use for the standalone symbols image,
      where the canvas wraps the table's actual width.

    A positive ``column_count`` overrides the column-count search
    and forces that exact count. With ``wrap_content=True`` the
    table reports the natural width of those N columns; with
    ``wrap_content=False`` the columns inflate to fill ``max_width``.

    Per-entry width is uniform across the grid: widest glyph +
    ``table_header_spacing`` + widest description, plus any slack
    introduced by ``wrap_content=False``. Empty ``entries`` returns
    a zero-sized noop component.

    ``flow`` controls the index → cell mapping:

    * ``"column"`` (default) — column-major. Adjacent entries land in
      the same column; the next column starts when the current one
      fills. Visually keeps related entries (e.g. a numbered category)
      close together vertically.
    * ``"row"`` — row-major. Adjacent entries land in the same row.
    """
    metrics = SymbolMetrics.from_ctx(ctx, scale=scale)
    if not entries:
        size = Size(0.0, 0.0)

        def _noop(d, origin):
            del d, origin

        return size, _noop

    glyph_widths = [
        _measure_glyph_width(e.display_label, metrics=metrics, color=text_color) for e in entries
    ]
    desc_widths = [
        max(
            measure_text_width(e.description, Font.FINGER_KEY, metrics.desc_font_size),
            metrics.min_glyph_cell,
        )
        for e in entries
    ]
    max_glyph_w = max(glyph_widths)
    max_desc_w = max(desc_widths)
    natural_entry_w = max_glyph_w + metrics.table_header_spacing + max_desc_w

    n = len(entries)
    if column_count is not None:
        col_count = max(1, column_count)
    else:
        # The most columns that pack within ``max_width`` at the
        # natural per-entry width.
        col_count = max(
            1,
            int(
                (max_width + metrics.table_col_spacing)
                / (natural_entry_w + metrics.table_col_spacing)
            ),
        )
        if not wrap_content:
            # Snug to the row count actually needed so the
            # inflate-to-fill below doesn't spread visible content
            # thinly across trailing empty columns.
            # ``wrap_content=True`` keeps the natural ``col_count``
            # so the table snugs to that width verbatim.
            row_count_initial = (n + col_count - 1) // col_count
            col_count = (n + row_count_initial - 1) // row_count_initial

    total_gaps = max(0, col_count - 1) * metrics.table_col_spacing
    entry_w = (
        natural_entry_w
        if wrap_content
        else max(natural_entry_w, (max_width - total_gaps) / col_count)
    )
    row_count = (n + col_count - 1) // col_count

    entry_els: list[Component] = [
        SymbolEntry(
            entry=entry,
            text_color=text_color,
            glyph_cell_width=max_glyph_w,
            scale=scale,
        )
        for entry in entries
    ]

    width = col_count * entry_w + total_gaps
    height = (
        row_count * metrics.entry_row_height + max(0, row_count - 1) * metrics.table_row_spacing
    )
    size = Size(width, height)

    def draw_at(d, origin):
        for idx, el in enumerate(entry_els):
            if flow == "row":
                col = idx % col_count
                row = idx // col_count
            else:  # column-major
                col = idx // row_count
                row = idx % row_count
            cell_x = origin.x + col * (entry_w + metrics.table_col_spacing)
            cell_y = origin.y + row * (metrics.entry_row_height + metrics.table_row_spacing)
            el.draw_at(d, Point(cell_x, cell_y))

    return size, draw_at


@Composable(use_context=True)
def SymbolSection(
    ctx,
    *,
    entries: list[SymbolLegendEntry],
    max_width: float,
    wrap_content: bool = False,
    column_count: int | None = None,
    flow: FlowDirection = "column",
    scale: float = 1.0,
):
    """The SYMBOLS section — :func:`SectionStripe` + :func:`SymbolTable`.

    Encapsulates the title strip, the section's neutral accent colour
    and the standard inter-strip / body gap. ``max_width`` is the
    column-allocated budget. ``wrap_content`` chooses the layout
    policy and is forwarded to :func:`SymbolTable`:

    * ``False`` (default) — the section paints exactly ``max_width``
      wide, with the table balancing columns to fill the budget.
    * ``True`` — the table snugs to its natural width and the
      section reports that snug width so the parent canvas can wrap
      the section.

    ``column_count`` pins the table to that exact count.

    ``scale`` is forwarded to the underlying :func:`SymbolTable` so
    the entries enlarge while the section title strip stays at the
    unscaled per-image size.
    """
    palette = ctx.theme.palette
    stripe_metrics = SectionStripeMetrics.for_doc_width(ctx.config.output.layout.width)

    table = SymbolTable(
        entries=entries,
        text_color=palette.text_color,
        max_width=max_width,
        wrap_content=wrap_content,
        column_count=column_count,
        flow=flow,
        scale=scale,
    )
    stripe_width = table.size.width if wrap_content else max_width
    inner = Column(
        [
            SectionStripe(
                title="SYMBOLS",
                count=len(entries),
                width=stripe_width,
                accent_line=_ACCENT_LINE,
                # The standalone symbols image (``wrap_content=True``)
                # carries the ``N ENTRIES`` count for parity with the
                # macros / tap-dances images; the per-layer symbols
                # section (``wrap_content=False``) hides it so the
                # count doesn't compete with the keyboard for
                # attention.
                show_count=wrap_content,
            ),
            table,
        ],
        gap=ctx.document_metrics.section_spacing,
        align="start",
    )
    return MetricsComponent(
        size=inner.size,
        draw_fn=inner.draw_fn,
        metrics=SymbolSectionMetrics(rule_offset=stripe_metrics.rule_offset),
    )


__all__ = ["FlowDirection", "SymbolSection"]
