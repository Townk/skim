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

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import drawsvg as draw

from skim.application.render.composable import Component
from skim.application.render.font import (
    Font,
    FontSubsetter,
    FontUsageCollector,
    current_font_usage_collector,
    register_font_usage,
)
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
from skim.data.config import (
    KeyboardLayer,
    LayerColor,
    Palette,
    SkimConfig,
    Spacing,
    SplitSidePosition,
)
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


def _svalboard_config(*, num_layers: int = 4) -> SkimConfig:
    """SkimConfig wired to the curated Svalboard palette from
    ``samples/config/SvalCOLEMAK-config.yaml`` so colour mocks read
    like a real Svalboard render rather than a generic palette.
    """
    import yaml

    sample_path = ROOT / "samples" / "config" / "SvalCOLEMAK-config.yaml"
    with open(sample_path) as f:
        data = yaml.safe_load(f)
    sample_config = SkimConfig.model_validate(data)
    palette_layers = sample_config.output.style.palette.layers[:num_layers]

    config = SkimConfig()
    keyboard = config.keyboard.model_copy(
        update={
            "layers": tuple(
                KeyboardLayer(index=i, name=f"Layer {i}") for i in range(num_layers)
            )
        }
    )
    palette = config.output.style.palette.model_copy(
        update={
            "neutral_color": sample_config.output.style.palette.neutral_color,
            "layers": palette_layers,
        }
    )
    style = config.output.style.model_copy(
        update={"use_system_fonts": True, "palette": palette}
    )
    output = config.output.model_copy(update={"style": style})
    return config.model_copy(update={"keyboard": keyboard, "output": output})


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


def _embed_used_fonts(d: draw.Drawing) -> None:
    """Embed @font-face rules for fonts referenced by the rendered
    component, subsetted to the glyphs actually painted when a usage
    collector is active.

    Mirrors the option-images embed path: under
    :func:`using_render_context` the collector is automatically active,
    so a ``FontSubsetter`` produces a tiny SVG payload covering only
    the glyphs the component asked for. Outside that context (no
    collector active) we fall back to embedding every bundled font in
    full — needed by mocks that paint Nerd-Font glyphs whose fonts may
    not be installed system-wide.
    """
    collector = current_font_usage_collector()
    if collector is None:
        for font in Font:
            d.append_css(font.css_style)
        return
    subsetter = FontSubsetter(collector)
    css = subsetter.generate_subsetted_css()
    d.append_css(css if css else subsetter.generate_full_fonts_css())


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

        # Each band's cross-axis spans half the central key's width
        # and is centred on it — short markers rather than full-edge
        # spans, matching the half-cross-axis treatment used by the
        # margin / inset / table-spacing mocks.
        half = slots.center_width / 2.0
        center_x = center_left + slots.center_width / 2.0
        center_y = center_top + slots.center_width / 2.0

        # Top gap (between north and centre)
        _highlight_rect(
            d,
            x=offset + center_x - half / 2.0,
            y=offset + north_bottom,
            width=half,
            height=center_top - north_bottom,
        )
        # Bottom gap (between centre and south)
        south_top = slots.south_origin.y
        _highlight_rect(
            d,
            x=offset + center_x - half / 2.0,
            y=offset + center_bottom,
            width=half,
            height=south_top - center_bottom,
        )
        # Left gap (between west's right edge and centre's left edge)
        west_right = slots.west_origin.x + slots.outer_width
        _highlight_rect(
            d,
            x=offset + west_right,
            y=offset + center_y - half / 2.0,
            width=center_left - west_right,
            height=half,
        )
        # Right gap (between centre's right edge and east's left edge)
        east_left = slots.east_origin.x
        _highlight_rect(
            d,
            x=offset + center_right,
            y=offset + center_y - half / 2.0,
            width=east_left - center_right,
            height=half,
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

    The canvas paints with an explicit white background so the file's
    boundaries read distinctly from the light-grey keymap interior, and
    a thin square stroke around the canvas edge marks the SVG file's
    boundary. Showing a real keymap inside makes each value's role
    legible at a glance. The mock uses an exaggerated
    ``border_width = 4`` so the stroke reads cleanly even on the small
    canvas.
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
    # Light-grey keymap interior — contrasts the white canvas behind it
    # so the document's boundary is visible without depending on the
    # docs page's own background colour.
    keymap_bg = "#F3F4F6"
    palette = config.output.style.palette.model_copy(
        update={"background_color": keymap_bg}
    )
    style = config.output.style.model_copy(
        update={
            "border": Border(width=border_width, radius=border_radius),
            "show_layer_indicators": False,
            "palette": palette,
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
        # Paint the canvas white before the document so the bands and
        # border stroke read against an explicit background rather than
        # the SVG's default transparent fill.
        d.append(
            draw.Rectangle(
                x=0.0,
                y=0.0,
                width=canvas_w,
                height=canvas_h,
                fill="#FFFFFF",
                stroke="none",
            )
        )
        document.draw_at(d, Point(0.0, 0.0))

        if highlight == "margin":
            # Bands sit between canvas edge and the border stroke's
            # outer edge. The border path is centred at ``margin`` from
            # each edge with stroke ``border_width``, so its outer edge
            # sits at ``margin - border_width/2`` — the band's
            # thickness fills exactly that strip so it visually
            # represents the full margin value.
            #
            # The cross-axis length is half the available straight
            # edge between the rounded corners, centred along it. That
            # keeps each band as a short marker rather than spanning
            # corner-to-corner — easier to read against the keymap
            # without crowding the corner regions or overlapping the
            # adjacent bands.
            available = margin - border_width / 2.0
            corner_offset = margin + border_radius
            straight_w = canvas_w - 2 * corner_offset
            straight_h = canvas_h - 2 * corner_offset
            band_w = straight_w / 2.0
            band_h = straight_h / 2.0
            center_x = canvas_w / 2.0
            center_y = canvas_h / 2.0
            _highlight_rect(
                d,
                x=center_x - band_w / 2.0,
                y=0.0,
                width=band_w,
                height=available,
            )
            _highlight_rect(
                d,
                x=center_x - band_w / 2.0,
                y=canvas_h - available,
                width=band_w,
                height=available,
            )
            _highlight_rect(
                d,
                x=0.0,
                y=center_y - band_h / 2.0,
                width=available,
                height=band_h,
            )
            _highlight_rect(
                d,
                x=canvas_w - available,
                y=center_y - band_h / 2.0,
                width=available,
                height=band_h,
            )
        elif highlight == "inset":
            # Bands between the border path's inner edge and the
            # content. ``content_offset = margin + border_width + inset``
            # so the band fills the gap from the border stroke's
            # inner edge (``margin + border_width/2``) to the content
            # origin (``margin + border_width + inset``). Thickness is
            # therefore ``border_width/2 + inset`` — the full visible
            # inset region — so the band touches both the border and
            # the content without painting over either. Mirrors the
            # ``margin`` highlight, which fills the canvas-edge → outer
            # stroke gap.
            #
            # The cross-axis length is half the available straight
            # extent between the rounded corners, centred along that
            # extent — short markers rather than corner-to-corner spans.
            inner_edge = margin + border_width / 2.0
            band_thickness = border_width / 2.0 + inset
            content_origin = margin + border_width + inset
            straight_w = canvas_w - 2 * content_origin
            straight_h = canvas_h - 2 * content_origin
            band_w = straight_w / 2.0
            band_h = straight_h / 2.0
            center_x = canvas_w / 2.0
            center_y = canvas_h / 2.0
            _highlight_rect(
                d,
                x=center_x - band_w / 2.0,
                y=inner_edge,
                width=band_w,
                height=band_thickness,
            )
            _highlight_rect(
                d,
                x=center_x - band_w / 2.0,
                y=canvas_h - inner_edge - band_thickness,
                width=band_w,
                height=band_thickness,
            )
            _highlight_rect(
                d,
                x=inner_edge,
                y=center_y - band_h / 2.0,
                width=band_thickness,
                height=band_h,
            )
            _highlight_rect(
                d,
                x=canvas_w - inner_edge - band_thickness,
                y=center_y - band_h / 2.0,
                width=band_thickness,
                height=band_h,
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

        # File-boundary outline — thin square stroke flush with the
        # canvas edge so the SVG's own bounds read distinctly from the
        # keymap's rounded border. Drawn last so highlights and the
        # rounded border don't paint over it.
        d.append(
            draw.Rectangle(
                x=0.5,
                y=0.5,
                width=canvas_w - 1.0,
                height=canvas_h - 1.0,
                fill="none",
                stroke="#9CA3AF",
                stroke_width=1.0,
            )
        )

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


def _grey_td(
    *,
    idx: str = "0",
    name: str | None = None,
    variants: tuple[str, str, str, str] | None = None,
) -> SvalboardTapDance[SvalboardTargetKey]:
    """Tap-dance with all four variants populated so cells render.

    ``variants`` overrides the per-cell labels (TAP / HOLD /
    DOUBLE-TAP / TAP & HOLD). When ``None`` every cell renders as
    an em-dash placeholder.
    """
    if variants is None:
        variants = ("—", "—", "—", "—")
    return SvalboardTapDance(
        id=idx,
        tap=SvalboardTargetKey(label=variants[0]),
        hold=SvalboardTargetKey(label=variants[1]),
        double_tap=SvalboardTargetKey(label=variants[2]),
        tap_then_hold=SvalboardTargetKey(label=variants[3]),
        name=name,
    )


@dataclass(frozen=True)
class _SectionStage:
    """Computed geometry of the shared stripe + TapDance body stage."""

    drawing: draw.Drawing
    stripe: Component
    stripe_metrics: SectionStripeMetrics
    td_metrics: TapDanceMetrics
    x: float
    y: float
    body_w: float
    body_y: float
    header_height: float
    row_height: float
    cell_width: float
    name_column_width: float
    num_rows: int


def _section_stage_ctx() -> RenderContext:
    """Build a render context for the section / table spacing mocks
    with the embedded-font setup wired in.

    ``use_system_fonts=False`` so the painted glyphs reference the
    bundled font families (``Key-Symbols``, ``Finger-Key-Label``)
    that :func:`_embed_used_fonts` writes into the SVG — rather than
    system fallbacks like ``'Symbols Nerd Font'`` that won't exist
    on every viewer's machine.
    """
    config = _grey_config()
    style = config.output.style.model_copy(update={"use_system_fonts": False})
    config = config.model_copy(
        update={"output": config.output.model_copy(update={"style": style})}
    )
    keymap = _empty_keymap()
    return RenderContext.build(config=config, keymap=keymap)


def _build_section_stage(
    ctx: RenderContext,
    *,
    num_rows: int = 1,
    variants: tuple[str, str, str, str] | None = None,
    cell_width: float | None = None,
) -> _SectionStage:
    """Lay out the shared stripe + TapDance body the section / table
    spacing mocks paint on top of, so all six illustrations share the
    same canvas shape and the docs render them at matching font sizes.

    ``num_rows`` controls how many tap-dance rows the body stacks
    (separated by ``table_row_spacing``). Defaults to 1 — enough for
    every mock except ``table-row-spacing``, which needs at least
    two rows to expose the inter-row gap.

    ``variants`` overrides each row's per-cell labels (TAP / HOLD /
    DOUBLE-TAP / TAP & HOLD). When ``None`` cells render as
    em-dash placeholders; pass real labels when the mock needs the
    cells to read like a real keymap (e.g. for the pill-padding
    illustration).
    """
    if num_rows < 1:
        raise ValueError("num_rows must be >= 1")
    section_spacing = ctx.document_metrics.section_spacing
    stripe_metrics = SectionStripeMetrics.from_ctx(ctx)
    td_metrics = TapDanceMetrics.from_ctx(ctx)
    stripe_width = 320.0
    stripe = SectionStripe(
        title="TAP-DANCE", count=num_rows, width=stripe_width, accent_line=_GREY_BORDER
    )
    # Pin the TapDance body's column geometry so the row + header
    # fit inside ``stripe_width`` rather than expanding past it.
    # Hides the name column (``name_column_width=0``) and shrinks
    # the variant cells to a width that keeps the four cells +
    # column spacings within budget.
    td_cell_width = cell_width if cell_width is not None else 56.0
    td_name_column_width = 0.0
    header = TapDanceColumnHeader(
        text_color=_GREY_TEXT,
        name_column_width=td_name_column_width,
        cell_width=td_cell_width,
    )
    rows = [
        TapDanceRow(
            td=_grey_td(idx=str(i), variants=variants),
            accent_fill=_GREY_NEUTRAL,
            accent_line=_GREY_BORDER,
            text_color=_GREY_TEXT,
            name_column_width=td_name_column_width,
            cell_width=td_cell_width,
        )
        for i in range(num_rows)
    ]
    row_height = rows[0].size.height
    row_spacing = td_metrics.table_row_spacing
    body_w = max(header.size.width, *(r.size.width for r in rows))
    body_h = header.size.height + num_rows * row_height + (num_rows - 1) * row_spacing
    canvas_w = max(stripe.size.width, body_w) + 24.0
    canvas_h = stripe.size.height + section_spacing + body_h + 24.0
    d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

    x = 12.0
    y = 12.0
    stripe.draw_at(d, Point(x, y))
    body_y = y + stripe.size.height + section_spacing
    header.draw_at(d, Point(x, body_y))
    for i, row in enumerate(rows):
        row.draw_at(
            d,
            Point(x, body_y + header.size.height + i * (row_height + row_spacing)),
        )

    return _SectionStage(
        drawing=d,
        stripe=stripe,
        stripe_metrics=stripe_metrics,
        td_metrics=td_metrics,
        x=x,
        y=y,
        body_w=body_w,
        body_y=body_y,
        header_height=header.size.height,
        row_height=row_height,
        cell_width=td_cell_width,
        name_column_width=td_name_column_width,
        num_rows=num_rows,
    )


def _build_section_spacing_mock() -> draw.Drawing:
    """Highlight the gap between a section's stripe and the first body row.

    ``section_spacing`` lands as the inter-child gap inside the
    ``Column`` MacroSection / TapDanceSection use to stack the title
    stripe and the body. It also splits named-vs-unnamed macro
    sub-blocks. The mock paints the stripe + a single TD row and
    highlights the gap between them.
    """
    ctx = _section_stage_ctx()

    with using_render_context(ctx):
        stage = _build_section_stage(ctx)

        # Highlight the section_spacing band between the stripe rule's
        # bottom edge and the body's top. The rule line is centred at
        # ``y + stripe.size.height`` with stroke ``rule_stroke``, so
        # half the stroke extends into the gap; the band starts past
        # that half-stroke (snapped up to a whole pixel so the visual
        # gap is consistent) and ends flush with the body, never
        # painting over the rule.
        rule_y = stage.y + stage.stripe.size.height
        band_y = math.ceil(rule_y + stage.stripe_metrics.rule_stroke / 2.0)
        band_w = stage.body_w / 2.0
        _highlight_rect(
            stage.drawing,
            x=stage.x + (stage.body_w - band_w) / 2.0,
            y=band_y,
            width=band_w,
            height=stage.body_y - band_y,
        )
        _embed_used_fonts(stage.drawing)

    return stage.drawing


def _build_table_header_spacing_mock() -> draw.Drawing:
    """Highlight every gap that ``table_header_spacing`` controls.

    The value lands in two places inside a table-shaped section:

    1. Between the column header text and the first variant row —
       baked into the header's reported height (the gap sits at the
       bottom of the header's bbox; the text is top-anchored).
    2. Between a row's chip-and-name block and the first variant
       cell (or, in a :func:`MacroRow`, between the chip and the
       first pill).

    Both bands paint here so the docs make clear that the same value
    drives both axes.

    Shares the stripe + body stage with
    :func:`_build_section_spacing_mock` so the canvas matches.
    """
    ctx = _section_stage_ctx()

    with using_render_context(ctx):
        stage = _build_section_stage(ctx)
        header_spacing = stage.td_metrics.table_header_spacing

        # (1) Header text → first row gap. Halve the band's
        # horizontal extent and centre it across the body — matches
        # the half-cross-axis treatment of the other section / table
        # mocks.
        band_w = stage.body_w / 2.0
        _highlight_rect(
            stage.drawing,
            x=stage.x + (stage.body_w - band_w) / 2.0,
            y=stage.body_y + stage.header_height - header_spacing,
            width=band_w,
            height=header_spacing,
        )

        # (2) Row chip → first cell gap. Same value drives the
        # horizontal indent inside :func:`TapDanceRow` (and the
        # equivalent chip-to-first-pill gap inside :func:`MacroRow`).
        # Cross-axis here is the row height, so halve that and centre
        # the band on the row.
        row_top = stage.body_y + stage.header_height
        gap_band_h = stage.row_height / 2.0
        gap_band_y = row_top + (stage.row_height - gap_band_h) / 2.0
        _highlight_rect(
            stage.drawing,
            x=stage.x + stage.td_metrics.chip_width + stage.name_column_width,
            y=gap_band_y,
            width=header_spacing,
            height=gap_band_h,
        )
        _embed_used_fonts(stage.drawing)

    return stage.drawing


def _build_table_col_spacing_mock() -> draw.Drawing:
    """Highlight the gaps between adjacent variant cells in a TD row.

    Shares the stripe + body stage with
    :func:`_build_section_spacing_mock`; the bands span each gap
    between the four variant cells, vertically aligned with the
    first row.
    """
    ctx = _section_stage_ctx()

    with using_render_context(ctx):
        stage = _build_section_stage(ctx)
        col_spacing = stage.td_metrics.table_col_spacing
        header_spacing = stage.td_metrics.table_header_spacing
        # Cells start after the chip + name column + header_spacing
        # gap (matches :func:`TapDanceRow`'s ``cells_start_x``).
        cells_start_x = (
            stage.x
            + stage.td_metrics.chip_width
            + stage.name_column_width
            + header_spacing
        )
        row_top = stage.body_y + stage.header_height
        # Halve the band's vertical extent (the cross-axis here) and
        # centre it on the row — matches the half-cross-axis
        # treatment of the other mocks.
        band_h = stage.row_height / 2.0
        band_y = row_top + (stage.row_height - band_h) / 2.0
        for i in range(3):
            gap_x = cells_start_x + (i + 1) * stage.cell_width + i * col_spacing
            _highlight_rect(
                stage.drawing,
                x=gap_x,
                y=band_y,
                width=col_spacing,
                height=band_h,
            )
        _embed_used_fonts(stage.drawing)

    return stage.drawing


def _build_table_row_spacing_mock() -> draw.Drawing:
    """Highlight the gaps between adjacent rows in a tap-dance table.

    Stages the same stripe + body as the other section / table mocks
    but stacks two rows so the inter-row gap exists at all. Same
    canvas geometry otherwise — the only delta is the extra row plus
    its preceding ``table_row_spacing``.
    """
    ctx = _section_stage_ctx()

    with using_render_context(ctx):
        stage = _build_section_stage(ctx, num_rows=2)
        row_spacing = stage.td_metrics.table_row_spacing
        # Gap sits between the two rows: from row1's bottom edge to
        # row2's top edge. Halve horizontally and centre across the
        # body — matches the cross-axis half treatment.
        gap_y = stage.body_y + stage.header_height + stage.row_height
        band_w = stage.body_w / 2.0
        _highlight_rect(
            stage.drawing,
            x=stage.x + (stage.body_w - band_w) / 2.0,
            y=gap_y,
            width=band_w,
            height=row_spacing,
        )
        _embed_used_fonts(stage.drawing)

    return stage.drawing


# ---------------------------------------------------------------------------
# Section / legend internals
# ---------------------------------------------------------------------------


def _build_section_title_rule_gap_mock() -> draw.Drawing:
    """Highlight the gap between the section title and the rule below it.

    The strip is top-anchored: the title's em-box top sits at the
    strip's top edge, with no dangling space above. The rule line
    sits ``title_rule_gap`` below the title's em-box bottom — the
    only configurable vertical value inside the strip.

    Shares the stripe + TapDance body staging with
    :func:`_build_section_spacing_mock` so the two illustrations
    sit on the same canvas shape; only the highlight band differs.
    """
    ctx = _section_stage_ctx()

    with using_render_context(ctx):
        stage = _build_section_stage(ctx)

        # Highlight the gap from the title's em-box bottom (=
        # title_font_size below the strip top) down to the rule line.
        # Halve the band's horizontal extent and centre it under the
        # title text so the band reads as a marker rather than a full
        # stripe-width fill — matches the half-width treatment used
        # for the section_spacing / margin / inset mocks.
        band_w = stage.stripe.size.width / 2.0
        _highlight_rect(
            stage.drawing,
            x=stage.x + (stage.stripe.size.width - band_w) / 2.0,
            y=stage.y + stage.stripe_metrics.title_font_size,
            width=band_w,
            height=stage.stripe_metrics.title_rule_gap,
        )
        _embed_used_fonts(stage.drawing)

    return stage.drawing


def _build_chip_padding_mock() -> draw.Drawing:
    """Highlight every gap that ``chip_padding`` controls inside a chip.

    ``chip_padding`` lands in two pairs of positions:

    1. Inside the chip body — leading (chip's left edge → glyph) and
       trailing (glyph → chip's right edge).
    2. Inside the chip's name area — leading (chip body → name text)
       and trailing (name text → outline's right edge).

    The :func:`TapDanceRow` composable paints with a fixed
    ``chip_width`` today (auto-sizing the chip to its glyph is a
    pending refactor), so this mock paints a custom chip whose body
    is sized to the actual glyph plus 2 × ``chip_padding``. That way
    the chip-internal bands land at the conceptually-correct
    positions instead of overlapping the glyph the fixed-width chip
    would otherwise centre.

    Each band's vertical extent is half the row height, centred on
    the row, so the band reads as a marker rather than a full-height
    fill. Bands are inset by half the chip-outline stroke so the
    highlights never paint over the chip border.

    ``use_system_fonts=False`` so the painted glyph + name use the
    bundled font families that match :func:`_embed_used_fonts`'s
    @font-face rules — otherwise the Nerd-Font glyph renders as a
    tofu box on browsers without ``Symbols Nerd Font`` installed,
    and PIL-measured text widths drift from the browser's actual
    rendering, causing the trailing band to overlap the name.
    """
    from skim.application.render.adjustable_text import AdjustableText, measure_text_width
    from skim.application.render.render_context import TextStyle
    from skim.application.render.rich_text import RichText
    from skim.application.render.tap_dance import _filled_chip_path

    config = _grey_config()
    style = config.output.style.model_copy(update={"use_system_fonts": False})
    config = config.model_copy(update={"output": config.output.model_copy(update={"style": style})})
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    with using_render_context(ctx):
        metrics = TapDanceMetrics.from_ctx(ctx)
        name_text = "MY-TD"
        chip_padding = metrics.chip_padding
        row_height = metrics.row_height
        stroke_inset = metrics.chip_stroke_width / 2.0

        # Measure the chip glyph (Nerd-Font icon + id) and the name
        # text via the same PIL-based helper the renderer uses, so
        # widths land where the painted text actually starts and ends.
        chip_glyph_style = TextStyle(
            font=Font.FINGER_KEY,
            size=metrics.chip_inner_font_size,
            color="#FFF",
        )
        chip_glyph_el = RichText(
            text="%%nf-md-keyboard_close; 0",
            style=chip_glyph_style,
            text_anchor="start",
            dominant_baseline="central",
        )
        glyph_w = chip_glyph_el.size.width
        glyph_h = chip_glyph_el.size.height

        # Auto-size the chip body so glyph + 2 × chip_padding fits
        # exactly. Mirrors the layout auto-sizing will produce once
        # :func:`TapDanceRow` is refactored to size its chip from
        # the glyph instead of a fixed ratio.
        chip_w = glyph_w + 2 * chip_padding

        natural_name_w = measure_text_width(name_text, Font.FINGER_KEY, metrics.name_font_size)
        name_column_w = 2 * chip_padding + natural_name_w
        outline_w = chip_w + name_column_w

        offset = 12.0
        canvas_w = outline_w + 2 * offset
        canvas_h = row_height + 2 * offset
        d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

        chip_x = offset
        chip_y = offset
        # Filled chip body — rounded left corners only since the
        # outline extends rightward across the name area.
        d.append(
            _filled_chip_path(
                x=chip_x,
                y=chip_y,
                width=chip_w,
                height=row_height,
                radius=metrics.chip_corner_radius,
                round_right=False,
                fill=_GREY_NEUTRAL,
            )
        )
        # Outline rectangle around chip + name area.
        d.append(
            draw.Rectangle(
                x=chip_x,
                y=chip_y,
                width=outline_w,
                height=row_height,
                rx=metrics.chip_corner_radius,
                ry=metrics.chip_corner_radius,
                fill="none",
                stroke=_GREY_BORDER,
                stroke_width=metrics.chip_stroke_width,
            )
        )
        # Chip glyph centred in the chip body.
        chip_glyph_el.draw_at(
            d,
            Point(
                chip_x + (chip_w - glyph_w) / 2.0,
                chip_y + row_height / 2.0
                + metrics.chip_inner_text_baseline_offset
                - glyph_h / 2.0,
            ),
        )
        # Name text inside the name area, ``chip_padding`` past the
        # chip body's right edge.
        name_el = AdjustableText(
            text=name_text,
            style=TextStyle(
                font=Font.FINGER_KEY,
                size=metrics.name_font_size,
                color=_GREY_TEXT,
            ),
            text_anchor="start",
            dominant_baseline="central",
        )
        name_el.draw_at(
            d,
            Point(
                chip_x + chip_w + chip_padding,
                chip_y + row_height / 2.0
                + metrics.chip_inner_text_baseline_offset
                - name_el.size.height / 2.0,
            ),
        )

        # Embed the bundled fonts so the painted glyph + text render
        # without depending on the user's system fonts.
        _embed_used_fonts(d)

        # Cross-axis (vertical) is the row height; halve it and
        # centre the band on the row.
        band_h = row_height / 2.0
        band_y = offset + (row_height - band_h) / 2.0
        # Outer (chip-outline-edge-touching) bands lose a half-stroke
        # so they don't paint over the outline; inner bands (away
        # from any stroke) keep the full ``chip_padding`` width.
        outer_band_w = chip_padding - stroke_inset

        # (1a) Inside chip body — leading edge to glyph.
        _highlight_rect(
            d,
            x=chip_x + stroke_inset,
            y=band_y,
            width=outer_band_w,
            height=band_h,
        )
        # (1b) Inside chip body — glyph to right edge.
        _highlight_rect(
            d,
            x=chip_x + chip_w - chip_padding,
            y=band_y,
            width=chip_padding,
            height=band_h,
        )
        # (2a) Name area — chip body's right edge to the name text.
        _highlight_rect(
            d,
            x=chip_x + chip_w,
            y=band_y,
            width=chip_padding,
            height=band_h,
        )
        # (2b) Name area — name text end to outline's right edge.
        _highlight_rect(
            d,
            x=chip_x + outline_w - chip_padding,
            y=band_y,
            width=outer_band_w,
            height=band_h,
        )

    return d


def _build_tap_dance_pill_padding_mock() -> draw.Drawing:
    """Highlight the symmetric inset inside each TD pill (cell).

    Today the cell width is fixed; this band shows the configurable
    ``tap_dance_pill_padding`` value that an auto-sized cell will use
    once the refactor lands. Two bands per cell — leading and
    trailing — across all four variant cells in the row, since the
    same value drives every cell's internal padding.

    Shares the stripe + body stage with
    :func:`_build_table_col_spacing_mock` so the canvas matches the
    rest of the section / table mocks.
    """
    from skim.application.render.render_context import TextStyle
    from skim.application.render.rich_text import RichText

    ctx = _section_stage_ctx()

    with using_render_context(ctx):
        td_metrics_pre = TapDanceMetrics.from_ctx(ctx)
        pill_padding = td_metrics_pre.tap_dance_pill_padding
        # Same Nerd-Font glyph in all four cells so a single
        # ``cell_width`` fits each one with exactly ``pill_padding``
        # of visible space on either side. Different glyphs would
        # mean different widths, and ``TapDanceRow`` only accepts a
        # single ``cell_width`` for all cells.
        glyph_token = "%%nf-md-apple_keyboard_shift;"
        glyph_el = RichText(
            text=glyph_token,
            style=TextStyle(
                font=Font.FINGER_KEY,
                size=td_metrics_pre.cell_label_font_size,
                color=_GREY_TEXT,
            ),
            text_anchor="start",
            dominant_baseline="central",
        )
        # Auto-size cells so visible padding == ``pill_padding``,
        # making the highlight bands fill the actual gap from cell
        # border to glyph edge — what ``pill_padding`` will
        # represent once the auto-sizing refactor lands.
        cell_w = glyph_el.size.width + 2 * pill_padding
        stage = _build_section_stage(
            ctx,
            variants=(glyph_token, glyph_token, glyph_token, glyph_token),
            cell_width=cell_w,
        )
        col_spacing = stage.td_metrics.table_col_spacing
        header_spacing = stage.td_metrics.table_header_spacing
        # Cells start after the chip + name column + header_spacing
        # gap (matches :func:`TapDanceRow`'s ``cells_start_x``).
        cells_start_x = (
            stage.x
            + stage.td_metrics.chip_width
            + stage.name_column_width
            + header_spacing
        )
        row_top = stage.body_y + stage.header_height
        # Half-cross-axis (vertical) treatment: halve the band's
        # height and centre it on the row.
        band_h = stage.row_height / 2.0
        band_y = row_top + (stage.row_height - band_h) / 2.0
        for i in range(4):
            cell_x = cells_start_x + i * (stage.cell_width + col_spacing)
            # Leading inset — cell left edge to glyph.
            _highlight_rect(
                stage.drawing,
                x=cell_x,
                y=band_y,
                width=pill_padding,
                height=band_h,
            )
            # Trailing inset — glyph to cell right edge.
            _highlight_rect(
                stage.drawing,
                x=cell_x + stage.cell_width - pill_padding,
                y=band_y,
                width=pill_padding,
                height=band_h,
            )
        _embed_used_fonts(stage.drawing)

    return stage.drawing


def _build_macro_action_inset_mock() -> draw.Drawing:
    """Highlight the three visible-padding regions inside a
    :func:`MacroPill`: pill edge → icon left edge, icon right edge →
    text left edge, and text right edge → pill edge.

    A single ``macro_action_inset`` value drives all three regions —
    :func:`MacroPill` positions the icon's left edge at ``inset``
    from the pill border and snugs the text to the icon-to-text and
    trailing inset gaps, so each visible padding equals ``inset``.

    Each band's vertical extent is half the pill height, centred on
    the pill, so the band reads as a marker rather than a full-pill
    fill. ``use_system_fonts=False`` so the painted text uses the
    bundled :func:`_embed_used_fonts` family (``Finger-Key-Label``)
    that PIL also measures against — keeps the trailing band
    aligned with the actual end of the label rather than drifting
    when the browser falls back to a different system font.
    """
    config = _grey_config()
    style = config.output.style.model_copy(update={"use_system_fonts": False})
    config = config.model_copy(
        update={"output": config.output.model_copy(update={"style": style})}
    )
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

        inset = metrics.macro_action_inset
        icon_w = metrics.pill_icon_width
        pill_w = pill.size.width
        pill_left = offset
        pill_right = pill_left + pill_w
        icon_left = pill_left + inset
        icon_right = icon_left + icon_w
        text_right = pill_right - inset

        # The highlight rectangle's stroke is centred on its path —
        # half the stroke pokes outside the nominal rect on each side.
        # If we positioned a band flush with the pill border or with
        # the icon, that half-stroke would paint over the pill stroke
        # (visible as a doubled-up edge) or eat into the icon (the
        # circle visually shrinks by ~1 px on each side). Inset each
        # band's nominal edge by the half-stroke values below so both
        # the fill and the stroke stop short of the touched element.
        pad_half = _HIGHLIGHT_STROKE_WIDTH / 2.0  # half the pad's own stroke
        pill_half = 0.5  # half the pill background's stroke (default 1.0)

        # Half-cross-axis (vertical) treatment: halve the band's
        # height and centre it on the pill rectangle.
        pill_top = offset + (metrics.pill_row_height - metrics.pill_height) / 2
        band_h = metrics.pill_height / 2.0
        band_y = pill_top + (metrics.pill_height - band_h) / 2.0

        # The pill stroke takes ``pill_half`` out of the leading and
        # trailing inset regions (the pill border's outer half sits
        # outside the configured ``inset`` region but its inner half
        # eats into the visible whitespace). To keep the three bands
        # visually identical, size every band to the most-constrained
        # one (pad1 / pad3) and centre pad2 inside its larger region.
        band_w = inset - pill_half - 2 * pad_half

        # (1) Leading visible padding — between pill border (inner
        # stroke edge) and the icon's left edge.
        pad1_x = pill_left + pill_half + pad_half
        _highlight_rect(d, x=pad1_x, y=band_y, width=band_w, height=band_h)
        # (2) Icon-to-text visible gap, centred between icon right
        # edge and text left edge so its visible extent matches the
        # other two bands.
        text_left = icon_right + inset
        pad2_centre = (icon_right + text_left) / 2.0
        pad2_x = pad2_centre - band_w / 2.0
        _highlight_rect(d, x=pad2_x, y=band_y, width=band_w, height=band_h)
        # (3) Trailing visible padding — text end to pill border.
        pad3_right = pill_right - pill_half - pad_half
        pad3_x = pad3_right - band_w
        _highlight_rect(d, x=pad3_x, y=band_y, width=band_w, height=band_h)

        _embed_used_fonts(d)

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
    5. Trailing inset (``inset * 2``) — name end → badge edge,
       painted as two adjacent ``inset``-wide bands so the doubled
       value reads as ``inset + inset`` rather than a single
       differently-sized region.

    Two stacked badges show the right-alignment in action: index ``0``
    sits with leading whitespace inside the index column and ``12``
    fills it. Painted text uses the bundled ``Finger-Key-Label``
    family that PIL measures against, so the trailing band aligns
    with the actual end of the label rather than drifting when the
    browser falls back to a different system font.
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

        # Half-cross-axis (vertical) treatment: halve the band height
        # and centre it on each badge.
        band_h = badge_height / 2.0
        band_dy = (badge_height - band_h) / 2.0

        # The highlight rectangle's stroke is centred on its path, so
        # half the stroke pokes outside the nominal rect on each
        # side. Inset every band's nominal edge by ``pad_half`` so
        # the visible stroke stops exactly at the touched element
        # (badge edge, index column, name text, or the boundary
        # between pad3a / pad3b) instead of poking 1 px past it.
        pad_half = _HIGHLIGHT_STROKE_WIDTH / 2.0
        # Each band's nominal width is the configured ``inset`` minus
        # both stroke clearances. With ``pad_half`` of clearance on
        # each side, the visible stroke spans exactly ``inset`` —
        # the configured value reads correctly across all four bands.
        band_w = inset - 2 * pad_half

        # Bundled Roboto family — same one ``_measure_badge_text_width``
        # measures against. Painting with this family keeps the
        # trailing band's left edge flush with the actual end of the
        # rendered label.
        text_family = Font.FINGER_KEY.value

        for row, idx_text in enumerate(rows):
            badge_y = offset + row * (badge_height + badge_gap)
            cy = badge_y + badge_height / 2
            band_y = badge_y + band_dy

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
                    font_family=text_family,
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
                    font_family=text_family,
                    fill="#FFFFFF",
                )
            )

            # (1) Leading inset — badge edge → index column.
            _highlight_rect(
                d, x=offset + pad_half, y=band_y, width=band_w, height=band_h
            )
            # (2) Inter-column inset — index → name.
            _highlight_rect(
                d,
                x=index_right_x + pad_half,
                y=band_y,
                width=band_w,
                height=band_h,
            )
            # (3a) + (3b) Trailing inset — painted as two adjacent
            # ``inset``-wide bands so the configured ``inset * 2``
            # trailing gap reads as two stacked values rather than a
            # single differently-sized region. pad3a sits flush with
            # the name's right edge; pad3b's right stroke ends at the
            # badge's right edge; the two visible extents meet at
            # ``trailing_midpoint`` without overlap.
            trailing_left_x = offset + badge_width - inset * 2
            trailing_midpoint = trailing_left_x + inset
            _highlight_rect(
                d,
                x=trailing_left_x + pad_half,
                y=band_y,
                width=band_w,
                height=band_h,
            )
            _highlight_rect(
                d,
                x=trailing_midpoint + pad_half,
                y=band_y,
                width=band_w,
                height=band_h,
            )

        # The badge text is painted via raw ``draw.Text`` (not the
        # composable ``AdjustableText`` / ``RichText``), so the active
        # font-usage collector never sees these characters. Register
        # them explicitly so :func:`_embed_used_fonts` produces a
        # subsetted SVG instead of falling back to the full bundled
        # fonts (~4 MB payload).
        for idx_text in rows:
            register_font_usage(Font.FINGER_KEY, idx_text)
        register_font_usage(Font.FINGER_KEY, name_text)

        _embed_used_fonts(d)

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

        # Each band's cross-axis (its width) spans half the key it
        # sits above, centred on the key — short markers rather than
        # full-edge spans, matching the half-cross-axis treatment used
        # by the margin / inset / table-spacing / finger-key-gap mocks.
        for key_origin, key_width in (
            (slots.pad_origin, slots.pad_width),
            (slots.nail_origin, slots.nail_width),
            (slots.up_origin, slots.up_width),
            (slots.knuckle_origin, slots.knuckle_width),
        ):
            band_w = key_width / 2.0
            _highlight_rect(
                d,
                x=offset + key_origin.x + (key_width - band_w) / 2.0,
                y=offset + key_origin.y - inset,
                width=band_w,
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

    ``use_system_fonts=False`` so the chip's Nerd-Font glyph
    references the bundled ``Key-Symbols`` family that
    :func:`_embed_used_fonts` writes into the SVG; otherwise the
    glyph renders as a tofu box on browsers without
    ``Symbols Nerd Font`` installed.
    """
    from skim.application.render.adjustable_text import measure_text_width

    config = _grey_config()
    style = config.output.style.model_copy(update={"use_system_fonts": False})
    config = config.model_copy(
        update={"output": config.output.model_copy(update={"style": style})}
    )
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

        _embed_used_fonts(d)

    return d


def _build_header_rule_stroke_mock() -> draw.Drawing:
    """Highlight ``Strokes.header_rule`` as a rose-coloured rule line
    underneath a SectionStripe title.

    Shares the stripe + TapDance body stage with
    :func:`_build_section_title_rule_gap_mock` so the two
    illustrations sit on the same canvas shape; only the
    highlight differs.
    """
    ctx = _section_stage_ctx()

    with using_render_context(ctx):
        stage = _build_section_stage(ctx)

        # Rose overlay on the rule line at the same y position the
        # stripe paints its own rule (=
        # ``stage.y + stage.stripe.size.height``). The overlay's
        # stroke width matches the painted rule so the rose
        # exactly covers the underlying stroke.
        rule_y = stage.y + stage.stripe.size.height
        stage.drawing.append(
            draw.Line(
                sx=stage.x,
                sy=rule_y,
                ex=stage.x + stage.stripe.size.width,
                ey=rule_y,
                stroke=_HIGHLIGHT,
                stroke_width=stage.stripe_metrics.rule_stroke,
            )
        )
        _embed_used_fonts(stage.drawing)

    return stage.drawing


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


def _panel_extents(component: Component) -> tuple[Size, Point]:
    """Return ``(overflow_size, overflow_offset)`` for any component.

    Composables that paint chrome past their keys-only bbox (finger /
    thumb clusters with layer indicators) expose an
    ``overflow_size`` and an ``overflow_offset`` on their metrics —
    the latter is the negative-magnitude vector from the keys-only
    origin to the overflow bbox's top-left corner. Plain components
    (no metrics, or metrics without overflow) fall back to the
    component's own ``size`` and a zero offset.
    """
    metrics = getattr(component, "metrics", None)
    if metrics is not None:
        overflow_size = getattr(metrics, "overflow_size", None)
        overflow_offset = getattr(metrics, "overflow_offset", None)
        if overflow_size is not None and overflow_offset is not None:
            return overflow_size, overflow_offset
    return component.size, Point(0.0, 0.0)


def _build_side_by_side(
    *,
    panels: list[tuple[Component, str]],
    panel_gap: float = 28.0,
    outer_padding: float = 16.0,
    label_font_size: float = 12.0,
) -> draw.Drawing:
    """Render N components horizontally with a caption under each.

    All panels' **keys-only** origins align on a shared horizontal
    line — the canvas reserves enough headroom at the top to fit the
    worst-case overflow above any panel, so chrome (layer indicators,
    thumb double-down badges) that protrudes past the keys-only bbox
    lands on canvas without dragging the keys themselves out of
    alignment with the panels that don't have such chrome.
    """
    label_gap = 8.0
    label_height = label_font_size + label_gap
    extents = [_panel_extents(c) for c, _ in panels]

    # Shared headroom = the largest amount any panel's overflow
    # extends ABOVE its keys-only origin. Translates every panel's
    # keys-only origin down by this amount so they line up.
    headroom = max(max(0.0, -offset.y) for _, offset in extents)
    # Shared footroom = the largest amount any panel's overflow
    # extends BELOW its keys-only bottom edge.
    footroom = max(
        max(
            0.0,
            (overflow_size.height + offset.y) - component.size.height,
        )
        for (component, _), (overflow_size, offset) in zip(panels, extents, strict=True)
    )
    keys_origin_y = outer_padding + headroom
    keys_max_h = max(c.size.height for c, _ in panels)
    canvas_h = keys_origin_y + keys_max_h + footroom + label_height + outer_padding

    total_w = sum(size.width for size, _ in extents) + panel_gap * (len(panels) - 1)
    canvas_w = total_w + 2 * outer_padding
    d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

    cursor_x = outer_padding
    for (component, caption), (overflow_size, overflow_offset) in zip(panels, extents, strict=True):
        # Each panel's keys-only origin lands at the same y; the
        # overflow chrome fills upward / leftward as needed.
        keys_origin = Point(
            cursor_x - overflow_offset.x,
            keys_origin_y,
        )
        component.draw_at(d, keys_origin)
        d.append(
            draw.Text(
                caption,
                x=cursor_x + overflow_size.width / 2,
                y=keys_origin_y + keys_max_h + footroom + label_gap,
                font_size=label_font_size,
                text_anchor="middle",
                dominant_baseline="text-before-edge",
                font_family="Roboto, sans-serif",
                fill=_GREY_TEXT,
            )
        )
        cursor_x += overflow_size.width + panel_gap

    return d


def _build_hold_symbol_position_mock() -> draw.Drawing:
    """Three LEFT thumb clusters illustrating the three
    ``hold_symbol_position`` modes. Each pad / up / nail / knuckle
    key carries a real hold-tap label (modifier glyph on hold,
    short key name on tap) so the swap behaviour reads at a glance.
    The default skim palette renders the cluster in colour rather
    than greyscale so the modifier glyphs and the down-key fill
    contrast cleanly.
    """
    # Use the curated Svalboard palette so the cluster reads like a
    # real Svalboard render, not a generic Skim default. Override
    # ``use_system_fonts`` off so the painted Nerd-Font glyphs
    # reference the bundled ``Key-Symbols`` family that
    # :func:`_embed_used_fonts` writes into the SVG, instead of the
    # system ``'Symbols Nerd Font'`` fallback that won't exist on
    # every viewer's machine.
    config = _svalboard_config(num_layers=4)
    style = config.output.style.model_copy(update={"use_system_fonts": False})
    config = config.model_copy(
        update={"output": config.output.model_copy(update={"style": style})}
    )
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    # Real hold-tap labels: modifier glyph on hold, key name on tap.
    # The box-drawing pipe (│) is the SEPARATOR_CHAR the hold-symbol
    # logic splits on. Modifier glyphs are Nerd Font tokens
    # (``%%nf-md-apple_keyboard_*;``) so the labels stay visually
    # consistent with the macros / tap-dance / symbols snippets that
    # use the same glyph set.
    blank = SvalboardTargetKey(label="")
    cluster_data = ThumbClusterData(
        down_key=SvalboardTargetKey(label="%%nf-md-keyboard_space;"),
        pad_key=SvalboardTargetKey(
            label="%%nf-md-apple_keyboard_command;│%%nf-md-keyboard_tab;"
        ),
        up_key=SvalboardTargetKey(
            label="%%nf-md-apple_keyboard_control;│%%nf-md-keyboard_esc;"
        ),
        nail_key=SvalboardTargetKey(
            label="%%nf-md-apple_keyboard_option;│%%nf-md-keyboard_return;"
        ),
        knuckle_key=SvalboardTargetKey(
            label="%%nf-md-apple_keyboard_shift;│%%nf-md-backspace_reverse;"
        ),
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
                use_layer_colors_on_keys=True,
                show_layer_indicators=False,
                hold_symbol_position=pos,
            )
            panels.append((cluster, caption))
        d = _build_side_by_side(panels=panels)
        _embed_used_fonts(d)
        return d


def _build_layer_indicator_show_mock() -> draw.Drawing:
    """Finger cluster with a layer-switching north key, rendered with
    and without the layer-indicator badge.

    Uses the curated Svalboard palette so layer 2's purple gives the
    indicator badge clear contrast against the cluster's neutral keys.
    """
    config = _svalboard_config(num_layers=4)
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

    Uses the curated Svalboard palette so layer 2's purple comes
    through vividly on the ``true`` panel.
    """
    config = _svalboard_config(num_layers=4)
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


def _build_symbols_flow_mock() -> draw.Drawing:
    """Two SymbolSection layouts side by side, one column-major and
    one row-major, fed the same six entries. The column-major panel
    fills top-to-bottom before starting the next column; the
    row-major panel fills left-to-right before dropping to the next
    row. Demonstrates the difference at a glance.
    """
    from skim.application.render.section_data import SymbolLegendEntry
    from skim.application.render.symbols import SymbolSection

    # Six entries split across two categories so the two flow modes
    # produce clearly different orderings.
    entries = [
        SymbolLegendEntry(
            display_label="%%nf-md-apple_keyboard_command;",
            description="Command",
            sort_key="MOD_LCMD",
            category="Modifiers",
        ),
        SymbolLegendEntry(
            display_label="%%nf-md-apple_keyboard_control;",
            description="Control",
            sort_key="MOD_LCTL",
            category="Modifiers",
        ),
        SymbolLegendEntry(
            display_label="%%nf-md-apple_keyboard_option;",
            description="Option",
            sort_key="MOD_LOPT",
            category="Modifiers",
        ),
        SymbolLegendEntry(
            display_label="0",
            description="Base layer",
            sort_key="0",
            category="Layers",
        ),
        SymbolLegendEntry(
            display_label="1",
            description="Numbers / Symbols",
            sort_key="1",
            category="Layers",
        ),
        SymbolLegendEntry(
            display_label="2",
            description="Function / Navigation",
            sort_key="2",
            category="Layers",
        ),
    ]

    # ``use_system_fonts=False`` so painted Nerd-Font glyphs use the
    # bundled ``Key-Symbols`` family that :func:`_embed_used_fonts`
    # writes into the SVG. ``Spacing.table_col_spacing=24`` (absolute
    # SVG units) bumps the inter-column gap past the in-cell
    # glyph→description gap (default 12 px), so the two columns read
    # as distinct rather than blending into one another — same
    # treatment the ``symbol-descriptions`` mock uses.
    config = _svalboard_config(num_layers=4)
    style = config.output.style.model_copy(update={"use_system_fonts": False})
    layout = config.output.layout.model_copy(
        update={"spacing": Spacing(table_col_spacing=24.0)}
    )
    output = config.output.model_copy(update={"style": style, "layout": layout})
    config = config.model_copy(update={"output": output})
    keymap = _empty_keymap()
    ctx = RenderContext.build(config=config, keymap=keymap)

    section_width = 360.0

    with using_render_context(ctx):
        panels: list[tuple[Component, str]] = []
        for flow, caption in (("column", '"column"'), ("row", '"row"')):
            section = SymbolSection(
                entries=entries,
                max_width=section_width,
                # ``wrap_content=True`` so the section snugs to the
                # natural entry width and the title-strip rule lines
                # up with the table's right edge instead of stopping
                # short at ``max_width`` when the entries overflow.
                wrap_content=True,
                column_count=2,
                flow=flow,
                scale=1.5,
            )
            panels.append((section, caption))
        # Per-panel gap wider than ``table_col_spacing`` so the two
        # comparison panels read as separate units instead of looking
        # like a four-column extension of either legend.
        d = _build_side_by_side(panels=panels, panel_gap=72.0)
        _embed_used_fonts(d)
        return d


def _build_layer_connector_show_mock() -> draw.Drawing:
    """Two miniature overviews side by side, one with the dotted
    connector lines drawn (``show: true``) and one without
    (``show: false``).

    A 2-layer keymap with both thumb-cluster pad keys (left + right)
    bound to ``LT(1)`` so the ``true`` panel paints two connectors
    fanning into layer 1's badge — same data on both panels means
    the only visible difference is the lines themselves. The
    ``layer_connector.width`` and ``dot_spacing`` are bumped well
    past their defaults so the connectors read as the dominant
    feature of the figure (the docs use this image to explain what
    the connectors *are*; legibility wins over realistic styling).
    """
    from skim.data.keyboard import SplitSide

    blank = SvalboardTargetKey(label="")
    pad_to_layer1 = SvalboardTargetKey(
        label="%%nf-md-layers_outline; 1", layer_switch=1
    )

    def _empty_finger() -> FingerClusterData[SvalboardTargetKey]:
        return FingerClusterData(blank)

    def _layer0_thumb() -> ThumbClusterData[SvalboardTargetKey]:
        return ThumbClusterData(
            down_key=blank,
            pad_key=pad_to_layer1,
            up_key=blank,
            nail_key=blank,
            knuckle_key=blank,
            double_down_key=blank,
        )

    def _empty_thumb() -> ThumbClusterData[SvalboardTargetKey]:
        return ThumbClusterData(
            down_key=blank,
            pad_key=blank,
            up_key=blank,
            nail_key=blank,
            knuckle_key=blank,
            double_down_key=blank,
        )

    # Layer 0 places ``LT(1)`` on both pad keys (one per thumb
    # cluster). Both connectors run to layer 1's row in the badge
    # column — two paths fanning into the same destination.
    layer0_left = SplitSide(
        index=_empty_finger(),
        middle=_empty_finger(),
        ring=_empty_finger(),
        pinky=_empty_finger(),
        thumb=_layer0_thumb(),
    )
    layer0_right = SplitSide(
        index=_empty_finger(),
        middle=_empty_finger(),
        ring=_empty_finger(),
        pinky=_empty_finger(),
        thumb=_layer0_thumb(),
    )

    # Layer 1 is blank — the connectors only need source keys on
    # the destination's neighbouring layers, not destinations.
    def _blank_side() -> SplitSide[SvalboardTargetKey]:
        return SplitSide(
            index=_empty_finger(),
            middle=_empty_finger(),
            ring=_empty_finger(),
            pinky=_empty_finger(),
            thumb=_empty_thumb(),
        )

    keymap = SvalboardKeymap(
        layers={
            0: SvalboardLayout(left=layer0_left, right=layer0_right),
            1: SvalboardLayout(left=_blank_side(), right=_blank_side()),
        }
    )

    # Use a smaller doc width so the overview fits side-by-side on
    # the page; the Svalboard palette so badges and indicators read
    # cleanly. ``num_layers=2`` matches the keymap above.
    # ``use_system_fonts=False`` so painted text references the
    # bundled font families that :func:`_embed_used_fonts` writes
    # into the SVG (otherwise the layer-trigger key's
    # ``%%nf-md-layers_outline;`` glyph renders as a tofu box).
    base = _svalboard_config(num_layers=2)
    style = base.output.style.model_copy(update={"use_system_fonts": False})
    layout = base.output.layout.model_copy(update={"width": 800.0})
    output = base.output.model_copy(update={"layout": layout, "style": style})
    base_with_smaller_width = base.model_copy(update={"output": output})

    from skim.application.render.keymap_overview import KeymapOverview

    # Bump connector ``width`` and ``dot_spacing`` to absolute values
    # (≥ 1.0 = SVG units, not a doc-width proportion) above the
    # natural defaults so the dotted path reads as the figure's main
    # subject. Default at doc_width=800 is roughly width=2.2 / dot
    # spacing=6.1. The visible dot diameter equals ``width`` (the
    # path uses ``stroke-linecap="round"`` so each painted segment
    # caps as a circle of that diameter); ``dot_spacing`` controls
    # the gap between consecutive dots.
    chunky_width = 7.5
    chunky_dot_spacing = 18.0

    # Shared font-usage collector — each panel's
    # ``using_render_context`` block writes its painted-glyph chars
    # into this same collector instead of a fresh per-block one,
    # so :func:`_embed_used_fonts` (called after the loop) sees the
    # union of every character the panels actually paint.
    shared_collector = FontUsageCollector()

    panels: list[tuple[Component, str]] = []
    last_ctx: RenderContext | None = None
    for show, caption in ((True, "show: true"), (False, "show: false")):
        style = base_with_smaller_width.output.style.model_copy(
            update={
                "layer_connector": base_with_smaller_width.output.style.layer_connector.model_copy(
                    update={
                        "show": show,
                        "width": chunky_width,
                        "dot_spacing": chunky_dot_spacing,
                    }
                )
            }
        )
        config_for_panel = base_with_smaller_width.model_copy(
            update={
                "output": base_with_smaller_width.output.model_copy(update={"style": style})
            }
        )
        ctx = RenderContext.build(config=config_for_panel, keymap=keymap)
        last_ctx = ctx
        with using_render_context(ctx, font_usage_collector=shared_collector):
            overview = KeymapOverview(keymap=keymap)
            panels.append((overview, caption))

    # Each panel was built under its own render context. Stack them
    # vertically — overview images are very wide, so a vertical stack
    # keeps the figure narrow enough to read on the doc page.
    label_font_size = 12.0
    label_gap = 8.0
    label_height = label_font_size + label_gap
    panel_gap = 36.0
    outer_padding = 16.0

    extents = [_panel_extents(c) for c, _ in panels]
    panel_width = max(size.width for size, _ in extents)
    panel_heights = [size.height for size, _ in extents]
    canvas_w = panel_width + 2 * outer_padding
    canvas_h = (
        sum(panel_heights)
        + label_height * len(panels)
        + panel_gap * (len(panels) - 1)
        + 2 * outer_padding
    )

    d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")
    cursor_y = outer_padding
    for (component, caption), (overflow_size, overflow_offset) in zip(panels, extents, strict=True):
        # Centre each panel horizontally inside the canvas; offset the
        # keys-only origin by ``-overflow_offset`` so any chrome above
        # / left of the keys-only bbox lands on canvas.
        panel_x = outer_padding + (panel_width - overflow_size.width) / 2
        keys_origin = Point(
            panel_x - overflow_offset.x,
            cursor_y - overflow_offset.y,
        )
        component.draw_at(d, keys_origin)
        cursor_y += overflow_size.height
        d.append(
            draw.Text(
                caption,
                x=panel_x + overflow_size.width / 2,
                y=cursor_y + label_gap,
                font_size=label_font_size,
                text_anchor="middle",
                dominant_baseline="text-before-edge",
                font_family="Roboto, sans-serif",
                fill=_GREY_TEXT,
            )
        )
        cursor_y += label_height + panel_gap

    # Activate one of the panel ctxes so the shared collector becomes
    # the active one for ``_embed_used_fonts``, then write the
    # subsetted @font-face rules into the SVG.
    assert last_ctx is not None
    with using_render_context(last_ctx, font_usage_collector=shared_collector):
        _embed_used_fonts(d)

    return d


def _build_show_transparent_fallthrough_mock() -> draw.Drawing:
    """Two single layer-tinted keys side-by-side, illustrating what
    a transparent key on a non-base layer renders as under each
    setting:

    * ``true`` (default) — the key carries a ghost version of the
      layer-0 label it falls through to.
    * ``false`` — :func:`KeymapTargetAdapter` stamps the Vial-style
      ⛛ glyph on the transparent position so it stays visible
      instead of rendering as a blank key.

    The key fill mirrors what a transparent key on a layer above 0
    actually renders as in production — the activating layer's
    colour. Both labels paint in a lightness-shifted variant of
    that colour, matching the legacy ghost contrast.
    """
    panel_w = 120.0
    panel_h = 120.0
    key_w = 96.0
    key_h = 96.0
    radius = 6.0
    ghost_label_text = "K"
    transparent_glyph = "⛛"  # ⛛ — same glyph the adapter stamps
    label_font = 32.0
    # Colour mirrors a typical layer accent (a dusty blue from the
    # default skim palette). Both labels paint as a
    # lightness-shifted version of that colour — the legacy
    # production behaviour.
    key_fill = "#3F7BB6"
    ghost_fill = "#9CBEDD"  # = key_fill with HSL lightness +0.18

    def _key_panel(*, label: str | None) -> Component:
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
                    fill=key_fill,
                )
            )
            if label is not None:
                d.append(
                    draw.Text(
                        label,
                        x=kx + key_w / 2,
                        y=ky + key_h / 2,
                        font_size=label_font,
                        font_family="'DejaVu Sans Condensed', 'DejaVu Sans', 'Apple Symbols', sans-serif",
                        text_anchor="middle",
                        dominant_baseline="central",
                        fill=ghost_fill,
                    )
                )

        return BaseComponent(size=size, draw_fn=draw_at)

    return _build_side_by_side(
        panels=[
            (_key_panel(label=ghost_label_text), "true (ghost label)"),
            (_key_panel(label=transparent_glyph), "false (⛛ glyph)"),
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
    "layer-connector-show": _build_layer_connector_show_mock,
    "use-layer-colors-on-keys": _build_use_layer_colors_on_keys_mock,
    "show-transparent-fallthrough": _build_show_transparent_fallthrough_mock,
    "symbols-flow": _build_symbols_flow_mock,
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
