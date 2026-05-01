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

Plus the section's text-measurement and chip-shape helpers
(``_truncate_with_ellipsis``, ``_filled_chip_path``,
``_resolve_name_column``) and the standalone tap-dance image entry
point :func:`draw_tap_dances_image`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import drawsvg as draw

from .composable import Column, Composable, Point, Size
from .legend import _legend_key_label, _LegendGeometry
from .section_stripe import SectionStripe
from .styling import derive_accent_line
from .text import Font, Label

if TYPE_CHECKING:
    from skim.domain import SvalboardTapDance, SvalboardTargetKey


# ---------------------------------------------------------------------------
# Text measurement helpers
# ---------------------------------------------------------------------------

# Single character used for ellipsis truncation. Kept as a module-level
# constant so the measurement helper and the truncator agree on the same
# glyph (PIL's ``getlength`` is sensitive to the exact character).
_ELLIPSIS = "…"


def _measure_text_width(text: str, font_size: float) -> float:
    """Rendered width of ``text`` at ``font_size`` using the FINGER_KEY font.

    Goes through :meth:`Label.measure_rendered_width` — the canonical
    "measure as painted" helper, shared with the symbol legend. That
    path skips the upper-casing that :meth:`Label.measure_width`
    applies for keymap key labels (which DO render in caps) and so
    matches the mixed-case glyph run an SVG ``<text>`` element
    actually paints for tap-dance names.
    """
    if not text:
        return 0.0
    return Label(text, Font.FINGER_KEY, text_color="#000").measure_rendered_width(
        int(round(max(font_size, 1.0)))
    )


def _truncate_with_ellipsis(text: str, font_size: float, max_width: float) -> str:
    """Trim ``text`` so its rendered width fits inside ``max_width``.

    When the natural rendered width already fits, ``text`` is returned
    unchanged. Otherwise the longest prefix that — once an ellipsis is
    appended — still fits within ``max_width`` is selected via binary
    search. When ``max_width`` is so tight that not even the ellipsis
    fits, the ellipsis is returned alone.
    """
    if max_width <= 0 or not text:
        return ""
    natural = _measure_text_width(text, font_size)
    if natural <= max_width:
        return text
    ellipsis_w = _measure_text_width(_ELLIPSIS, font_size)
    if ellipsis_w >= max_width:
        return _ELLIPSIS
    target = max_width - ellipsis_w
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _measure_text_width(text[:mid], font_size) <= target:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + _ELLIPSIS


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
    geom = _LegendGeometry.for_doc_width(ctx.config.output.layout.width * scale)
    use_system_fonts = ctx.config.output.style.use_system_fonts
    cell_w = cell_width if cell_width is not None else geom.td_cell_w
    inner_w = geom.td_cell_inner_w * (cell_w / geom.td_cell_w)
    row_h = geom.td_row_height
    size = Size(cell_w, row_h)
    rect_x_offset = (cell_w - inner_w) / 2.0

    def draw_at(d, origin):
        rect_x = origin.x + rect_x_offset
        rect_y = origin.y
        if content is None:
            d.append(
                draw.Rectangle(
                    x=rect_x,
                    y=rect_y,
                    width=inner_w,
                    height=row_h,
                    rx=geom.pill_corner_radius,
                    ry=geom.pill_corner_radius,
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
                rx=geom.pill_corner_radius,
                ry=geom.pill_corner_radius,
                fill="#FAFAF6",
                stroke=text_color,
                stroke_opacity=0.18,
            )
        )
        d.append(
            Label(
                _legend_key_label(content),
                font=Font.FINGER_KEY,
                text_color=text_color,
                text_anchor="middle",
                dominant_baseline="central",
            ).build_text(
                x=rect_x + inner_w / 2,
                y=rect_y + row_h / 2 + geom.tag_inner_text_baseline_offset,
                font_size=geom.td_cell_label_font_size,
                use_system_fonts=use_system_fonts,
            )
        )

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
    geom = _LegendGeometry.for_doc_width(ctx.config.output.layout.width * scale)
    use_system_fonts = ctx.config.output.style.use_system_fonts
    if name_column_width is None:
        name_column_width = geom.td_name_w - geom.tag_w
    cell_w = cell_width if cell_width is not None else geom.td_cell_w

    inner_w = geom.td_cell_inner_w * (cell_w / geom.td_cell_w)
    cells_offset = geom.tag_w + name_column_width
    cells_start_x = cells_offset + geom.row_content_indent_gap
    # Reported width tracks the last inner rect's right edge — each cell
    # slot reserves ``(cell_w - inner_w) / 2`` of empty padding on each
    # side of its inner rect, and the trailing slack on the right of the
    # last cell would otherwise stretch the bounding box past the
    # visible content (e.g. the section stripe rule would extend past
    # the rightmost cell rather than aligning with it).
    width = cells_start_x + 4 * cell_w - (cell_w - inner_w) / 2.0
    height = geom.td_row_height
    size = Size(width, height)

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
                width=geom.tag_w,
                height=height,
                radius=geom.pill_corner_radius,
                round_right=not td.name,
                fill=accent_fill,
            )
        )
        # Outlined chip — extends across the name area when ``td.name`` is set.
        chip_outline_width = cells_offset if td.name else geom.tag_w
        d.append(
            draw.Rectangle(
                x=x,
                y=y,
                width=chip_outline_width,
                height=height,
                rx=geom.pill_corner_radius,
                ry=geom.pill_corner_radius,
                fill="none",
                stroke=accent_line,
                stroke_width=geom.tag_stroke_width,
            )
        )
        # Chip glyph (the keyboard-close icon + id) centred in the chip.
        chip_label_text = f"%%nf-md-keyboard_close; {td.id}"
        d.append(
            Label(
                chip_label_text,
                Font.FINGER_KEY,
                text_color="#FFF",
                background_color=accent_fill,
                text_anchor="middle",
                dominant_baseline="central",
            ).build_text(
                x + geom.tag_w / 2,
                cy + geom.tag_inner_text_baseline_offset,
                geom.tag_inner_font_size,
                use_system_fonts,
            )
        )
        # Optional name in the chip's outlined extension. Rendered at the
        # bundled Roboto Regular weight (no ``font_weight`` attribute) so the
        # painted glyph run matches what :func:`_measure_text_width` reports
        # via PIL — requesting weight 500 would synthesize a slightly
        # heavier face since only Regular / Black / Thin are embedded, and
        # PIL would then under-measure the rendered run.
        if td.name:
            d.append(
                draw.Text(
                    td.name,
                    x=x + geom.tag_w + geom.tag_name_gap,
                    y=cy + geom.tag_inner_text_baseline_offset,
                    font_size=geom.td_name_font_size,
                    text_anchor="start",
                    dominant_baseline="central",
                    font_family="'Roboto', sans-serif",
                    fill=text_color,
                )
            )
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
    geom = _LegendGeometry.for_doc_width(ctx.config.output.layout.width * scale)
    if name_column_width is None:
        name_column_width = geom.td_name_w - geom.tag_w
    cell_w = cell_width if cell_width is not None else geom.td_cell_w
    inner_w = geom.td_cell_inner_w * (cell_w / geom.td_cell_w)

    cells_start_x = geom.tag_w + name_column_width + geom.row_content_indent_gap
    # See :func:`TapDanceRow` — the reported width matches the rows so
    # the section stripe rule aligns with the last inner rect.
    width = cells_start_x + 4 * cell_w - (cell_w - inner_w) / 2.0
    height = geom.td_header_height
    size = Size(width, height)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        text_y = y + geom.title_baseline_offset
        for i, label in enumerate(("TAP", "HOLD", "DOUBLE-TAP", "TAP & HOLD")):
            d.append(
                draw.Text(
                    label,
                    x=x + cells_start_x + i * cell_w + cell_w / 2,
                    y=text_y,
                    font_size=geom.macro_column_label_font_size,
                    fill=text_color,
                    letter_spacing=geom.macro_column_label_letter_spacing,
                    text_anchor="middle",
                    font_family="'Roboto', sans-serif",
                )
            )

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
         name column is capped at the maximum room available and any
         names that still overflow that cap are truncated with an
         ellipsis (``"…"``).

    When ``max_width`` is ``None`` the legacy behaviour is preserved:
    a caller-supplied ``name_column_width`` wins, otherwise the column
    is the geom-derived ``td_name_w - tag_w`` when at least one TD has
    a name and ``0`` when none do.
    """
    geom = _LegendGeometry.for_doc_width(ctx.config.output.layout.width * scale)
    cell_w = cell_width if cell_width is not None else geom.td_cell_w
    inner_w = geom.td_cell_inner_w * (cell_w / geom.td_cell_w)
    # The cells block ends at the LAST inner rect's right edge — the
    # trailing slack in the last cell slot is excluded so the budget
    # math agrees with :func:`TapDanceRow`'s reported ``size.width``.
    cells_block_w = geom.row_content_indent_gap + 4 * cell_w - (cell_w - inner_w) / 2.0

    # Resolve name column width and compute possibly-truncated display
    # names. Three branches:
    #
    #   * caller-pinned width (``name_column_width`` supplied) — pass
    #     through as-is, no truncation.
    #   * ``max_width`` budget given — measure names and pick the
    #     tightest column that fits the longest, capped at the budget.
    #   * neither — fall back to the geom-derived legacy default.
    if name_column_width is not None:
        resolved_name_column_width = name_column_width
        adjusted_tds = list(tap_dances)
    elif max_width is not None:
        resolved_name_column_width, adjusted_tds = _resolve_name_column(
            tap_dances=tap_dances,
            geom=geom,
            cells_block_w=cells_block_w,
            max_width=max_width,
        )
    else:
        resolved_name_column_width = (
            geom.td_name_w - geom.tag_w if any(td.name for td in tap_dances) else 0.0
        )
        adjusted_tds = list(tap_dances)

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
        for td in adjusted_tds
    ]

    width = max(header.size.width, *(row.size.width for row in rows)) if rows else header.size.width
    body_h = geom.td_header_height + len(rows) * (geom.td_row_height + geom.td_row_gap)
    size = Size(width, body_h)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        header.draw_at(d, Point(x, y))
        cursor_y = y + geom.td_header_height
        for row in rows:
            row.draw_at(d, Point(x, cursor_y))
            cursor_y += geom.td_row_height + geom.td_row_gap

    return size, draw_at


def _resolve_name_column(
    *,
    tap_dances: list[SvalboardTapDance[SvalboardTargetKey]],
    geom: _LegendGeometry,
    cells_block_w: float,
    max_width: float,
) -> tuple[float, list[SvalboardTapDance[SvalboardTargetKey]]]:
    """Compute the dynamic name column width and any truncated names.

    Implements the sizing rule documented on :func:`TapDanceTable`:
    measure each name, give the longest the smallest column that fits
    it, cap at the available budget, and truncate any names that still
    overflow.

    The name area reserves SYMMETRIC padding inside the chip outline —
    a leading gap between the chip and the name text, and a matching
    trailing gap between the name text and the outline's right edge.
    Without the trailing gap the rightmost glyph reads as "drawn on
    top" of the chip's rounded right border.

    Returns ``(name_column_width, adjusted_tap_dances)`` — adjusted
    TDs have their ``name`` field replaced with a truncated version
    when they would have overflowed; untouched otherwise.
    """
    named = [td for td in tap_dances if td.name]
    if not named:
        return 0.0, list(tap_dances)

    name_font_size = geom.td_name_font_size
    leading_gap = geom.tag_name_gap
    trailing_gap = leading_gap  # symmetric padding inside the chip outline
    natural = {td.id: _measure_text_width(td.name or "", name_font_size) for td in named}
    longest_natural = max(natural.values())

    # The name area reserves leading + text + trailing inside the chip
    # outline. Solve for the text width that keeps the table — chip,
    # name area, indent gap, four cells — within ``max_width``.
    available_for_text = max(
        0.0,
        max_width - geom.tag_w - leading_gap - trailing_gap - cells_block_w,
    )

    if longest_natural <= available_for_text:
        # All names fit at their natural width.
        name_text_width = longest_natural
        adjusted = list(tap_dances)
    else:
        # Longest name doesn't fit even at the right-most table position;
        # cap the name area at the available budget and truncate any
        # names that still exceed it.
        name_text_width = available_for_text
        adjusted = [
            replace(td, name=_truncate_with_ellipsis(td.name, name_font_size, name_text_width))
            if td.name and natural[td.id] > name_text_width
            else td
            for td in tap_dances
        ]

    name_column_width = leading_gap + name_text_width + trailing_gap
    return name_column_width, adjusted


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
    geom = _LegendGeometry.for_doc_width(ctx.config.output.layout.width)

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
        gap=2 * geom.title_baseline_offset,
        align="start",
    )
    return inner.size, inner.draw_at


# ---------------------------------------------------------------------------
# Standalone image entry point
# ---------------------------------------------------------------------------


def draw_tap_dances_image(config, keymap):
    """Render the standalone tap-dances image.

    Builds the table via the :func:`TapDanceTable` composable with the
    canvas content width as the budget — the table either snugly wraps
    its content (and the canvas shrinks to match) or stretches to the
    budget and truncates the longest names with ``"…"`` when they
    can't fit.
    """
    # Local imports — avoid pulling rendering siblings at module load
    # time (and avoid a hard dep on the standalone-image stack from
    # the per-component composables).
    from .composable import Spacer
    from .keymap_document import BODY_SCALE, render
    from .legend import all_tap_dances
    from .render_context import RenderContext, using_render_context

    with using_render_context(RenderContext.build(config, keymap)) as ctx:
        tap_dances = all_tap_dances(keymap.tap_dances)
        metrics = ctx.document_metrics

        initial_content_w = metrics.doc_width - 2 * metrics.padding

        # Build the section first so we can shrink the canvas to match it.
        # ``max_width`` caps the table at the canvas budget; when names
        # would overflow the cap they're auto-truncated. Omitting
        # ``width`` lets the section snug-fit the table's natural extent.
        if tap_dances:
            section = TapDanceSection(
                tap_dances=tap_dances,
                scale=BODY_SCALE,
                max_width=initial_content_w,
            )
            content_w = min(initial_content_w, section.size.width)
            body = section
        else:
            content_w = initial_content_w
            body = Spacer()

        return render(
            body=body,
            content_w=content_w,
            footer_section_title="TAP-DANCE",
        )


__all__ = [
    "TapDanceCell",
    "TapDanceColumnHeader",
    "TapDanceRow",
    "TapDanceSection",
    "TapDanceTable",
    "draw_tap_dances_image",
]
