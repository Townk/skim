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
from .context import RenderContext
from .geometry import AspectRatio
from .indicators import (
    LayerIndicator,
    _finger_cluster_offset,
    _FINGER_KEY_NAMES,
    _thumb_cluster_offset,
    _THUMB_KEY_NAMES,
    _THUMB_KEY_HEIGHT_RATIOS,
)
from .layout import Boundary, KeymapLayoutMetrics
from .overview_layout import BadgeDimensions, OverviewLayout
from .text import Font

_LOGO_ASPECT_RATIO = AspectRatio.from_dimensions(width=2333.333, height=458.333, precision=2)
_FINGER_CLUSTERS_PER_SIDE = 4
_CONNECTOR_ROUTING_MARGIN = 12.0

# Finger cluster key proportions (same as FingerClusterComponent)
_OUTER_KEY_WIDTH_PROPORTION = 0.328


def _compute_badge_dims(
    config: SkimConfig,
    render_layer_count: int,
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
    for layer_idx in range(render_layer_count):
        if layer_idx < len(config.keyboard.layers):
            name = config.keyboard.layers[layer_idx].name.upper()
            badge_texts.append(f"{layer_idx} {name}")
    badge_texts.append("THUMBS")

    # Estimate text width: for bold Roboto at badge_font_size, ~0.62 * font_size per char
    badge_font_size = badge_height * 0.55
    char_width = badge_font_size * 0.62
    max_text_width = max(len(t) * char_width for t in badge_texts) if badge_texts else 50

    badge_width = 15.0 + max_text_width + 30.0
    border_radius = badge_height * 0.2

    return BadgeDimensions(
        width=badge_width,
        height=badge_height,
        border_radius=border_radius,
    )


def _collect_indicator_positions(
    clusters: list[list[FingerClusterComponent]],
    keymap: SvalboardKeymap[SvalboardTargetKey],
    row_to_layer: list[int],
) -> list[tuple[int, float, float, int]]:
    """Collect absolute positions of all layer indicator circles from finger clusters.

    Returns list of (row_idx, abs_cx, abs_cy, target_layer_idx).
    """
    results: list[tuple[int, float, float, int]] = []

    for row_idx, layer_clusters in enumerate(clusters):
        layer_idx = row_to_layer[row_idx]
        layer_data = keymap.layers[layer_idx]

        for cluster_idx, comp in enumerate(layer_clusters):
            is_right = cluster_idx >= _FINGER_CLUSTERS_PER_SIDE
            finger_idx = cluster_idx - _FINGER_CLUSTERS_PER_SIDE if is_right else cluster_idx
            side = KeyboardSide.RIGHT if is_right else KeyboardSide.LEFT

            finger_data = (
                layer_data.right.fingers[finger_idx] if is_right
                else layer_data.left.fingers[finger_idx]
            )

            metrics = comp._layout.metrics
            palette = comp._render_context.palette
            circle_diameter = metrics.north_key.width * 0.55
            gap = metrics.north_key.width * 0.18

            for key_name in _FINGER_KEY_NAMES:
                if key_name == "double_south_key" and not comp._render_context.has_double_south:
                    continue

                key: SvalboardTargetKey = getattr(finger_data, key_name)
                if key.layer_switch is None:
                    continue

                layout_b = getattr(metrics, key_name)
                offset_dir, conn_type = _finger_cluster_offset(key_name, side)
                key_gap = gap * 3 if key_name == "center_key" else gap

                indicator = LayerIndicator(
                    key_x=layout_b.pos.x, key_y=layout_b.pos.y,
                    key_width=layout_b.width, key_height=layout_b.width,
                    target_layer=key.layer_switch, palette=palette,
                    circle_diameter=circle_diameter, gap=key_gap,
                    offset_direction=offset_dir, connector_type=conn_type,
                )

                results.append((
                    row_idx,
                    comp.x + indicator.circle_center_x,
                    comp.y + indicator.circle_center_y,
                    key.layer_switch,
                ))

    return results


def _collect_thumb_indicator_positions(
    left_thumb: ThumbClusterComponent,
    right_thumb: ThumbClusterComponent,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> list[tuple[float, float, int]]:
    """Collect absolute positions of layer indicator circles from thumb clusters.

    Returns list of (abs_cx, abs_cy, target_layer_idx).
    """
    results: list[tuple[float, float, int]] = []
    layer0 = keymap.layers[0]

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
            else:
                ref_y = layout_b.pos.y
                ref_height = layout_b.width * _THUMB_KEY_HEIGHT_RATIOS.get(key_name, 1.0)
                connector_target_y = None

            indicator = LayerIndicator(
                key_x=layout_b.pos.x, key_y=ref_y,
                key_width=layout_b.width, key_height=ref_height,
                target_layer=key.layer_switch, palette=palette,
                circle_diameter=circle_diameter, gap=gap,
                offset_direction=offset_dir, connector_type=conn_type,
                connector_target_y=connector_target_y,
            )

            results.append((
                thumb_comp.x + indicator.circle_center_x,
                thumb_comp.y + indicator.circle_center_y,
                key.layer_switch,
            ))

    return results


def _draw_connector_lines(
    d: draw.Drawing,
    layout: OverviewLayout,
    finger_indicators: list[tuple[int, float, float, int]],
    thumb_indicators: list[tuple[float, float, int]],
    config: SkimConfig,
    all_row_bounds: list[tuple[float, float, float, float]],
    layer_to_row: dict[int, int],
) -> None:
    """Draw orthogonal dashed connector lines from indicators to target rows."""
    palette = config.output.style.palette
    right_edge = layout.canvas_width - layout.padding

    def _route_line(abs_cx: float, abs_cy: float, target_layer: int) -> None:
        if target_layer not in layer_to_row:
            return
        if 0 <= target_layer < len(palette.layers):
            stroke_color = palette.layers[target_layer][4]
        else:
            stroke_color = "#808080"

        target_row_idx = layer_to_row[target_layer]
        tgt_x, tgt_y, tgt_w, tgt_h = all_row_bounds[target_row_idx]
        target_mid_y = tgt_y + tgt_h / 2.0
        target_right_x = tgt_x + tgt_w

        routing_x = right_edge - _CONNECTOR_ROUTING_MARGIN

        path_d = (
            f"M {abs_cx:.2f} {abs_cy:.2f} "
            f"L {routing_x:.2f} {abs_cy:.2f} "
            f"L {routing_x:.2f} {target_mid_y:.2f} "
            f"L {target_right_x - _CONNECTOR_ROUTING_MARGIN:.2f} {target_mid_y:.2f}"
        )

        d.append(draw.Raw(
            f'<path d="{path_d}"'
            f' stroke="{stroke_color}"'
            f' stroke-width="1.5"'
            f' stroke-dasharray="6 4"'
            f' fill="none"'
            f' opacity="0.7"'
            f'/>'
        ))

    for _row, cx, cy, target in finger_indicators:
        _route_line(cx, cy, target)

    for cx, cy, target in thumb_indicators:
        _route_line(cx, cy, target)


def draw_overview(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Generate the full overview SVG image for a multi-layer keymap."""
    num_layers = len(config.keyboard.layers)
    render_layer_count = min(len(keymap.layers), num_layers)
    use_system_fonts = config.output.style.use_system_fonts
    palette = config.output.style.palette
    base_metrics = KeymapLayoutMetrics.from_config(config)

    # Pre-compute badge dimensions based on key sizes.
    # We need a preliminary cluster width to size the badge height.
    # Use a rough estimate: scale base cluster width to ~80% of total width.
    prelim_scale = 0.75
    prelim_cluster_w = base_metrics.finger_cluster_width * prelim_scale
    badge_dims = _compute_badge_dims(config, render_layer_count, prelim_cluster_w)

    layout = OverviewLayout(config, badge_dims)

    # Recompute badge dims with the actual cluster width from the layout
    badge_dims = _compute_badge_dims(config, render_layer_count, layout.finger_cluster_width)
    # Rebuild layout with correct badge dims (badge width may have changed)
    layout = OverviewLayout(config, badge_dims)

    canvas_w = layout.canvas_width
    canvas_h = layout.canvas_height
    padding = layout.padding
    margin = base_metrics.margin

    d = draw.Drawing(canvas_w, canvas_h)

    # Embed fonts
    if not use_system_fonts:
        for font in Font:
            d.append_css(font.css_style)

    # Background with rounded border
    border = config.output.style.border
    d.append(draw.Rectangle(
        x=margin, y=margin,
        width=canvas_w - margin * 2.0,
        height=canvas_h - margin * 2.0,
        rx=border.radius if border else None,
        ry=border.radius if border else None,
        fill=palette.background_color,
        stroke=palette.border_color if border else None,
        stroke_width=border.width if border else None,
    ))

    label_font = Font.THUMB_KEY.get_system_font_family() if use_system_fonts else Font.THUMB_KEY.value
    title_font = Font.TITLE.get_system_font_family() if use_system_fonts else Font.TITLE.value

    badge_w = badge_dims.width
    badge_h = badge_dims.height
    badge_r = badge_dims.border_radius
    badge_font_size = badge_h * 0.55
    badge_x = padding

    # ---------------------------------------------------------------
    # Header row: logo (col 1) + title (col 2)
    # ---------------------------------------------------------------
    logo_width = badge_w * 0.85
    logo_height = _LOGO_ASPECT_RATIO.height_from_width(logo_width)
    d.append(draw.Image(
        x=padding, y=padding,
        width=logo_width, height=logo_height,
        path=ASSETS.logo_svalboard, embed=True,
    ))

    # Title — left-aligned in col 2
    if num_layers > 0:
        first_layer = config.keyboard.layers[0]
        title_text = f"{(first_layer.subtitle or first_layer.name)} Layers Layout"
    else:
        title_text = "Keymap Layout"

    title_font_size = badge_font_size * 1.8
    d.append(draw.Text(
        title_text,
        font_size=title_font_size,
        x=layout.right_column_x,
        y=padding + logo_height / 2.0,
        text_anchor="start",
        dominant_baseline="central",
        font_family=title_font,
        fill=palette.text_color,
    ))

    # "LAYERS" heading below logo
    layers_heading_y = padding + logo_height + badge_h * 0.3
    d.append(draw.Text(
        "LAYERS",
        font_size=badge_font_size * 0.7,
        x=padding,
        y=layers_heading_y,
        text_anchor="start",
        dominant_baseline="text-before-edge",
        font_family=label_font,
        fill=palette.text_color,
        font_weight="bold",
    ))

    # ---------------------------------------------------------------
    # Layer rows: reversed order (highest layer at top)
    # ---------------------------------------------------------------
    row_to_layer = list(reversed(range(render_layer_count)))

    for row_idx, layer_idx in enumerate(row_to_layer):
        row_y = layout.layer_row_y_positions[row_idx]
        row_h = layout.layer_row_heights[row_idx]

        layer_cfg = config.keyboard.layers[layer_idx]
        layer_color = (
            palette.layers[layer_idx].base_color
            if layer_idx < len(palette.layers)
            else palette.neutral_color
        )

        # Badge centered vertically in the row
        badge_y = row_y + row_h / 2.0 - badge_h / 2.0
        badge_text = f"{layer_idx} {layer_cfg.name.upper()}"

        d.append(draw.Rectangle(
            x=badge_x, y=badge_y,
            width=badge_w, height=badge_h,
            rx=badge_r, ry=badge_r,
            fill=layer_color,
        ))
        d.append(draw.Text(
            badge_text,
            font_size=badge_font_size,
            x=badge_x + 15.0,
            y=badge_y + badge_h / 2.0,
            text_anchor="start",
            dominant_baseline="central",
            font_family=label_font,
            fill="white",
            font_weight="bold",
        ))

        # Optional subtitle below badge
        if layer_cfg.subtitle:
            subtitle_size = badge_font_size * 0.75
            d.append(draw.Text(
                layer_cfg.subtitle,
                font_size=subtitle_size,
                x=badge_x + 15.0,
                y=badge_y + badge_h + subtitle_size * 0.3,
                text_anchor="start",
                dominant_baseline="text-before-edge",
                font_family=label_font,
                fill=palette.text_color,
            ))

    # THUMBS badge — same dimensions as layer badges
    thumbs_y = layout.thumb_row_y
    d.append(draw.Rectangle(
        x=badge_x, y=thumbs_y,
        width=badge_w, height=badge_h,
        rx=badge_r, ry=badge_r,
        fill=palette.text_color,
    ))
    d.append(draw.Text(
        "THUMBS",
        font_size=badge_font_size,
        x=badge_x + 15.0,
        y=thumbs_y + badge_h / 2.0,
        text_anchor="start",
        dominant_baseline="central",
        font_family=label_font,
        fill="white",
        font_weight="bold",
    ))

    # ---------------------------------------------------------------
    # Finger clusters (all top-aligned per row)
    # ---------------------------------------------------------------
    cluster_width = layout.finger_cluster_width
    all_finger_clusters: list[list[FingerClusterComponent]] = []

    for row_idx, layer_idx in enumerate(row_to_layer):
        layer_data = keymap.layers[layer_idx]
        ctx = RenderContext(
            palette=palette,
            layer_index=layer_idx,
            has_double_south=config.keyboard.features.double_south,
            use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
            hold_symbol_position=config.output.style.hold_symbol_position,
            use_system_fonts=use_system_fonts,
            show_layer_indicators=config.output.style.show_layer_indicators,
        )

        positions = layout.finger_cluster_positions(row_idx)
        row_clusters: list[FingerClusterComponent] = []

        for i in range(_FINGER_CLUSTERS_PER_SIDE):
            c = FingerClusterComponent(
                keymap_cluster=layer_data.left.fingers[i],
                side=KeyboardSide.LEFT,
                layout=Boundary(width=cluster_width, pos=positions[i]),
                render_context=ctx,
            )
            row_clusters.append(c)
            d.append(c.build())

        for i in range(_FINGER_CLUSTERS_PER_SIDE):
            c = FingerClusterComponent(
                keymap_cluster=layer_data.right.fingers[i],
                side=KeyboardSide.RIGHT,
                layout=Boundary(width=cluster_width, pos=positions[_FINGER_CLUSTERS_PER_SIDE + i]),
                render_context=ctx,
            )
            row_clusters.append(c)
            d.append(c.build())

        all_finger_clusters.append(row_clusters)

    # ---------------------------------------------------------------
    # Thumb clusters (layer 0 only)
    # ---------------------------------------------------------------
    left_thumb = right_thumb = None
    if keymap.layers:
        layer0 = keymap.layers[0]
        thumb_ctx = RenderContext(
            palette=palette, layer_index=0,
            has_double_south=config.keyboard.features.double_south,
            use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
            hold_symbol_position=config.output.style.hold_symbol_position,
            use_system_fonts=use_system_fonts,
            show_layer_indicators=config.output.style.show_layer_indicators,
        )
        thumb_w = layout.thumb_cluster_width
        left_pos, right_pos = layout.thumb_cluster_positions()

        left_thumb = ThumbClusterComponent(
            keymap_cluster=layer0.left.thumb, side=KeyboardSide.LEFT,
            layout=Boundary(width=thumb_w, pos=left_pos), render_context=thumb_ctx,
        )
        d.append(left_thumb.build())

        right_thumb = ThumbClusterComponent(
            keymap_cluster=layer0.right.thumb, side=KeyboardSide.RIGHT,
            layout=Boundary(width=thumb_w, pos=right_pos), render_context=thumb_ctx,
        )
        d.append(right_thumb.build())

    # ---------------------------------------------------------------
    # Connector lines (finger + thumb indicators)
    # ---------------------------------------------------------------
    if config.output.style.show_layer_indicators:
        layer_to_row = {li: ri for ri, li in enumerate(row_to_layer)}
        all_row_bounds = [layout.layer_row_bounding_box(i) for i in range(render_layer_count)]

        finger_indicators = _collect_indicator_positions(
            all_finger_clusters, keymap, row_to_layer
        )

        thumb_indicators: list[tuple[float, float, int]] = []
        if left_thumb and right_thumb:
            thumb_indicators = _collect_thumb_indicator_positions(
                left_thumb, right_thumb, keymap
            )

        _draw_connector_lines(
            d, layout, finger_indicators, thumb_indicators,
            config, all_row_bounds, layer_to_row,
        )

    # ---------------------------------------------------------------
    # Optional copyright
    # ---------------------------------------------------------------
    if config.output.copyright:
        d.append(draw.Text(
            config.output.copyright,
            font_size=max(6, int(canvas_h * 0.012)),
            x=canvas_w - padding,
            y=canvas_h - padding,
            text_anchor="end",
            dominant_baseline="text-after-edge",
            font_family=title_font,
            fill=palette.text_color,
            opacity=0.6,
        ))

    return d
