"""Generate annotated spacing-mock SVGs for the configuration docs.

Each mock renders a focused chunk of the keymap (cluster, half, or full
layer) in monochrome through the *real* render composables, then
overlays a coloured highlight on the specific gap/spacing the
illustration is documenting. The user can eyeball each spacing in
isolation while deciding which to expose in the config schema.

Output lands in ``docs/_static/spacing/<field>.svg`` and is embedded
in the configuration docs alongside each field's description.

Run via ``just spacing-mocks``.

Style choices
-------------

- **Greyscale base**: every key, border, and indicator paints in a
  light/medium-grey palette so the user's eye locks onto the highlight
  rather than the keymap content.
- **Highlight colour**: rose-red (``#E11D48``) at full opacity for
  outlines, ``0.35`` opacity for fills. Pops against the grey without
  fighting any of the bundled palette colours used elsewhere in the docs.
- **Empty key labels**: keeps the visual focus on layout, not content.
- **System fonts on**: the snippets are pure layout; no bundled fonts
  needed, keeps the SVG small.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import drawsvg as draw

from skim.application.render.composable import Component
from skim.application.render.macros import MacroMetrics, MacroPill
from skim.application.render.primitives import BaseComponent, Point, Size
from skim.application.render.render_context import (
    RenderContext,
    using_render_context,
)
from skim.application.render.section_stripe import SectionStripe, SectionStripeMetrics
from skim.application.render.svalboard_clusters import FingerCluster, ThumbCluster
from skim.application.render.svalboard_halves import FingerHalf
from skim.application.render.tap_dance import (
    TapDanceColumnHeader,
    TapDanceMetrics,
    TapDanceRow,
    TapDanceTable,
)
from skim.data.config import KeyboardLayer, LayerColor, Palette, SkimConfig, SplitSidePosition
from skim.data.keyboard import (
    FingerCluster as FingerClusterData,
    SvalboardKeymap,
    SvalboardLayout,
    ThumbCluster as ThumbClusterData,
)
from skim.domain import (
    KeyboardSide,
    SvalboardMacroActionKind,
    SvalboardTapDance,
    SvalboardTargetKey,
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = ROOT / "docs" / "_static" / "spacing"

MockBuilder = Callable[[], draw.Drawing]

# Greyscale palette tokens — light/dark greys that mute the visual
# weight of the rendered keymap so the highlight reads as the focal
# element of the image.
_GREY_NEUTRAL = "#B8BCC3"  # key fills
_GREY_BORDER = "#6B7280"  # outlines, separator chars, etc.
_GREY_TEXT = "#4B5563"  # incidental text (badges, headers)
_GREY_LIGHT = "#E5E7EB"  # accent backgrounds (badges, chips)

# Highlight palette — rose-red. Full opacity for stroke/outline,
# semi-transparent for fills so the underlying layout stays readable.
_HIGHLIGHT = "#E11D48"
_HIGHLIGHT_FILL_OPACITY = 0.35
_HIGHLIGHT_STROKE_WIDTH = 1.5


def _grey_palette() -> Palette:
    """A monochrome palette: every key/badge/border in greys."""
    base = Palette()
    return base.model_copy(
        update={
            "neutral_color": _GREY_NEUTRAL,
            "text_color": _GREY_TEXT,
            "key_label_color": "#FFFFFF",
            "background_color": "#FFFFFF",
            "border_color": _GREY_BORDER,
            "macro_color": _GREY_BORDER,
            "tap_dance_color": _GREY_BORDER,
            "layers": tuple(LayerColor(base_color=_GREY_NEUTRAL) for _ in range(8)),
        }
    )


def _grey_config(*, num_layers: int = 4) -> SkimConfig:
    """SkimConfig with the greyscale palette wired in."""
    config = SkimConfig()
    keyboard = config.keyboard.model_copy(
        update={
            "layers": tuple(
                KeyboardLayer(index=i, name=f"Layer {i}") for i in range(num_layers)
            )
        }
    )
    style = config.output.style.model_copy(
        update={
            "use_system_fonts": True,
            "palette": _grey_palette(),
        }
    )
    output = config.output.model_copy(update={"style": style})
    return config.model_copy(update={"keyboard": keyboard, "output": output})


def _empty_keymap(*, layer_index: int = 0) -> SvalboardKeymap[SvalboardTargetKey]:
    blank = SvalboardTargetKey(label="")
    return SvalboardKeymap(layers={layer_index: SvalboardLayout.from_sequence([blank] * 60)})


# ---------------------------------------------------------------------------
# Highlight helpers — draw rose-red overlays on top of a base render.
# ---------------------------------------------------------------------------


def _highlight_rect(
    d: draw.Drawing,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """Translucent filled rectangle outlined in rose — fills a gap area."""
    d.append(
        draw.Rectangle(
            x=x,
            y=y,
            width=width,
            height=height,
            fill=_HIGHLIGHT,
            fill_opacity=_HIGHLIGHT_FILL_OPACITY,
            stroke=_HIGHLIGHT,
            stroke_width=_HIGHLIGHT_STROKE_WIDTH,
        )
    )


def _highlight_band(
    d: draw.Drawing,
    *,
    direction: str,
    bbox: tuple[float, float, float, float],
    gap_start: float,
    gap_end: float,
) -> None:
    """Draw a horizontal or vertical band over a gap.

    ``direction='vertical'`` paints the band as ``[gap_start, gap_end]``
    on the X axis spanning the full Y range of ``bbox``. ``'horizontal'``
    flips it. Used for inter-element gaps (column gaps, row gaps).
    """
    bx, by, bw, bh = bbox
    if direction == "vertical":
        _highlight_rect(d, x=gap_start, y=by, width=gap_end - gap_start, height=bh)
    elif direction == "horizontal":
        _highlight_rect(d, x=bx, y=gap_start, width=bw, height=gap_end - gap_start)
    else:
        raise ValueError(f"direction must be 'vertical' or 'horizontal', got {direction!r}")


# ---------------------------------------------------------------------------
# Base renderers — produce a Drawing of a focused chunk in greyscale.
# Each returns the Drawing AND the component bbox so the highlight
# helpers know where to overlay.
# ---------------------------------------------------------------------------


def _render_grey_canvas(
    component: Component,
    *,
    padding: float = 24.0,
) -> draw.Drawing:
    """Render a component to a Drawing sized to its natural bbox + padding."""
    canvas_w = component.size.width + padding
    canvas_h = component.size.height + padding
    d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")
    offset = padding / 2
    component.draw_at(d, Point(offset, offset))
    return d


# ---------------------------------------------------------------------------
# Mock builders — one per spacing field.
# Each function returns the final annotated Drawing.
# ---------------------------------------------------------------------------


def _build_finger_key_gap_mock() -> draw.Drawing:
    """Highlight the centre→outer-key gap inside a finger cluster.

    The four gap bands sit around the central key — the inset value
    governs how thick each band is. Centre-of-cluster x = cluster_width / 2.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    blank = SvalboardTargetKey(label="")
    cluster_width = 240.0

    with using_render_context(ctx):
        cluster = FingerCluster(
            cluster=FingerClusterData(blank),
            side=KeyboardSide.LEFT,
            width=cluster_width,
            layer_qmk_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=False,
            show_layer_indicators=False,
        )
        d = _render_grey_canvas(cluster)

        from skim.application.render.svalboard_clusters import _compute_slots

        slots = _compute_slots(cluster_width=cluster_width, has_double_south=False)
        offset = 12.0  # canvas padding from _render_grey_canvas

        # Inset thickness — derive from the gap between north's bottom
        # edge and centre's top edge.
        north_bottom = slots.north_origin.y + slots.outer_width
        center_top = slots.center_origin.y
        center_bottom = center_top + slots.center_width
        center_left = slots.center_origin.x
        center_right = center_left + slots.center_width

        # Top gap (between north and centre)
        _highlight_rect(
            d,
            x=offset + center_left,
            y=offset + north_bottom,
            width=slots.center_width,
            height=center_top - north_bottom,
        )
        # Bottom gap (between centre and south)
        south_top = slots.south_origin.y
        _highlight_rect(
            d,
            x=offset + center_left,
            y=offset + center_bottom,
            width=slots.center_width,
            height=south_top - center_bottom,
        )
        # Left gap (between west's right edge and centre's left edge)
        west_right = slots.west_origin.x + slots.outer_width
        _highlight_rect(
            d,
            x=offset + west_right,
            y=offset + center_top,
            width=center_left - west_right,
            height=slots.center_width,
        )
        # Right gap (between centre's right edge and east's left edge)
        east_left = slots.east_origin.x
        _highlight_rect(
            d,
            x=offset + center_right,
            y=offset + center_top,
            width=east_left - center_right,
            height=slots.center_width,
        )

    return d


def _build_layer_indicator_spacing_mock() -> draw.Drawing:
    """Highlight the gap between an outer key and its layer indicator.

    Uses the **north** key (not the centre): the centre's indicator
    sits diagonally and uses the ``_CENTER_KEY_GAP_MULTIPLIER`` we
    filtered out of the candidate list. The outer keys (N/E/S/W) are
    the canonical case — indicator extends straight outward in the
    key's cardinal direction, governed solely by
    ``layer_indicator_spacing``.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    blank = SvalboardTargetKey(label="")
    cluster_width = 240.0

    cluster_data = FingerClusterData(
        blank, north_key=SvalboardTargetKey(label="", layer_switch=2)
    )

    with using_render_context(ctx):
        cluster = FingerCluster(
            cluster=cluster_data,
            side=KeyboardSide.LEFT,
            width=cluster_width,
            layer_qmk_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=False,
            show_layer_indicators=True,
        )

        # Indicator-bearing clusters have an overflow_size that's
        # larger than their keys-only size — paint the canvas around
        # the overflow box so nothing clips at the top edge.
        from skim.application.render.svalboard_clusters import _compute_slots

        metrics = cluster.metrics
        padding = 24.0
        canvas_w = metrics.overflow_size.width + padding
        canvas_h = metrics.overflow_size.height + padding
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

        # The cluster's keys-only origin lands at:
        cluster_origin_x = padding / 2 - metrics.overflow_offset.x
        cluster_origin_y = padding / 2 - metrics.overflow_offset.y
        cluster.draw_at(d, Point(cluster_origin_x, cluster_origin_y))

        slots = _compute_slots(cluster_width=cluster_width, has_double_south=False)
        north_indicator = metrics.indicators.north_key
        if north_indicator is not None:
            # circle_center is in KEY-LOCAL coords. Convert to canvas
            # coords by adding the cluster origin and the north-key
            # origin (which is at y=0 in cluster-local).
            key_origin_y = cluster_origin_y + slots.north_origin.y
            circle_cy = key_origin_y + north_indicator.circle_center.y
            r = north_indicator.circle_radius

            # The spacing band: from the indicator circle's bottom
            # edge to the north key's top edge, centred horizontally
            # on the key.
            gap_y_start = circle_cy + r  # bottom of circle (above the key)
            gap_y_end = key_origin_y  # top of the north key
            key_centre_x = (
                cluster_origin_x + slots.north_origin.x + slots.outer_width / 2.0
            )
            band_width = slots.outer_width * 0.45

            _highlight_rect(
                d,
                x=key_centre_x - band_width / 2.0,
                y=gap_y_start,
                width=band_width,
                height=max(gap_y_end - gap_y_start, 1.0),
            )

    return d


def _build_column_gap_mock() -> draw.Drawing:
    """Highlight one of the column gaps between finger clusters in a half."""
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    blank = SvalboardTargetKey(label="")
    empty_cluster = FingerClusterData(blank)
    fingers = (empty_cluster, empty_cluster, empty_cluster, empty_cluster)
    half_min_width = 800.0

    with using_render_context(ctx):
        column_gap = ctx.document_metrics.column_gap
        # cluster_width matches the formula in svalboard_halves.py:172
        cluster_width = (half_min_width - column_gap * 3) / 4

        half = FingerHalf(
            fingers=fingers,
            side=KeyboardSide.RIGHT,  # keeps cluster order index→pinky left-to-right
            min_width=half_min_width,
            layer_qmk_index=0,
            stagger_middle_fingers=False,  # flat row reads cleaner for the mock
            has_double_south=False,
            use_layer_colors_on_keys=False,
            show_layer_indicators=False,
        )
        d = _render_grey_canvas(half)
        offset = 12.0

        # Highlight every column gap between adjacent clusters so the
        # user sees the full rhythm. Three gaps for four clusters.
        for i in range(3):
            gap_x = (i + 1) * cluster_width + i * column_gap
            _highlight_rect(
                d,
                x=offset + gap_x,
                y=offset,
                width=column_gap,
                height=half.size.height,
            )

    return d


# ---------------------------------------------------------------------------
# Document-wide spacings (margin / inset / table rhythm / section_spacing)
# ---------------------------------------------------------------------------


def _doc_chrome_mock(*, highlight: str) -> draw.Drawing:
    """Render a small KeymapDocument with a real keymap inside, then
    highlight one of three document-chrome values:

    * ``margin`` — band between canvas edge and the border line.
    * ``inset`` — band between the border line and the content.
    * ``border`` — rose stroke overlaid on the border path itself
      (the value is a stroke width, not a band).

    Showing a real keymap inside makes each value's role legible at a
    glance. The mock uses an exaggerated ``border_width = 4`` so the
    stroke reads cleanly even on the small canvas.
    """
    from skim.application.render.keymap_document import KeymapDocument
    from skim.application.render.keymap_layer import KeymapLayer
    from skim.data.config import Border, Spacing

    margin = 18.0
    inset = 22.0
    border_width = 4.0
    border_radius = 8.0
    doc_width = 720.0

    config = _grey_config()
    layout = config.output.layout.model_copy(
        update={
            "width": doc_width,
            "spacing": Spacing(margin=margin, inset=inset),
        }
    )
    style = config.output.style.model_copy(
        update={
            "border": Border(width=border_width, radius=border_radius),
            "show_layer_indicators": False,
        }
    )
    output = config.output.model_copy(update={"layout": layout, "style": style})
    config = config.model_copy(update={"output": output})

    keymap = _empty_keymap()
    layer_data = keymap.layers[0]
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        content_offset = margin + border_width + inset
        target_content_w = doc_width - 2 * content_offset
        body = KeymapLayer(
            layer=layer_data,
            qmk_index=0,
            target_content_w=target_content_w,
        )
        document = KeymapDocument(content=body)

        canvas_w = document.size.width
        canvas_h = document.size.height
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")
        document.draw_at(d, Point(0.0, 0.0))

        if highlight == "margin":
            # Bands between canvas edge and border path. The border
            # stroke is centred on a path at ``margin`` from each edge,
            # so the band's width equals the resolved margin value
            # exactly (with half the stroke peeking inside the band).
            _highlight_rect(d, x=0.0, y=0.0, width=canvas_w, height=margin)
            _highlight_rect(
                d, x=0.0, y=canvas_h - margin, width=canvas_w, height=margin
            )
            _highlight_rect(
                d, x=0.0, y=margin, width=margin, height=canvas_h - 2 * margin
            )
            _highlight_rect(
                d,
                x=canvas_w - margin,
                y=margin,
                width=margin,
                height=canvas_h - 2 * margin,
            )
        elif highlight == "inset":
            # Bands between the border path's inner edge and the
            # content. ``content_offset = margin + border_width + inset``
            # so a band of width ``inset`` starts at ``margin +
            # border_width`` (inner edge of the stroke) and ends at the
            # content origin.
            inner = margin + border_width
            _highlight_rect(
                d,
                x=inner,
                y=inner,
                width=canvas_w - 2 * inner,
                height=inset,
            )
            _highlight_rect(
                d,
                x=inner,
                y=canvas_h - inner - inset,
                width=canvas_w - 2 * inner,
                height=inset,
            )
            _highlight_rect(
                d,
                x=inner,
                y=inner + inset,
                width=inset,
                height=canvas_h - 2 * (inner + inset),
            )
            _highlight_rect(
                d,
                x=canvas_w - inner - inset,
                y=inner + inset,
                width=inset,
                height=canvas_h - 2 * (inner + inset),
            )
        elif highlight == "border":
            # Rose overlay on the border path. The path is centred at
            # ``margin`` from each edge with ``border_width`` stroke,
            # so the overlay re-paints the same rectangle in rose to
            # show what the border-width value strokes.
            d.append(
                draw.Rectangle(
                    x=margin,
                    y=margin,
                    width=canvas_w - 2 * margin,
                    height=canvas_h - 2 * margin,
                    rx=border_radius,
                    ry=border_radius,
                    fill="none",
                    stroke=_HIGHLIGHT,
                    stroke_width=border_width,
                )
            )
        else:
            raise ValueError(f"unknown highlight {highlight!r}")

    return d


def _build_margin_mock() -> draw.Drawing:
    return _doc_chrome_mock(highlight="margin")


def _build_border_width_mock() -> draw.Drawing:
    return _doc_chrome_mock(highlight="border")


def _build_inset_mock() -> draw.Drawing:
    return _doc_chrome_mock(highlight="inset")


# ---------------------------------------------------------------------------
# Tap-dance / Macro mocks — share the grey config wiring.
# ---------------------------------------------------------------------------


def _grey_td(*, idx: str = "0", name: str | None = None) -> SvalboardTapDance[SvalboardTargetKey]:
    """Tap-dance with all four variants populated so cells render."""
    blank = SvalboardTargetKey(label="—")
    return SvalboardTapDance(
        id=idx,
        tap=blank,
        hold=blank,
        double_tap=blank,
        tap_then_hold=blank,
        name=name,
    )


def _build_section_spacing_mock() -> draw.Drawing:
    """Highlight the gap between a section's stripe and the first body row.

    ``section_spacing`` lands as the inter-child gap inside the
    ``Column`` MacroSection / TapDanceSection use to stack the title
    stripe and the body. It also splits named-vs-unnamed macro
    sub-blocks. The mock paints the stripe + a single TD row and
    highlights the gap between them.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        section_spacing = ctx.document_metrics.section_spacing
        stripe = SectionStripe(
            title="TAP-DANCE", count=1, width=320.0, accent_line=_GREY_BORDER
        )
        header = TapDanceColumnHeader(text_color=_GREY_TEXT)
        row = TapDanceRow(
            td=_grey_td(),
            accent_fill=_GREY_NEUTRAL,
            accent_line=_GREY_BORDER,
            text_color=_GREY_TEXT,
        )
        body_w = max(header.size.width, row.size.width)
        canvas_w = max(stripe.size.width, body_w) + 24.0
        canvas_h = stripe.size.height + section_spacing + header.size.height + row.size.height + 24.0
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

        x = 12.0
        y = 12.0
        stripe.draw_at(d, Point(x, y))
        body_y = y + stripe.size.height + section_spacing
        header.draw_at(d, Point(x, body_y))
        row.draw_at(d, Point(x, body_y + header.size.height))

        # Highlight the section_spacing band between the stripe's
        # bottom and the body's top.
        _highlight_rect(
            d,
            x=x,
            y=y + stripe.size.height,
            width=body_w,
            height=section_spacing,
        )

    return d


def _build_table_header_spacing_mock() -> draw.Drawing:
    """Highlight the gap between a TapDanceColumnHeader and the first row."""
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = TapDanceMetrics.from_ctx(ctx)
        header = TapDanceColumnHeader(text_color=_GREY_TEXT)
        row = TapDanceRow(
            td=_grey_td(),
            accent_fill=_GREY_NEUTRAL,
            accent_line=_GREY_BORDER,
            text_color=_GREY_TEXT,
        )
        # The header's ``table_header_spacing`` of empty space is
        # baked into its reported height (text_height +
        # table_header_spacing); the band we want sits at the bottom
        # of the header's bbox.
        canvas_w = max(header.size.width, row.size.width) + 24.0
        canvas_h = header.size.height + row.size.height + 24.0
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

        x = 12.0
        y = 12.0
        header.draw_at(d, Point(x, y))
        row.draw_at(d, Point(x, y + header.size.height))

        # Highlight the band — the bottom slice of the header's bbox
        # (text sits flush with the top, gap is at the bottom).
        _highlight_rect(
            d,
            x=x,
            y=y + header.size.height - metrics.table_header_spacing,
            width=row.size.width,
            height=metrics.table_header_spacing,
        )

    return d


def _build_table_col_spacing_mock() -> draw.Drawing:
    """Highlight the gaps between adjacent variant cells in a TD row."""
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = TapDanceMetrics.from_ctx(ctx)
        row = TapDanceRow(
            td=_grey_td(),
            accent_fill=_GREY_NEUTRAL,
            accent_line=_GREY_BORDER,
            text_color=_GREY_TEXT,
        )
        d = _render_grey_canvas(row)
        offset = 12.0

        cells_start_x = metrics.chip_width + (metrics.name_w - metrics.chip_width) + metrics.table_header_spacing
        cell_w = metrics.cell_w
        col_spacing = metrics.table_col_spacing

        for i in range(3):
            gap_x = cells_start_x + (i + 1) * cell_w + i * col_spacing
            _highlight_rect(
                d,
                x=offset + gap_x,
                y=offset,
                width=col_spacing,
                height=metrics.row_height,
            )

    return d


def _build_table_row_spacing_mock() -> draw.Drawing:
    """Highlight the gaps between adjacent rows in a tap-dance table."""
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = TapDanceMetrics.from_ctx(ctx)
        tds = [_grey_td(idx=str(i)) for i in range(3)]
        table = TapDanceTable(
            tap_dances=tds,
            accent_fill=_GREY_NEUTRAL,
            accent_line=_GREY_BORDER,
            text_color=_GREY_TEXT,
        )
        d = _render_grey_canvas(table)
        offset = 12.0

        # Highlight the gaps BETWEEN rows. The trailing post-last-row
        # spacing exists (it's baked into the table's reported height)
        # but reads as padding rather than rhythm, so we leave it
        # un-highlighted.
        header_height = TapDanceColumnHeader(text_color=_GREY_TEXT).size.height
        for i in range(2):
            gap_y = (
                header_height
                + (i + 1) * metrics.row_height
                + i * metrics.table_row_spacing
            )
            _highlight_rect(
                d,
                x=offset,
                y=offset + gap_y,
                width=table.size.width,
                height=metrics.table_row_spacing,
            )

    return d


# ---------------------------------------------------------------------------
# Section / legend internals
# ---------------------------------------------------------------------------


def _build_section_title_rule_gap_mock() -> draw.Drawing:
    """Highlight the gap between the section title and the rule below it.

    The strip is top-anchored: the title's em-box top sits at the
    strip's top edge, with no dangling space above. The rule line
    sits ``title_rule_gap`` below the title's em-box bottom — the
    only configurable vertical value inside the strip.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = SectionStripeMetrics.for_doc_width(ctx.config.output.layout.width)
        stripe = SectionStripe(
            title="MACROS", count=2, width=320.0, accent_line=_GREY_BORDER
        )
        # Pad above and below so the strip reads as a discrete region;
        # the highlight band sits inside the strip and the surrounding
        # whitespace makes its boundaries legible.
        pad = 24.0
        canvas_w = stripe.size.width + 2 * pad
        canvas_h = stripe.size.height + 2 * pad
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

        x = pad
        y = pad
        stripe.draw_at(d, Point(x, y))

        # Highlight the gap from the title's em-box bottom (=
        # title_font_size below the strip top) down to the rule line.
        _highlight_rect(
            d,
            x=x,
            y=y + metrics.title_font_size,
            width=stripe.size.width,
            height=metrics.title_rule_gap,
        )

    return d


def _build_chip_padding_mock() -> draw.Drawing:
    """Highlight ``chip_padding`` inside the TD chip outline name area.

    Symmetric horizontal inset: leading (chip body → name text) and
    trailing (name text → outline's right edge). The mock snugs the
    name column to ``chip_padding + name_text + chip_padding`` so the
    trailing highlight lands at the outline's actual right edge — no
    extra column slack leaking past the band.

    Same ``chip_padding`` value will eventually govern the chip body's
    internal padding around the centered glyph (currently implicit —
    chip body is fixed-width — so the visible inner padding varies
    with id length until auto-sizing lands).
    """
    from skim.application.render.adjustable_text import measure_text_width
    from skim.application.render.font import Font

    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = TapDanceMetrics.from_ctx(ctx)
        name_text = "MY-TD"
        natural_name_w = measure_text_width(name_text, Font.FINGER_KEY, metrics.name_font_size)
        name_column_width = 2 * metrics.chip_padding + natural_name_w
        outline_width = metrics.chip_width + name_column_width

        row = TapDanceRow(
            td=_grey_td(idx="0", name=name_text),
            accent_fill=_GREY_NEUTRAL,
            accent_line=_GREY_BORDER,
            text_color=_GREY_TEXT,
            name_column_width=name_column_width,
        )

        # Canvas crops to the outline's right edge — the cells the row
        # paints further right land outside the viewBox and clip during
        # render, so the mock reads as a chip in isolation.
        offset = 12.0
        canvas_w = outline_width + 2 * offset
        canvas_h = row.size.height + 2 * offset
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")
        row.draw_at(d, Point(offset, offset))

        # Leading chip_padding (chip body → name).
        _highlight_rect(
            d,
            x=offset + metrics.chip_width,
            y=offset,
            width=metrics.chip_padding,
            height=metrics.row_height,
        )
        # Trailing chip_padding (name → outline's right edge).
        _highlight_rect(
            d,
            x=offset + outline_width - metrics.chip_padding,
            y=offset,
            width=metrics.chip_padding,
            height=metrics.row_height,
        )

    return d


def _build_tap_dance_pill_padding_mock() -> draw.Drawing:
    """Highlight the symmetric inset inside a TD pill (cell).

    Today the cell width is fixed; this band shows the configurable
    ``tap_dance_pill_padding`` value that an auto-sized cell will use
    once the refactor lands. Two bands: leading and trailing.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = TapDanceMetrics.from_ctx(ctx)
        # Build a TD row to get a representative pill (cell) painted.
        row = TapDanceRow(
            td=_grey_td(idx="0"),
            accent_fill=_GREY_NEUTRAL,
            accent_line=_GREY_BORDER,
            text_color=_GREY_TEXT,
        )
        d = _render_grey_canvas(row)
        offset = 12.0

        # Cell start x — same math TapDanceRow uses internally.
        name_column_width = metrics.name_w - metrics.chip_width  # default for unnamed
        cells_start_x = (
            metrics.chip_width + name_column_width + metrics.table_header_spacing
        )

        # Highlight the first cell's leading + trailing padding.
        _highlight_rect(
            d,
            x=offset + cells_start_x,
            y=offset,
            width=metrics.tap_dance_pill_padding,
            height=metrics.row_height,
        )
        _highlight_rect(
            d,
            x=offset + cells_start_x + metrics.cell_w - metrics.tap_dance_pill_padding,
            y=offset,
            width=metrics.tap_dance_pill_padding,
            height=metrics.row_height,
        )

    return d


def _build_macro_action_inset_mock() -> draw.Drawing:
    """Highlight the three positions ``macro_action_inset`` paints inside
    a :func:`MacroPill`: pill edge → icon centre, icon → text, and text
    end → pill edge. A single configurable value drives all three so
    the pill's internal rhythm stays consistent.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = MacroMetrics.from_ctx(ctx)
        pill = MacroPill(
            kind=SvalboardMacroActionKind.TAP,
            label="LONG-PILL-LABEL",
            text_color=_GREY_TEXT,
        )
        d = _render_grey_canvas(pill)
        offset = 12.0

        pill_top = offset + (metrics.pill_row_height - metrics.pill_height) / 2
        inset = metrics.macro_action_inset

        # Leading inset — pill edge to icon centre.
        _highlight_rect(
            d,
            x=offset,
            y=pill_top,
            width=inset,
            height=metrics.pill_height,
        )
        # Icon → text — from icon's right edge (icon_centre +
        # icon_w/2) to text start.
        gap_start = offset + inset + metrics.pill_icon_width / 2
        _highlight_rect(
            d,
            x=gap_start,
            y=pill_top,
            width=inset,
            height=metrics.pill_height,
        )
        # Trailing inset — pill's right edge inward.
        _highlight_rect(
            d,
            x=offset + pill.size.width - inset,
            y=pill_top,
            width=inset,
            height=metrics.pill_height,
        )

    return d


# ---------------------------------------------------------------------------
# Overview / chrome
# ---------------------------------------------------------------------------


def _build_layer_badge_inset_mock() -> draw.Drawing:
    """Highlight the inset paint inside a LayerBadge.

    The badge lays out as four columns:

    1. Leading inset (``inset``) — badge edge → start of index.
    2. Index column — fixed width across all badges (sized to the
       widest digit count) so single-digit indices right-align flush
       with double-digit ones.
    3. Inter-column inset (``inset``) — index → name.
    4. Name column — left-aligned label.
    5. Trailing inset (``inset * 2``) — name end → badge edge.

    Two stacked badges show the right-alignment in action: index ``0``
    sits with leading whitespace inside the index column and ``12``
    fills it. The leading and inter-column insets are highlighted at
    full opacity (both are the same configurable value); the trailing
    ``inset * 2`` is dashed at half opacity so the derived 1:2 ratio
    reads visually without competing with the canonical highlight.
    """
    from skim.application.render.keymap_overview import (
        _badge_inset,
        _measure_badge_text_width,
    )

    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        inset = _badge_inset(ctx.config)
        badge_height = 60.0
        font_size = badge_height * 0.45  # _BADGE_FONT_SIZE_RATIO
        border_radius = badge_height * 0.2

        # Index column — wide enough to fit a 2-digit index. Indices
        # right-align inside this column so the digits stack across
        # badges in the overview.
        index_col_width = _measure_badge_text_width("12", font_size)
        name_text = "LAYER NAME"
        name_width = _measure_badge_text_width(name_text, font_size)
        badge_width = inset + index_col_width + inset + name_width + inset * 2

        offset = 12.0
        badge_gap = 10.0
        rows = ("0", "12")
        canvas_w = badge_width + 2 * offset
        canvas_h = len(rows) * badge_height + (len(rows) - 1) * badge_gap + 2 * offset
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

        index_col_x = offset + inset
        index_right_x = index_col_x + index_col_width
        name_x = index_right_x + inset

        for row, idx_text in enumerate(rows):
            badge_y = offset + row * (badge_height + badge_gap)
            cy = badge_y + badge_height / 2

            d.append(
                draw.Rectangle(
                    x=offset,
                    y=badge_y,
                    width=badge_width,
                    height=badge_height,
                    rx=border_radius,
                    ry=border_radius,
                    fill=_GREY_NEUTRAL,
                )
            )
            # Index — right-aligned at the column's right edge.
            d.append(
                draw.Text(
                    idx_text,
                    font_size=font_size,
                    x=index_right_x,
                    y=cy,
                    text_anchor="end",
                    dominant_baseline="central",
                    font_family="Roboto, sans-serif",
                    fill="#FFFFFF",
                )
            )
            # Name — left-aligned after the inter-column inset.
            d.append(
                draw.Text(
                    name_text,
                    font_size=font_size,
                    x=name_x,
                    y=cy,
                    text_anchor="start",
                    dominant_baseline="central",
                    font_family="Roboto, sans-serif",
                    fill="#FFFFFF",
                )
            )

            # Leading inset.
            _highlight_rect(d, x=offset, y=badge_y, width=inset, height=badge_height)
            # Inter-column inset (index → name).
            _highlight_rect(
                d, x=index_right_x, y=badge_y, width=inset, height=badge_height
            )
            # Trailing inset (2 × inset) — dashed half-opacity so the
            # derived value doesn't compete with the canonical paint.
            d.append(
                draw.Rectangle(
                    x=offset + badge_width - inset * 2,
                    y=badge_y,
                    width=inset * 2,
                    height=badge_height,
                    fill=_HIGHLIGHT,
                    fill_opacity=_HIGHLIGHT_FILL_OPACITY * 0.5,
                    stroke=_HIGHLIGHT,
                    stroke_width=_HIGHLIGHT_STROKE_WIDTH,
                    stroke_dasharray="4 3",
                )
            )

    return d


# ---------------------------------------------------------------------------
# Thumb-key gap — one inset-tall band above each of the four outer
# thumb keys (pad, nail, up, knuckle). The inset value applies
# uniformly above every key that has a key above it; the down key
# itself sits at the cluster top so it has nothing above it.
# ---------------------------------------------------------------------------


def _build_thumb_key_gap_mock() -> draw.Drawing:
    """Highlight the inset band sitting on top of pad / nail / up / knuckle.

    Each of the four outer thumb keys has an ``inset``-tall band of
    breathing room directly above it. Pad and nail sit at the cluster
    top so their bands fill the strip from the cluster's top edge down
    to the key's top; up and knuckle sit lower in the cluster so their
    bands are inset-tall slivers floating just above each key.
    """
    from skim.application.render.svalboard_clusters import _compute_thumb_slots

    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    blank = SvalboardTargetKey(label="")
    cluster_data = ThumbClusterData(
        down_key=blank,
        pad_key=blank,
        up_key=blank,
        nail_key=blank,
        knuckle_key=blank,
        double_down_key=blank,
    )
    cluster_width = 360.0

    with using_render_context(ctx):
        cluster = ThumbCluster(
            cluster=cluster_data,
            side=KeyboardSide.LEFT,
            width=cluster_width,
            layer_qmk_index=0,
            use_layer_colors_on_keys=False,
            show_layer_indicators=False,
        )
        d = _render_grey_canvas(cluster)
        offset = 12.0

        slots = _compute_thumb_slots(cluster_width=cluster_width, side=KeyboardSide.LEFT)
        inset = slots.pad_origin.y  # = cluster_width * _THUMB_INSET_PROPORTION

        for key_origin, key_width in (
            (slots.pad_origin, slots.pad_width),
            (slots.nail_origin, slots.nail_width),
            (slots.up_origin, slots.up_width),
            (slots.knuckle_origin, slots.knuckle_width),
        ):
            _highlight_rect(
                d,
                x=offset + key_origin.x,
                y=offset + key_origin.y - inset,
                width=key_width,
                height=inset,
            )

    return d


# ---------------------------------------------------------------------------
# Stroke-width mocks — overlay a rose-red stroke on top of the real
# rendered chrome at the configured width, so the user sees what the
# stroke value actually paints. The underlying greyscale render gives
# context (where the stroke sits inside the component).
# ---------------------------------------------------------------------------


def _build_chip_outline_mock() -> draw.Drawing:
    """Highlight the ``Strokes.chip_outline`` value as a rose stroke
    overlaid on a TapDance chip outline.
    """
    from skim.application.render.adjustable_text import measure_text_width
    from skim.application.render.font import Font

    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = TapDanceMetrics.from_ctx(ctx)
        name_text = "MY-TD"
        natural_name_w = measure_text_width(name_text, Font.FINGER_KEY, metrics.name_font_size)
        name_column_width = 2 * metrics.chip_padding + natural_name_w
        outline_width = metrics.chip_width + name_column_width

        row = TapDanceRow(
            td=_grey_td(idx="0", name=name_text),
            accent_fill=_GREY_NEUTRAL,
            accent_line=_GREY_BORDER,
            text_color=_GREY_TEXT,
            name_column_width=name_column_width,
        )

        offset = 12.0
        canvas_w = outline_width + 2 * offset
        canvas_h = row.size.height + 2 * offset
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")
        row.draw_at(d, Point(offset, offset))

        # Rose overlay on the chip's outlined path. ``chip_corner_radius``
        # matches the underlying outline so the rose sits flush.
        d.append(
            draw.Rectangle(
                x=offset,
                y=offset,
                width=outline_width,
                height=metrics.row_height,
                rx=metrics.chip_corner_radius,
                ry=metrics.chip_corner_radius,
                fill="none",
                stroke=_HIGHLIGHT,
                stroke_width=metrics.chip_stroke_width,
            )
        )

    return d


def _build_header_rule_stroke_mock() -> draw.Drawing:
    """Highlight ``Strokes.header_rule`` as a rose-coloured rule line
    underneath a SectionStripe title.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = SectionStripeMetrics.from_ctx(ctx)
        stripe = SectionStripe(
            title="MACROS", count=3, width=320.0, accent_line=_GREY_BORDER
        )
        pad = 24.0
        canvas_w = stripe.size.width + 2 * pad
        canvas_h = stripe.size.height + 2 * pad
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

        x = pad
        y = pad
        stripe.draw_at(d, Point(x, y))

        # Rose overlay on the rule line at the same y position the
        # stripe paints its own rule.
        d.append(
            draw.Line(
                sx=x,
                sy=y + metrics.rule_offset,
                ex=x + stripe.size.width,
                ey=y + metrics.rule_offset,
                stroke=_HIGHLIGHT,
                stroke_width=metrics.rule_stroke,
            )
        )

    return d


def _build_layer_indicator_stroke_mock() -> draw.Drawing:
    """Highlight ``Strokes.layer_indicator`` as a rose-coloured stroke
    on the indicator circle next to a finger cluster's north key.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    blank = SvalboardTargetKey(label="")
    cluster_width = 240.0
    cluster_data = FingerClusterData(
        blank, north_key=SvalboardTargetKey(label="", layer_switch=2)
    )

    with using_render_context(ctx):
        cluster = FingerCluster(
            cluster=cluster_data,
            side=KeyboardSide.LEFT,
            width=cluster_width,
            layer_qmk_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=False,
            show_layer_indicators=True,
        )

        from skim.application.render.svalboard_clusters import _compute_slots

        metrics = cluster.metrics
        padding = 24.0
        canvas_w = metrics.overflow_size.width + padding
        canvas_h = metrics.overflow_size.height + padding
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

        cluster_origin_x = padding / 2 - metrics.overflow_offset.x
        cluster_origin_y = padding / 2 - metrics.overflow_offset.y
        cluster.draw_at(d, Point(cluster_origin_x, cluster_origin_y))

        slots = _compute_slots(cluster_width=cluster_width, has_double_south=False)
        north_indicator = metrics.indicators.north_key
        if north_indicator is not None:
            key_origin_y = cluster_origin_y + slots.north_origin.y
            key_origin_x = cluster_origin_x + slots.north_origin.x
            cx = key_origin_x + north_indicator.circle_center.x
            cy = key_origin_y + north_indicator.circle_center.y

            from skim.application.render.layer_indicator import _CIRCLE_STROKE_WIDTH_RATIO
            from skim.data import resolve_spacing

            stroke_w = resolve_spacing(
                ctx.config.output.style.layer_indicator.width,
                base=ctx.document_metrics.doc_width,
                default_proportion=_CIRCLE_STROKE_WIDTH_RATIO,
            )
            d.append(
                draw.Circle(
                    cx=cx,
                    cy=cy,
                    r=north_indicator.circle_radius,
                    fill="none",
                    stroke=_HIGHLIGHT,
                    stroke_width=stroke_w,
                )
            )

    return d


def _build_layer_connector_width_mock() -> draw.Drawing:
    """Highlight ``LayerConnector.width`` as a rose-coloured dotted
    path mirroring the overview's connector chrome.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        from skim.application.render.keymap_overview import (
            _CONNECTOR_PATH_DASH_DOT_RATIO,
            _CONNECTOR_PATH_DASH_GAP_RATIO,
            _CONNECTOR_PATH_STROKE_WIDTH_RATIO,
        )
        from skim.data import resolve_spacing

        doc_width = ctx.document_metrics.doc_width
        stroke_w = resolve_spacing(
            ctx.config.output.style.layer_connector.width,
            base=doc_width,
            default_proportion=_CONNECTOR_PATH_STROKE_WIDTH_RATIO,
        )
        dot = doc_width * _CONNECTOR_PATH_DASH_DOT_RATIO
        dash_gap = resolve_spacing(
            ctx.config.output.style.layer_connector.dot_spacing,
            base=doc_width,
            default_proportion=_CONNECTOR_PATH_DASH_GAP_RATIO,
        )

        # Short horizontal connector path so the dotted cadence reads.
        canvas_w = 320.0
        canvas_h = 60.0
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")
        d.append(
            draw.Line(
                sx=20,
                sy=canvas_h / 2,
                ex=canvas_w - 20,
                ey=canvas_h / 2,
                stroke=_HIGHLIGHT,
                stroke_width=stroke_w,
                stroke_linecap="round",
                stroke_dasharray=f"{dot} {dash_gap}",
                opacity=0.85,
            )
        )

    return d


def _build_layer_connector_dot_spacing_mock() -> draw.Drawing:
    """Highlight ``LayerConnector.dot_spacing`` as a rose band sitting
    in the gap between two adjacent dots on a grey connector path.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        from skim.application.render.keymap_overview import (
            _CONNECTOR_PATH_DASH_DOT_RATIO,
            _CONNECTOR_PATH_DASH_GAP_RATIO,
            _CONNECTOR_PATH_STROKE_WIDTH_RATIO,
        )
        from skim.data import resolve_spacing

        doc_width = ctx.document_metrics.doc_width
        stroke_w = resolve_spacing(
            ctx.config.output.style.layer_connector.width,
            base=doc_width,
            default_proportion=_CONNECTOR_PATH_STROKE_WIDTH_RATIO,
        )
        dot = doc_width * _CONNECTOR_PATH_DASH_DOT_RATIO
        dash_gap = resolve_spacing(
            ctx.config.output.style.layer_connector.dot_spacing,
            base=doc_width,
            default_proportion=_CONNECTOR_PATH_DASH_GAP_RATIO,
        )

        canvas_w = 320.0
        canvas_h = 60.0
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")
        line_x_start = 20.0
        line_x_end = canvas_w - 20.0
        cy = canvas_h / 2
        d.append(
            draw.Line(
                sx=line_x_start,
                sy=cy,
                ex=line_x_end,
                ey=cy,
                stroke=_GREY_BORDER,
                stroke_width=stroke_w,
                stroke_linecap="round",
                stroke_dasharray=f"{dot} {dash_gap}",
                opacity=0.85,
            )
        )

        # Highlight the gap that sits between the 3rd and 4th dots.
        # Each cycle is ``dot + dash_gap``; gap N spans
        # ``[line_start + N * cycle + dot, line_start + (N+1) * cycle]``.
        cycle = dot + dash_gap
        gap_idx = 3
        gap_start_x = line_x_start + gap_idx * cycle + dot
        gap_height = max(stroke_w * 4, 12.0)
        _highlight_rect(
            d,
            x=gap_start_x,
            y=cy - gap_height / 2,
            width=dash_gap,
            height=gap_height,
        )

    return d


# ---------------------------------------------------------------------------
# Flag-option mocks — before/after (or N-way) comparisons illustrating
# how a boolean / enum config switch changes the rendered output. Each
# variant gets a short caption underneath so the comparison reads as
# "this configured value yields this visual".
# ---------------------------------------------------------------------------


def _build_side_by_side(
    *,
    panels: list[tuple[Component, str]],
    panel_gap: float = 28.0,
    outer_padding: float = 16.0,
    label_font_size: float = 12.0,
) -> draw.Drawing:
    """Render N components horizontally with a caption under each.

    All panels align to the top; each caption centres horizontally
    under its component and the canvas height tracks the tallest
    panel plus a single caption row beneath.
    """
    label_gap = 8.0
    label_height = label_font_size + label_gap
    panel_h = max(c.size.height for c, _ in panels)
    panel_widths = [c.size.width for c, _ in panels]
    total_w = sum(panel_widths) + panel_gap * (len(panels) - 1)
    canvas_w = total_w + 2 * outer_padding
    canvas_h = panel_h + label_height + 2 * outer_padding
    d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

    cursor_x = outer_padding
    for component, caption in panels:
        component.draw_at(d, Point(cursor_x, outer_padding))
        d.append(
            draw.Text(
                caption,
                x=cursor_x + component.size.width / 2,
                y=outer_padding + panel_h + label_gap,
                font_size=label_font_size,
                text_anchor="middle",
                dominant_baseline="text-before-edge",
                font_family="Roboto, sans-serif",
                fill=_GREY_TEXT,
            )
        )
        cursor_x += component.size.width + panel_gap

    return d


def _build_hold_symbol_position_mock() -> draw.Drawing:
    """Three LEFT thumb clusters illustrating the three
    ``hold_symbol_position`` modes. Hold-tap labels sit on pad / up /
    nail / knuckle so the swap behaviour reads on every relevant key.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    hold_tap = SvalboardTargetKey(label="HOLD│TAP")
    blank = SvalboardTargetKey(label="")
    cluster_data = ThumbClusterData(
        down_key=blank,
        pad_key=hold_tap,
        up_key=hold_tap,
        nail_key=hold_tap,
        knuckle_key=hold_tap,
        double_down_key=blank,
    )
    cluster_width = 240.0

    positions = [
        (SplitSidePosition.QMK_DEFINED, '"qmk"'),
        (SplitSidePosition.INWARD, '"inward"'),
        (SplitSidePosition.OUTWARD, '"outward"'),
    ]

    with using_render_context(ctx):
        panels: list[tuple[Component, str]] = []
        for pos, caption in positions:
            cluster = ThumbCluster(
                cluster=cluster_data,
                side=KeyboardSide.LEFT,
                width=cluster_width,
                layer_qmk_index=0,
                use_layer_colors_on_keys=False,
                show_layer_indicators=False,
                hold_symbol_position=pos,
            )
            panels.append((cluster, caption))
        return _build_side_by_side(panels=panels)


def _build_layer_indicator_show_mock() -> draw.Drawing:
    """Finger cluster with a layer-switching north key, rendered with
    and without the layer-indicator badge.
    """
    config = _grey_config()
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    blank = SvalboardTargetKey(label="")
    cluster_data = FingerClusterData(
        blank, north_key=SvalboardTargetKey(label="", layer_switch=2)
    )
    cluster_width = 220.0

    with using_render_context(ctx):
        panels: list[tuple[Component, str]] = []
        for show, caption in ((True, "show: true"), (False, "show: false")):
            cluster = FingerCluster(
                cluster=cluster_data,
                side=KeyboardSide.LEFT,
                width=cluster_width,
                layer_qmk_index=0,
                has_double_south=False,
                use_layer_colors_on_keys=False,
                show_layer_indicators=show,
            )
            panels.append((cluster, caption))
        return _build_side_by_side(panels=panels)


def _build_use_layer_colors_on_keys_mock() -> draw.Drawing:
    """Finger cluster where the north key activates layer 2, rendered
    once with the destination layer's colour painting the key and
    once with the neutral fall-back.

    The grey-mock palette is replaced for this single illustration
    with one that gives layer 2 a distinct accent so the toggle reads
    visibly.
    """
    palette = _grey_palette()
    accent_layer = LayerColor(base_color="#3F7BB6")
    layers = list(palette.layers)
    while len(layers) < 3:
        layers.append(LayerColor(base_color=_GREY_NEUTRAL))
    layers[2] = accent_layer
    palette = palette.model_copy(update={"layers": tuple(layers)})

    config = SkimConfig()
    keyboard = config.keyboard.model_copy(
        update={
            "layers": tuple(KeyboardLayer(index=i, name=f"Layer {i}") for i in range(4)),
        }
    )
    style = config.output.style.model_copy(
        update={"use_system_fonts": True, "palette": palette}
    )
    output = config.output.model_copy(update={"style": style})
    config = config.model_copy(update={"keyboard": keyboard, "output": output})
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    blank = SvalboardTargetKey(label="")
    cluster_data = FingerClusterData(
        blank, north_key=SvalboardTargetKey(label="", layer_switch=2)
    )
    cluster_width = 220.0

    with using_render_context(ctx):
        panels: list[tuple[Component, str]] = []
        for use_layer_colors, caption in ((True, "true"), (False, "false")):
            cluster = FingerCluster(
                cluster=cluster_data,
                side=KeyboardSide.LEFT,
                width=cluster_width,
                layer_qmk_index=0,
                has_double_south=False,
                use_layer_colors_on_keys=use_layer_colors,
                show_layer_indicators=True,
            )
            panels.append((cluster, caption))
        return _build_side_by_side(panels=panels)


def _build_show_transparent_fallthrough_mock() -> draw.Drawing:
    """Two single keys side-by-side: one with a faded "ghost" label
    (the ``true`` / fall-through behaviour) and one blank (the
    ``false`` behaviour). Painted as primitives rather than going
    through the full multi-layer transparency path so the mock stays
    self-contained.
    """
    panel_w = 110.0
    panel_h = 110.0
    key_w = 88.0
    key_h = 88.0
    radius = 6.0
    label_text = "K"
    label_font = 28.0

    def _key_panel(*, ghost: bool) -> Component:
        size = Size(panel_w, panel_h)

        def draw_at(d, origin):
            kx = origin.x + (panel_w - key_w) / 2
            ky = origin.y + (panel_h - key_h) / 2
            d.append(
                draw.Rectangle(
                    x=kx,
                    y=ky,
                    width=key_w,
                    height=key_h,
                    rx=radius,
                    ry=radius,
                    fill=_GREY_NEUTRAL,
                    stroke=_GREY_BORDER,
                    stroke_width=1.0,
                )
            )
            if ghost:
                d.append(
                    draw.Text(
                        label_text,
                        x=kx + key_w / 2,
                        y=ky + key_h / 2,
                        font_size=label_font,
                        font_family="Roboto, sans-serif",
                        text_anchor="middle",
                        dominant_baseline="central",
                        fill="#FFFFFF",
                        opacity=0.45,
                    )
                )

        return BaseComponent(size=size, draw_fn=draw_at)

    return _build_side_by_side(
        panels=[
            (_key_panel(ghost=True), "true (ghost label)"),
            (_key_panel(ghost=False), "false (blank)"),
        ]
    )


# ---------------------------------------------------------------------------
# Registry & main
# ---------------------------------------------------------------------------


BUILDERS: dict[str, MockBuilder] = {
    # Document-wide
    "margin": _build_margin_mock,
    "inset": _build_inset_mock,
    "section-spacing": _build_section_spacing_mock,
    "table-header-spacing": _build_table_header_spacing_mock,
    "table-col-spacing": _build_table_col_spacing_mock,
    "table-row-spacing": _build_table_row_spacing_mock,
    "column-gap": _build_column_gap_mock,
    # Cluster
    "finger-key-gap": _build_finger_key_gap_mock,
    "thumb-key-gap": _build_thumb_key_gap_mock,
    "layer-indicator-spacing": _build_layer_indicator_spacing_mock,
    # Section / legend internals
    "section-title-rule-gap": _build_section_title_rule_gap_mock,
    "chip-padding": _build_chip_padding_mock,
    "tap-dance-pill-padding": _build_tap_dance_pill_padding_mock,
    "macro-action-inset": _build_macro_action_inset_mock,
    # Overview / chrome
    "layer-badge-inset": _build_layer_badge_inset_mock,
    # Strokes
    "border-width": _build_border_width_mock,
    "chip-outline-stroke": _build_chip_outline_mock,
    "header-rule-stroke": _build_header_rule_stroke_mock,
    "layer-indicator-stroke": _build_layer_indicator_stroke_mock,
    "layer-connector-width": _build_layer_connector_width_mock,
    "layer-connector-dot-spacing": _build_layer_connector_dot_spacing_mock,
    # Flag options (before / after comparisons)
    "hold-symbol-position": _build_hold_symbol_position_mock,
    "layer-indicator-show": _build_layer_indicator_show_mock,
    "use-layer-colors-on-keys": _build_use_layer_colors_on_keys_mock,
    "show-transparent-fallthrough": _build_show_transparent_fallthrough_mock,
    # NOTE: ``layer_indicator_endpoint_inset`` is omitted — the connector
    # path it inset-trims only renders inside the keymap overview, which
    # would dwarf the rest of these mocks. Will revisit if the value
    # makes it into the configurable schema.
}


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for name, builder in BUILDERS.items():
        target = OUTPUT_ROOT / f"{name}.svg"
        try:
            drawing = builder()
        except Exception as exc:  # noqa: BLE001
            print(f"  {target.relative_to(ROOT)}: FAILED — {exc}")
            continue
        drawing.save_svg(str(target))
        size = target.stat().st_size
        print(f"  {target.relative_to(ROOT)} ({size // 1024} KB)")
    print(f"Wrote spacing mocks to {OUTPUT_ROOT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
