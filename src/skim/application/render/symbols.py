# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable building blocks for the SYMBOLS section.

* :class:`SymbolMetrics` — sizing constants for the symbols composables.
* :func:`SymbolEntry` — one row: a centered glyph cell + a left-aligned
  description.
* :func:`SymbolTable` — entries packed into a multi-column grid sized to
  fit a ``max_width`` budget.
* :func:`SymbolSection` — the ``SYMBOLS`` :func:`SectionStripe` followed
  by a :func:`SymbolTable`, laid out in a Column with the section's
  standard inter-strip / body gap.
* :func:`draw_symbols_image` — the standalone symbols image entry point.

The symbol legend's accent line is a fixed neutral gray rather than a
palette colour — symbols don't belong to either macros or tap-dances,
so the title strip stays visually neutral. ``column``-major flow is
the default and matches the historical legacy behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import drawsvg as draw

from skim.data import KeycodeMappings, SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey

from .adjustable_text import AdjustableText, measure_text_width
from .composable import Composable
from .primitives import Column, Component, MetricsComponent, Point, Size
from .render_context import RenderContext, TextStyle, using_render_context
from .rich_text import RichText, parse_into_spans
from .section_stripe import SectionStripe, SectionStripeMetrics
from .symbol_legend import SymbolLegendEntry
from .text import Font

# ---------------------------------------------------------------------------
# Per-doc-width ratios — owned by this module so :class:`SymbolMetrics`
# stays self-contained. The ratios mirror the legacy ones in
# ``symbol_legend.py`` (still used by the per-layer / overview imperative
# path); when that legacy code retires the duplicates retire too.
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

    Walks the spans :func:`parse_into_spans` would emit so labels that
    carry Nerd Font tokens measure correctly (the parser swaps in
    :attr:`Font.SYMBOLS` for icon glyphs while plain-text fragments
    keep ``Font.FINGER_KEY``). Floors at ``min_glyph_cell`` so blank
    or whitespace-only labels never collapse the column.
    """
    style = TextStyle(font=Font.FINGER_KEY, size=metrics.symbol_font_size, color=color)
    spans = parse_into_spans(label, style)
    natural = sum(
        measure_text_width(
            span.text,
            (span.style or style).font,
            (span.style or style).size,
        )
        for span in spans
    )
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
        spans=parse_into_spans(entry.display_label, glyph_style),
        style=glyph_style,
        text_anchor="start",
        dominant_baseline="central",
        separator="",
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
    column_count: int | None = None,
    flow: FlowDirection = "column",
    scale: float = 1.0,
):
    """Multi-column grid of :func:`SymbolEntry` instances.

    When ``column_count`` is ``None`` (default), picks the largest
    column count that fits under ``max_width`` — same shape the legacy
    inline legend used. When a positive ``column_count`` is supplied,
    forces that exact count and reports the resulting natural width;
    callers that want the canvas to shrink to the table read
    ``size.width`` after the fact (the standalone symbols image does
    this — it's how the macros / tap-dances images already behave).

    Per-entry width is uniform across the grid: widest glyph +
    ``table_header_spacing`` + widest description. Adjacent columns
    are separated by ``table_col_spacing``; rows by
    ``table_row_spacing``. Empty ``entries`` returns a zero-sized
    noop component.

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
    entry_w = max_glyph_w + metrics.table_header_spacing + max_desc_w

    # The column-count formula treats one slot as ``entry_w + table_col_spacing``
    # and adds back the trailing ``table_col_spacing`` since the last column
    # has no right-side gap. ``max_width + table_col_spacing`` lets the
    # formula reduce cleanly. When the caller pinned ``column_count``, skip
    # the budget-fit search and use that value directly (clamped to >= 1).
    if column_count is not None:
        col_count = max(1, column_count)
    else:
        col_count = max(
            1,
            int((max_width + metrics.table_col_spacing) / (entry_w + metrics.table_col_spacing)),
        )
    n = len(entries)
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

    # Reported width snugs to the actual painted slots — useful when the
    # caller wants the title strip's rule to land at the rightmost column
    # rather than the full max_width budget.
    width = col_count * entry_w + max(0, col_count - 1) * metrics.table_col_spacing
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
    width: float | None = None,
    column_count: int | None = None,
    flow: FlowDirection = "column",
    scale: float = 1.0,
):
    """The SYMBOLS section — :func:`SectionStripe` + :func:`SymbolTable`.

    Encapsulates the title strip, the section's neutral accent colour
    and the standard inter-strip / body gap. ``max_width`` is the
    layout budget passed to :func:`SymbolTable` for column-count
    selection. ``width`` sets the :func:`SectionStripe`'s extent
    (where the count text lands and where the rule ends); when
    ``None`` the stripe snugs to the table's actual width, when given
    it spans the slot. ``column_count``, when set, forces the table
    to that exact column count and the stripe snugs to the resulting
    natural width (mirrors how the macros / tap-dances images shrink
    the canvas to their table's width).

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
        column_count=column_count,
        flow=flow,
        scale=scale,
    )
    stripe_width = width if width is not None else table.size.width
    inner = Column(
        [
            SectionStripe(
                title="SYMBOLS",
                count=len(entries),
                width=stripe_width,
                accent_line=_ACCENT_LINE,
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


# ---------------------------------------------------------------------------
# Standalone image entry point
# ---------------------------------------------------------------------------


def collect_symbol_entries(
    config: SkimConfig,
    raw_keymap: SvalboardKeymap[str] | None,
    keycode_mappings: KeycodeMappings | None,
) -> list[SymbolLegendEntry]:
    """Collect every symbol entry the keymap touches across all layers.

    Returns an empty list when ``raw_keymap`` or ``keycode_mappings``
    is unavailable. Honours
    ``output.style.show_transparent_fallthrough`` — when fall-through
    is on, the ⛛ entry is suppressed because the glyph never appears
    on any layer.
    """
    from .symbol_legend import collect_used_descriptions

    if raw_keymap is None or keycode_mappings is None:
        return []
    all_raw_keycodes: list[str] = []
    for qmk_idx in raw_keymap.layers:
        all_raw_keycodes.extend(k for k in raw_keymap.layers[qmk_idx] if k is not None)
    return collect_used_descriptions(
        all_raw_keycodes,
        raw_keymap,
        keycode_mappings,
        include_transparent=not config.output.style.show_transparent_fallthrough,
    )


def draw_symbols_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    entries: list[SymbolLegendEntry],
    *,
    scale: float | None = None,
) -> draw.Drawing:
    """Render the standalone symbols image from a pre-collected entry set.

    Caller is expected to gate on ``entries`` being non-empty (and on
    ``raw_keymap`` / ``keycode_mappings`` availability) — this entry
    point doesn't surface "skipping" warnings of its own. Use
    :func:`collect_symbol_entries` to build the entry set in the
    caller's preferred order.

    ``scale`` overrides the body-scale multiplier (the default is
    ``BODY_SCALE`` set inside :func:`KeymapSymbolDocument`); pass
    ``None`` to use that default.
    """
    # Local imports — :mod:`keymap_document` lazy-imports from this
    # module, so importing it eagerly would create a cycle.
    from .composable import render
    from .keymap_document import KeymapSymbolDocument
    from .macros import _resolve_title

    flow_str = config.output.style.symbol_legend_flow
    flow: FlowDirection = "row" if flow_str == "row" else "column"

    doc_kwargs: dict = {
        "entries": entries,
        "title": _resolve_title(config),
        "copyright": config.output.copyright,
        "flow": flow,
    }
    if scale is not None:
        doc_kwargs["scale"] = scale
    with using_render_context(RenderContext.build(config, keymap)):
        return render(KeymapSymbolDocument(**doc_kwargs))


__all__ = [
    "FlowDirection",
    "SymbolEntry",
    "SymbolMetrics",
    "SymbolSection",
    "SymbolSectionMetrics",
    "SymbolTable",
    "collect_symbol_entries",
    "draw_symbols_image",
]
