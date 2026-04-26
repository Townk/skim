# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Overview image rendering for multi-layer keymap visualization.

Generates a table-like overview SVG showing all keymap layers:
- Header row: Svalboard logo (col 1) + layout title (col 2)
- Layer rows: colored badge with "N NAME" (col 1) + 8 finger clusters (col 2)
- Thumb row: THUMBS badge (col 1) + thumb clusters for layer 0 (col 2)
- Dotted connector lines from layer indicator circles to target layer rows
"""

import drawsvg as draw

from skim.assets import ASSETS
from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import KeyboardSide, SvalboardTargetKey

from .components import FingerClusterComponent, ThumbClusterComponent
from .connectors import ConnectorRouting, route_thumb_connectors
from .context import RenderContext
from .geometry import AspectRatio
from .indicators import (
    _THUMB_KEY_HEIGHT_RATIOS,
    _THUMB_KEY_NAMES,
    LayerIndicator,
    _thumb_cluster_offset,
)
from .layout import Boundary, KeymapLayoutMetrics
from .overview_layout import (
    _BADGE_PADDING_LEFT,
    _BADGE_PADDING_RIGHT,
    BadgeDimensions,
    OverviewLayout,
)
from .text import Font

_LOGO_ASPECT_RATIO = AspectRatio.from_dimensions(width=2333.333, height=458.333, precision=2)
_FINGER_CLUSTERS_PER_SIDE = 4

# Finger cluster key proportions (same as FingerClusterComponent)
_OUTER_KEY_WIDTH_PROPORTION = 0.328

# Badge font size as a ratio of badge height
_BADGE_FONT_SIZE_RATIO = 0.45


def _compute_badge_dims(
    config: SkimConfig,
    render_layers: list[tuple[int, int]],
    finger_cluster_width: float,
) -> BadgeDimensions:
    """Compute uniform badge dimensions.

    Height matches the E/W key size in the overview finger cluster.
    Width = 15px padding + widest badge text + 30px padding.
    """
    # Badge height = E/W key height = outer_key proportion * cluster_width
    badge_height = finger_cluster_width * _OUTER_KEY_WIDTH_PROPORTION

    # Build all badge texts to find the widest
    badge_texts: list[str] = []
    for pos, qmk_idx in render_layers:
        name = config.keyboard.layers[pos].name.upper()
        badge_texts.append(f"{qmk_idx} {name}")
    badge_texts.append("THUMBS")

    # Measure text width using PIL font for accuracy.
    # PIL font sizes map to SVG units approximately 1:1 when the SVG uses
    # the same coordinate scale, but we need to measure at the actual size
    # that will be used in the SVG. Use a high-res measurement then scale.
    badge_font_size = badge_height * _BADGE_FONT_SIZE_RATIO
    try:
        from .text import Font as SkimFont

        # Measure at a large reference size then scale proportionally
        ref_size = 100
        pil_font = SkimFont.FINGER_KEY.load(ref_size)
        max_text_width_at_ref = (
            max(pil_font.getlength(t) for t in badge_texts) if badge_texts else 50
        )
        max_text_width = max_text_width_at_ref * (badge_font_size / ref_size)
    except Exception:
        char_width = badge_font_size * 0.65
        max_text_width = max(len(t) * char_width for t in badge_texts) if badge_texts else 50

    badge_width = _BADGE_PADDING_LEFT + max_text_width + _BADGE_PADDING_RIGHT
    border_radius = badge_height * 0.2

    return BadgeDimensions(
        width=badge_width,
        height=badge_height,
        border_radius=border_radius,
    )


_IndicatorInfo = tuple[float, float, float, int, str, KeyboardSide]
"""(abs_cx, abs_cy, circle_radius, target_layer_idx, key_name, side)"""


def _collect_finger_indicators(
    clusters: list[list[FingerClusterComponent]],
    keymap: SvalboardKeymap[SvalboardTargetKey],
    row_to_layer: list[tuple[int, int]],
) -> list[_IndicatorInfo]:
    """Collect indicator circle positions from finger clusters.

    Currently returns an empty list — finger cluster connector routing
    is not yet implemented (exception case requiring special handling).
    """
    return []


def _compute_thumb_indicator_rects(
    left_thumb: ThumbClusterComponent,
    right_thumb: ThumbClusterComponent,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    config: SkimConfig,
) -> dict[SvalboardTargetKey, tuple[float, float, float, float]]:
    """Return ``{triggering_key: (rect_x, rect_y, rect_w, rect_h)}`` for thumb indicators.

    Each rect is the bounding box of the indicator circle:
    ``(cx - r, cy - r, 2r, 2r)`` in absolute SVG coordinates.
    """
    results: dict[SvalboardTargetKey, tuple[float, float, float, float]] = {}
    first_qmk_idx = config.keyboard.layers[0].index if config.keyboard.layers else 0
    if first_qmk_idx not in keymap.layers:
        return results
    layer0 = keymap.layers[first_qmk_idx]

    for thumb_comp, thumb_data, side in [
        (left_thumb, layer0.left.thumb, KeyboardSide.LEFT),
        (right_thumb, layer0.right.thumb, KeyboardSide.RIGHT),
    ]:
        metrics = thumb_comp._layout.metrics
        palette = thumb_comp._render_context.palette
        down_metrics = metrics.down_key
        circle_diameter = down_metrics.width * 0.4
        gap = down_metrics.width * 0.18

        for key_name in _THUMB_KEY_NAMES:
            key: SvalboardTargetKey = getattr(thumb_data, key_name)
            if key.layer_switch is None:
                continue

            layout_b = getattr(metrics, key_name)
            offset_dir, conn_type = _thumb_cluster_offset(key_name, side)

            if key_name == "double_down_key":
                ref_y = down_metrics.pos.y
                ref_height = layout_b.width * _THUMB_KEY_HEIGHT_RATIOS.get("down_key", 1.0)
                connector_target_y = layout_b.pos.y
            elif key_name == "down_key":
                # Same fix as in indicators.py: position circle at
                # up_cy + (up_cy - pad_cy) instead of key center
                up_layout = metrics.up_key
                up_h = up_layout.width * _THUMB_KEY_HEIGHT_RATIOS["up_key"]
                up_cy = up_layout.pos.y + up_h / 2.0
                pad_layout = metrics.pad_key
                pad_h = pad_layout.width * _THUMB_KEY_HEIGHT_RATIOS["pad_key"]
                pad_cy = pad_layout.pos.y + pad_h / 2.0
                down_target_cy = up_cy + (up_cy - pad_cy)
                ref_height = layout_b.width * _THUMB_KEY_HEIGHT_RATIOS["down_key"]
                ref_y = down_target_cy - ref_height / 2.0
                connector_target_y = None
            else:
                ref_y = layout_b.pos.y
                ref_height = layout_b.width * _THUMB_KEY_HEIGHT_RATIOS.get(key_name, 1.0)
                connector_target_y = None

            indicator = LayerIndicator(
                key_x=layout_b.pos.x,
                key_y=ref_y,
                key_width=layout_b.width,
                key_height=ref_height,
                target_layer=key.layer_switch,
                palette=palette,
                circle_diameter=circle_diameter,
                gap=gap,
                offset_direction=offset_dir,
                connector_type=conn_type,
                connector_target_y=connector_target_y,
            )

            radius = circle_diameter / 2.0
            abs_cx = thumb_comp.x + indicator.circle_center_x
            abs_cy = thumb_comp.y + indicator.circle_center_y
            results[key] = (
                abs_cx - radius,
                abs_cy - radius,
                circle_diameter,
                circle_diameter,
            )

    return results


class _RoutingLayoutAdapter:
    """Adapter that exposes ``OverviewLayout`` to the connector router by QMK index.

    ``route_thumb_connectors`` calls ``layer_row_bounding_box(target_layer)``
    where ``target_layer`` is a key's QMK ``layer_switch`` value. The overview
    renders rows in reverse order (top row = highest QMK index) and may use
    non-sequential QMK indices (e.g. 0, 1, 3, 4, 8, ...), so a QMK index does
    not equal a row index. This adapter translates QMK indices to row indices
    using the caller's ``layer_to_row`` map and presents a ``layer_row_y_positions``
    long enough that the router's bounds check accepts every mapped QMK index.
    """

    def __init__(self, layout: OverviewLayout, layer_to_row: dict[int, int]) -> None:
        self._layout = layout
        self._layer_to_row = layer_to_row
        # Build a virtual y-positions list indexed by QMK layer index, padded
        # to ``max(qmk_idx) + 1`` so the router's
        # ``target_layer < len(layer_row_y_positions)`` bounds check passes for
        # every valid QMK index. Slots without a layer get 0.0 — they are never
        # looked up because ``layer_row_bounding_box`` is the only consumer of
        # the actual values, and it goes through ``_layer_to_row.get``.
        size = max(layer_to_row.keys()) + 1 if layer_to_row else 0
        positions = [0.0] * size
        real = layout.layer_row_y_positions
        for qmk_idx, row_idx in layer_to_row.items():
            if 0 <= row_idx < len(real):
                positions[qmk_idx] = real[row_idx]
        self._y_positions = positions

    @property
    def layer_row_y_positions(self) -> list[float]:
        return self._y_positions

    def layer_row_bounding_box(self, target_layer: int) -> tuple[float, float, float, float]:
        row_idx = self._layer_to_row.get(target_layer)
        if row_idx is None:
            # Fallback: caller passed an unmapped index. ``target_point_for``
            # already guards via the y_positions length check, so this is
            # purely defensive.
            row_idx = target_layer
        return self._layout.layer_row_bounding_box(row_idx)

    def thumb_cluster_y_bounds(self) -> tuple[float, float]:
        return self._layout.thumb_cluster_y_bounds()


def _build_thumb_clusters(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    layout: OverviewLayout,
    use_system_fonts: bool,
) -> tuple[ThumbClusterComponent | None, ThumbClusterComponent | None]:
    """Build thumb cluster components at the layout's current thumb position."""
    if not keymap.layers:
        return None, None
    first_qmk_idx = config.keyboard.layers[0].index if config.keyboard.layers else 0
    if first_qmk_idx not in keymap.layers:
        return None, None
    layer0 = keymap.layers[first_qmk_idx]
    palette = config.output.style.palette
    thumb_ctx = RenderContext(
        palette=palette,
        layer_index=0,
        has_double_south=config.keyboard.features.double_south,
        use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
        hold_symbol_position=config.output.style.hold_symbol_position,
        use_system_fonts=use_system_fonts,
        show_layer_indicators=config.output.style.show_layer_indicators,
        qmk_index_to_position=config.keyboard.qmk_index_to_position,
    )
    thumb_w = layout.thumb_cluster_width
    left_pos, right_pos = layout.thumb_cluster_positions()
    left_thumb = ThumbClusterComponent(
        keymap_cluster=layer0.left.thumb,
        side=KeyboardSide.LEFT,
        layout=Boundary(width=thumb_w, pos=left_pos),
        render_context=thumb_ctx,
    )
    right_thumb = ThumbClusterComponent(
        keymap_cluster=layer0.right.thumb,
        side=KeyboardSide.RIGHT,
        layout=Boundary(width=thumb_w, pos=right_pos),
        render_context=thumb_ctx,
    )
    return left_thumb, right_thumb


def draw_overview(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Generate the full overview SVG image for a multi-layer keymap."""
    num_layers = len(config.keyboard.layers)
    render_layers: list[tuple[int, int]] = []  # (config_position, qmk_index)
    for pos, layer_cfg in enumerate(config.keyboard.layers):
        if layer_cfg.index in keymap.layers:
            render_layers.append((pos, layer_cfg.index))

    use_system_fonts = config.output.style.use_system_fonts
    palette = config.output.style.palette
    base_metrics = KeymapLayoutMetrics.from_config(config)

    # --- Phase 1: Compute layout dimensions ---
    prelim_badge = BadgeDimensions(width=200, height=40, border_radius=8)
    prelim_layout = OverviewLayout(config, prelim_badge)
    badge_dims = _compute_badge_dims(config, render_layers, prelim_layout.finger_cluster_width)
    # Routing area width is allocated by route_thumb_connectors via extra_right_padding;
    # pass 0 so the constructor doesn't pre-reserve duplicate space.
    layout = OverviewLayout(config, badge_dims, routing_column_count=0)

    nk = layout.finger_cluster_width * _OUTER_KEY_WIDTH_PROPORTION
    ew_offset = layout.ew_key_y_offset
    row_to_layer = list(reversed(render_layers))  # list of (pos, qmk_idx) tuples
    layer_to_row = {qmk_idx: ri for ri, (_pos, qmk_idx) in enumerate(row_to_layer)}

    # --- Phase 2: Route thumb-cluster connectors via the new algorithm ---
    routing: ConnectorRouting | None = None
    if config.output.style.show_layer_indicators and keymap.layers:
        first_qmk_idx = config.keyboard.layers[0].index if config.keyboard.layers else 0
        if config.output.style.show_layer_connectors and first_qmk_idx in keymap.layers:
            layer0 = keymap.layers[first_qmk_idx]
            # ``route_thumb_connectors`` indexes the layout via
            # ``layer_row_bounding_box(target_layer)`` / ``layer_row_y_positions``.
            # In the overview, rows are reversed (top = highest QMK index) and
            # ``target_layer`` is a QMK layer index (``key.layer_switch``). Wrap
            # the layout so QMK indices resolve to the correct row.
            routing_layout = _RoutingLayoutAdapter(layout, layer_to_row)

            # Pass 1: discover ``extra_top_padding`` so we know how far to shift
            # the thumb cluster before the final routing pass.
            prelim_left, prelim_right = _build_thumb_clusters(
                config, keymap, layout, use_system_fonts
            )
            if prelim_left and prelim_right:
                prelim_rects = _compute_thumb_indicator_rects(
                    prelim_left, prelim_right, keymap, config
                )
                prelim_routing = route_thumb_connectors(
                    left=layer0.left.thumb,
                    right=layer0.right.thumb,
                    layout=routing_layout,
                    source_layer=first_qmk_idx,
                    keymap_spacing=nk,
                    indicator_rects=prelim_rects,
                )
                if prelim_routing.extra_top_padding > 0:
                    layout.shift_thumb_down(prelim_routing.extra_top_padding)

                # Pass 2: re-run routing against the shifted layout so the path
                # coordinates align with where the thumb indicators will actually
                # render.
                final_left, final_right = _build_thumb_clusters(
                    config, keymap, layout, use_system_fonts
                )
                if final_left and final_right:
                    final_rects = _compute_thumb_indicator_rects(
                        final_left, final_right, keymap, config
                    )
                    routing = route_thumb_connectors(
                        left=layer0.left.thumb,
                        right=layer0.right.thumb,
                        layout=routing_layout,
                        source_layer=first_qmk_idx,
                        keymap_spacing=nk,
                        indicator_rects=final_rects,
                    )
                    if routing.extra_right_padding > 0:
                        layout.adjust_canvas_width(
                            layout.canvas_width + routing.extra_right_padding
                        )

    # --- Phase 3: Render everything at final positions ---
    # Extend canvas to fit copyright text below all content
    copyright_extra = 0.0
    if config.output.copyright:
        # Reserve space: gap + text line + padding
        prelim_badge_font_size = badge_dims.height * _BADGE_FONT_SIZE_RATIO
        copyright_extra = prelim_badge_font_size + layout.padding

    canvas_w = layout.canvas_width
    canvas_h = layout.canvas_height + copyright_extra
    if routing is not None:
        canvas_h += routing.extra_bottom_padding
    padding = layout.padding
    margin = base_metrics.margin

    d = draw.Drawing(canvas_w, canvas_h)

    if not use_system_fonts:
        for font in Font:
            d.append_css(font.css_style)

    border = config.output.style.border
    d.append(
        draw.Rectangle(
            x=margin,
            y=margin,
            width=canvas_w - margin * 2.0,
            height=canvas_h - margin * 2.0,
            rx=border.radius if border else None,
            ry=border.radius if border else None,
            fill=palette.background_color,
            stroke=palette.border_color if border else None,
            stroke_width=border.width if border else None,
        )
    )

    label_font = (
        Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value
    )
    title_font = Font.TITLE.get_system_font_family() if use_system_fonts else Font.TITLE.value

    # Use the FINAL layout's outer_key_size for badge height so the badge top
    # and bottom line up exactly with the E/W key edges. badge_dims.height was
    # computed from the preliminary cluster_width and is stale.
    badge_w = badge_dims.width
    badge_h = layout.outer_key_size
    badge_r = badge_h * 0.2
    badge_font_size = badge_h * _BADGE_FONT_SIZE_RATIO
    badge_x = padding

    # Header: logo + title
    logo_width = badge_w * 1.06
    logo_height = _LOGO_ASPECT_RATIO.height_from_width(logo_width)
    d.append(
        draw.Image(
            x=padding,
            y=padding,
            width=logo_width,
            height=logo_height,
            path=ASSETS.logo_svalboard,
            embed=True,
        )
    )

    if config.output.keymap_title:
        title_text = config.output.keymap_title
    elif num_layers > 0:
        first_layer = config.keyboard.layers[0]
        title_text = f"{(first_layer.variant or first_layer.name)} Layers Layout"
    else:
        title_text = "Keymap Layout"
    d.append(
        draw.Text(
            title_text,
            font_size=badge_font_size * 1.8,
            x=layout.right_column_x,
            y=padding + logo_height / 2.0,
            text_anchor="start",
            dominant_baseline="central",
            font_family=title_font,
            fill=palette.text_color,
        )
    )

    # LAYERS heading
    if row_to_layer:
        first_badge_y = layout.layer_row_y_positions[0] + ew_offset
        d.append(
            draw.Text(
                "LAYERS",
                font_size=badge_font_size,
                x=badge_x + _BADGE_PADDING_LEFT,
                y=first_badge_y - badge_font_size * 0.2,
                text_anchor="start",
                dominant_baseline="text-after-edge",
                font_family=label_font,
                fill=palette.neutral_color,
            )
        )

    # Layer badges
    for row_idx, (pos, qmk_idx) in enumerate(row_to_layer):
        row_y = layout.layer_row_y_positions[row_idx]
        layer_cfg = config.keyboard.layers[pos]
        layer_color = (
            palette.layers[pos].base_color if pos < len(palette.layers) else palette.neutral_color
        )
        badge_y = row_y + ew_offset
        d.append(
            draw.Rectangle(
                x=badge_x,
                y=badge_y,
                width=badge_w,
                height=badge_h,
                rx=badge_r,
                ry=badge_r,
                fill=layer_color,
            )
        )
        d.append(
            draw.Text(
                f"{qmk_idx} {layer_cfg.name.upper()}",
                font_size=badge_font_size,
                x=badge_x + _BADGE_PADDING_LEFT,
                y=badge_y + badge_h / 2.0,
                text_anchor="start",
                dominant_baseline="central",
                font_family=label_font,
                fill="white",
            )
        )
        if layer_cfg.variant:
            d.append(
                draw.Text(
                    layer_cfg.variant,
                    font_size=badge_font_size,
                    x=badge_x + _BADGE_PADDING_LEFT,
                    y=badge_y + badge_h + badge_font_size * 0.2,
                    text_anchor="start",
                    dominant_baseline="text-before-edge",
                    font_family=label_font,
                    fill=layer_color,
                )
            )

    # THUMBS badge — align with the pad key TOP, which sits one thumb-cluster
    # inset below the down key (cluster top).
    thumbs_badge_y = layout.thumb_row_y + layout.thumb_pad_key_y_offset
    d.append(
        draw.Rectangle(
            x=badge_x,
            y=thumbs_badge_y,
            width=badge_w,
            height=badge_h,
            rx=badge_r,
            ry=badge_r,
            fill=palette.text_color,
        )
    )
    d.append(
        draw.Text(
            "THUMBS",
            font_size=badge_font_size,
            x=badge_x + _BADGE_PADDING_LEFT,
            y=thumbs_badge_y + badge_h / 2.0,
            text_anchor="start",
            dominant_baseline="central",
            font_family=label_font,
            fill="white",
        )
    )

    # Finger clusters
    cluster_width = layout.finger_cluster_width
    for row_idx, (pos, qmk_idx) in enumerate(row_to_layer):
        layer_data = keymap.layers[qmk_idx]
        ctx = RenderContext(
            palette=palette,
            layer_index=pos,
            has_double_south=config.keyboard.features.double_south,
            use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
            hold_symbol_position=config.output.style.hold_symbol_position,
            use_system_fonts=use_system_fonts,
            show_layer_indicators=config.output.style.show_layer_indicators,
            qmk_index_to_position=config.keyboard.qmk_index_to_position,
        )
        positions = layout.finger_cluster_positions(row_idx)
        for i in range(_FINGER_CLUSTERS_PER_SIDE):
            c = FingerClusterComponent(
                keymap_cluster=layer_data.left.fingers[i],
                side=KeyboardSide.LEFT,
                layout=Boundary(width=cluster_width, pos=positions[i]),
                render_context=ctx,
            )
            d.append(c.build())
        for i in range(_FINGER_CLUSTERS_PER_SIDE):
            c = FingerClusterComponent(
                keymap_cluster=layer_data.right.fingers[i],
                side=KeyboardSide.RIGHT,
                layout=Boundary(width=cluster_width, pos=positions[_FINGER_CLUSTERS_PER_SIDE + i]),
                render_context=ctx,
            )
            d.append(c.build())

    # Thumb clusters at final position
    left_thumb, right_thumb = _build_thumb_clusters(config, keymap, layout, use_system_fonts)
    if left_thumb:
        d.append(left_thumb.build())
    if right_thumb:
        d.append(right_thumb.build())

    # Connector lines
    if routing is not None:
        for path, target_layer in routing.paths:
            pos = config.keyboard.qmk_index_to_position(target_layer)
            if pos is not None and 0 <= pos < len(palette.layers):
                stroke_color = palette.layers[pos][4]
            else:
                stroke_color = "#808080"
            path.args["stroke"] = stroke_color
            path.args["stroke-width"] = 2.5
            path.args["stroke-dasharray"] = "0.1 7"
            path.args["stroke-linecap"] = "round"
            path.args["opacity"] = 0.7
            d.append(path)

    # Copyright
    if config.output.copyright:
        d.append(
            draw.Text(
                config.output.copyright,
                font_size=badge_font_size,
                x=canvas_w - padding,
                y=canvas_h - padding,
                text_anchor="end",
                dominant_baseline="text-after-edge",
                font_family=label_font,
                fill=palette.text_color,
                opacity=0.6,
            )
        )

    return d
