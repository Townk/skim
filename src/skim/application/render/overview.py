# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Overview image rendering for multi-layer keymap visualization.

This module provides the draw_overview() function that generates a full
overview SVG image showing all keymap layers in a two-column layout:
- Left column: Svalboard logo, "LAYERS" heading, per-layer labels
- Right column: Layout title, all layer finger clusters, thumb clusters
"""

import drawsvg as draw

from skim.assets import ASSETS
from skim.data import SkimConfig, SplitSide, SvalboardKeymap, SvalboardLayout
from skim.domain import KeyboardSide, SvalboardTargetKey

from .components import FingerClusterComponent, ThumbClusterComponent
from .context import RenderContext
from .geometry import AspectRatio
from .indicators import LayerIndicator, _finger_cluster_offset, _FINGER_KEY_NAMES
from .layout import Boundary, KeymapLayoutMetrics
from .overview_layout import OverviewLayout
from .text import Font, Label


# Svalboard logo aspect ratio (original dimensions: 2333.333 x 458.333)
_LOGO_ASPECT_RATIO = AspectRatio.from_dimensions(width=2333.333, height=458.333, precision=2)

# Number of finger clusters per side
_FINGER_CLUSTERS_PER_SIDE = 4

# Routing margin: how far past the cluster right edge we go before turning
_CONNECTOR_ROUTING_MARGIN = 12.0


def _collect_indicator_positions(
    all_finger_clusters: list[list[FingerClusterComponent]],
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> list[tuple[int, float, float, int]]:
    """Collect absolute positions of all layer indicator circles.

    Iterates over every finger cluster across all layers and finds keys
    with a ``layer_switch`` value. For each such key, creates a temporary
    ``LayerIndicator`` in cluster-local coordinates and converts the circle
    center to absolute canvas coordinates.

    Args:
        all_finger_clusters: Nested list ``[layer_idx][cluster_idx]`` of
            ``FingerClusterComponent`` objects already placed on the canvas.
        keymap: The full ``SvalboardKeymap`` used to retrieve per-key data.

    Returns:
        A list of ``(source_layer_idx, abs_cx, abs_cy, target_layer_idx)``
        tuples, one entry per indicator circle.
    """
    results: list[tuple[int, float, float, int]] = []

    for layer_idx, layer_clusters in enumerate(all_finger_clusters):
        layer_data = keymap.layers[layer_idx]

        for cluster_idx, cluster_comp in enumerate(layer_clusters):
            # Determine which side / finger this cluster belongs to
            is_right = cluster_idx >= _FINGER_CLUSTERS_PER_SIDE
            finger_idx = cluster_idx - _FINGER_CLUSTERS_PER_SIDE if is_right else cluster_idx
            side = KeyboardSide.RIGHT if is_right else KeyboardSide.LEFT

            finger_cluster_data = (
                layer_data.right.fingers[finger_idx]
                if is_right
                else layer_data.left.fingers[finger_idx]
            )

            metrics = cluster_comp._layout.metrics
            palette = cluster_comp._render_context.palette
            circle_diameter = metrics.north_key.width * 0.55
            gap = metrics.north_key.width * 0.18

            for key_name in _FINGER_KEY_NAMES:
                if key_name == "double_south_key" and not cluster_comp._render_context.has_double_south:
                    continue

                key: SvalboardTargetKey = getattr(finger_cluster_data, key_name)
                if key.layer_switch is None:
                    continue

                layout_boundary = getattr(metrics, key_name)
                offset_dir, conn_type = _finger_cluster_offset(key_name, side)
                key_gap = gap * 3 if key_name == "center_key" else gap

                indicator = LayerIndicator(
                    key_x=layout_boundary.pos.x,
                    key_y=layout_boundary.pos.y,
                    key_width=layout_boundary.width,
                    key_height=layout_boundary.width,
                    target_layer=key.layer_switch,
                    palette=palette,
                    circle_diameter=circle_diameter,
                    gap=key_gap,
                    offset_direction=offset_dir,
                    connector_type=conn_type,
                )

                # Convert local cluster coordinates to absolute canvas coordinates
                abs_cx = cluster_comp.x + indicator.circle_center_x
                abs_cy = cluster_comp.y + indicator.circle_center_y

                results.append((layer_idx, abs_cx, abs_cy, key.layer_switch))

    return results


def _draw_connector_lines(
    d: draw.Drawing,
    layout: OverviewLayout,
    indicator_positions: list[tuple[int, float, float, int]],
    config: SkimConfig,
    all_cluster_bounds: list[tuple[float, float, float, float]],
) -> None:
    """Draw orthogonal dashed connector lines from indicators to target rows.

    For each indicator position, draws an L-shaped (or Z-shaped) SVG path
    from the circle to the bounding region of the target layer's row.  The
    path routes horizontally first to just outside the right edge of the
    cluster area, then vertically to the target row's centre, then
    horizontally back to the row edge.

    Args:
        d: The ``drawsvg.Drawing`` to append elements to.
        layout: The ``OverviewLayout`` for positional information.
        indicator_positions: List of
            ``(source_layer_idx, abs_cx, abs_cy, target_layer_idx)`` tuples.
        config: The ``SkimConfig`` for palette lookups.
        all_cluster_bounds: Bounding boxes
            ``(x, y, width, height)`` for each layer row.
    """
    if not indicator_positions:
        return

    palette = config.output.style.palette
    right_edge = layout.canvas_width

    for _src_layer, abs_cx, abs_cy, target_layer in indicator_positions:
        # Resolve stroke color from target layer palette
        if 0 <= target_layer < len(palette.layers):
            stroke_color = palette.layers[target_layer][4]
        else:
            stroke_color = "#808080"

        # Target row bounding box
        tgt_x, tgt_y, tgt_w, tgt_h = all_cluster_bounds[target_layer]
        target_row_mid_y = tgt_y + tgt_h / 2.0
        target_row_right_x = tgt_x + tgt_w  # right edge of target row

        # Route: start at circle → go right to routing rail → go vertically
        # to target row mid → go left to target row right edge
        routing_x = right_edge - _CONNECTOR_ROUTING_MARGIN

        path_d = (
            f"M {abs_cx:.2f} {abs_cy:.2f} "
            f"L {routing_x:.2f} {abs_cy:.2f} "
            f"L {routing_x:.2f} {target_row_mid_y:.2f} "
            f"L {target_row_right_x - _CONNECTOR_ROUTING_MARGIN:.2f} {target_row_mid_y:.2f}"
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


def draw_overview(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Generate the full overview SVG image for a multi-layer keymap.

    Produces a two-column layout with a left column containing the logo,
    layer labels, and a "THUMBS" label; and a right column containing all
    layer finger clusters stacked as rows with thumb clusters below.

    Args:
        config: The SkimConfig containing layout, styling, and layer parameters.
        keymap: The SvalboardKeymap with all layers of key data.

    Returns:
        A drawsvg Drawing containing the complete overview image.
    """
    layout = OverviewLayout(config)
    use_system_fonts = config.output.style.use_system_fonts

    # Canvas dimensions from OverviewLayout
    canvas_width = layout.canvas_width
    canvas_height = layout.canvas_height

    d = draw.Drawing(canvas_width, canvas_height)

    # Embed fonts (use system fonts or embed from assets)
    if not use_system_fonts:
        for font in Font:
            d.append_css(font.css_style)

    # Background rectangle with rounded border
    border = config.output.style.border
    palette = config.output.style.palette

    # Determine margin for background rect positioning
    metrics = KeymapLayoutMetrics.from_config(config)
    margin = metrics.margin

    d.append(
        draw.Rectangle(
            x=margin,
            y=margin,
            width=canvas_width - margin * 2.0,
            height=canvas_height - margin * 2.0,
            rx=border.radius if border else None,
            ry=border.radius if border else None,
            fill=palette.background_color,
            stroke=palette.border_color if border else None,
            stroke_width=border.width if border else None,
        )
    )

    # ---------------------------------------------------------------
    # Left column: logo, "LAYERS" heading, layer badges, "THUMBS"
    # ---------------------------------------------------------------
    left_col_w = layout.left_column_width
    inset = metrics.inset

    # Svalboard logo at top-left
    logo_width = left_col_w * 0.7
    logo_height = _LOGO_ASPECT_RATIO.height_from_width(logo_width)
    logo_x = margin + inset
    logo_y = margin + inset

    d.append(
        draw.Image(
            x=logo_x,
            y=logo_y,
            width=logo_width,
            height=logo_height,
            path=ASSETS.logo_svalboard,
            embed=True,
        )
    )

    # Determine the alignment X for "LAYERS" heading and layer badges
    # All text left-aligns to a common edge slightly inside the left column
    text_align_x = margin + inset

    # "LAYERS" heading — rendered below the logo
    layers_heading_font_size = max(8, int(left_col_w * 0.08))
    layers_heading_y = logo_y + logo_height + inset

    label_font_family = (
        Font.THUMB_KEY.get_system_font_family() if use_system_fonts else Font.THUMB_KEY.value
    )

    d.append(
        draw.Text(
            "LAYERS",
            font_size=layers_heading_font_size,
            x=text_align_x,
            y=layers_heading_y,
            text_anchor="start",
            dominant_baseline="text-before-edge",
            font_family=label_font_family,
            fill=palette.text_color,
            font_weight="bold",
        )
    )

    # Per-layer badges
    num_layers = len(config.keyboard.layers)
    layer_badge_font_size = max(6, int(left_col_w * 0.065))
    subtitle_font_size = max(5, int(left_col_w * 0.055))
    badge_height = layer_badge_font_size * 1.8
    badge_padding_x = inset * 0.3
    badge_border_radius = badge_height * 0.2

    for layer_idx in range(num_layers):
        row_y = layout.layer_row_y_positions[layer_idx]
        row_h = layout.layer_row_heights[layer_idx]
        # Center the badge vertically within the row
        badge_center_y = row_y + row_h / 2.0
        badge_y = badge_center_y - badge_height / 2.0

        layer_cfg = config.keyboard.layers[layer_idx]
        layer_color = palette.layers[layer_idx].base_color if layer_idx < len(palette.layers) else palette.neutral_color

        # Badge rectangle extends slightly left of text_align_x
        badge_x = text_align_x - badge_padding_x
        badge_width = left_col_w - margin - badge_x + margin

        d.append(
            draw.Rectangle(
                x=badge_x,
                y=badge_y,
                width=badge_width,
                height=badge_height,
                rx=badge_border_radius,
                ry=badge_border_radius,
                fill=layer_color,
            )
        )

        # Badge text: "N LAYERNAME" in white bold
        badge_text = f"{layer_cfg.label} {layer_cfg.name}"
        d.append(
            draw.Text(
                badge_text,
                font_size=layer_badge_font_size,
                x=text_align_x,
                y=badge_y + badge_height / 2.0,
                text_anchor="start",
                dominant_baseline="central",
                font_family=label_font_family,
                fill="white",
                font_weight="bold",
            )
        )

        # Optional subtitle below badge
        if layer_cfg.subtitle:
            subtitle_y = badge_y + badge_height + subtitle_font_size * 0.3
            d.append(
                draw.Text(
                    layer_cfg.subtitle,
                    font_size=subtitle_font_size,
                    x=text_align_x,
                    y=subtitle_y,
                    text_anchor="start",
                    dominant_baseline="text-before-edge",
                    font_family=label_font_family,
                    fill=palette.text_color,
                )
            )

    # "THUMBS" label at the thumb row position
    thumb_row_y = layout.thumb_row_y
    thumbs_font_size = layers_heading_font_size

    d.append(
        draw.Text(
            "THUMBS",
            font_size=thumbs_font_size,
            x=text_align_x,
            y=thumb_row_y,
            text_anchor="start",
            dominant_baseline="text-before-edge",
            font_family=label_font_family,
            fill=palette.text_color,
            font_weight="bold",
        )
    )

    # ---------------------------------------------------------------
    # Right column: layout title at top
    # ---------------------------------------------------------------
    right_col_x = layout.right_column_x
    title_font_family = (
        Font.TITLE.get_system_font_family() if use_system_fonts else Font.TITLE.value
    )

    # Derive layout title from the first layer's name or a generic title
    if num_layers > 0:
        first_layer_name = config.keyboard.layers[0].name
        layout_title = first_layer_name
        if "layer" not in layout_title.lower() and "layout" not in layout_title.lower():
            layout_title = f"{layout_title} Layout"
    else:
        layout_title = "Keymap Layout"

    title_font_size = max(10, int(canvas_height * 0.03))
    title_y = margin + inset
    title_x = right_col_x + (canvas_width - right_col_x) / 2.0

    d.append(
        draw.Text(
            layout_title,
            font_size=title_font_size,
            x=title_x,
            y=title_y,
            text_anchor="middle",
            dominant_baseline="text-before-edge",
            font_family=title_font_family,
            fill=palette.text_color,
        )
    )

    # ---------------------------------------------------------------
    # Finger clusters for all layers
    # ---------------------------------------------------------------
    cluster_width = layout.finger_cluster_width
    all_finger_clusters: list[list[FingerClusterComponent]] = []

    # Only render layers that have config entries (palette colors, labels)
    render_layer_count = min(len(keymap.layers), num_layers)

    for layer_idx in range(render_layer_count):
        layer_data = keymap.layers[layer_idx]
        render_context = RenderContext(
            palette=config.output.style.palette,
            layer_index=layer_idx,
            has_double_south=config.keyboard.features.double_south,
            use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
            hold_symbol_position=config.output.style.hold_symbol_position,
            use_system_fonts=use_system_fonts,
            show_layer_indicators=config.output.style.show_layer_indicators,
        )

        positions = layout.finger_cluster_positions(layer_idx)
        layer_clusters: list[FingerClusterComponent] = []

        # Left side: positions 0-3 (index -> pinky)
        for i in range(_FINGER_CLUSTERS_PER_SIDE):
            cluster = FingerClusterComponent(
                keymap_cluster=layer_data.left.fingers[i],
                side=KeyboardSide.LEFT,
                layout=Boundary(width=cluster_width, pos=positions[i]),
                render_context=render_context,
            )
            layer_clusters.append(cluster)
            d.append(cluster.build())

        # Right side: positions 4-7 (index -> pinky)
        for i in range(_FINGER_CLUSTERS_PER_SIDE):
            cluster = FingerClusterComponent(
                keymap_cluster=layer_data.right.fingers[i],
                side=KeyboardSide.RIGHT,
                layout=Boundary(width=cluster_width, pos=positions[_FINGER_CLUSTERS_PER_SIDE + i]),
                render_context=render_context,
            )
            layer_clusters.append(cluster)
            d.append(cluster.build())

        all_finger_clusters.append(layer_clusters)

    # ---------------------------------------------------------------
    # Connector lines from layer indicator circles to target layer rows
    # ---------------------------------------------------------------
    if config.output.style.show_layer_indicators:
        all_cluster_bounds = [layout.layer_row_bounding_box(i) for i in range(render_layer_count)]
        indicator_positions = _collect_indicator_positions(all_finger_clusters, keymap)
        _draw_connector_lines(d, layout, indicator_positions, config, all_cluster_bounds)

    # ---------------------------------------------------------------
    # Thumb clusters for layer 0 only
    # ---------------------------------------------------------------
    if keymap.layers:
        layer0 = keymap.layers[0]
        thumb_render_context = RenderContext(
            palette=config.output.style.palette,
            layer_index=0,
            has_double_south=config.keyboard.features.double_south,
            use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
            hold_symbol_position=config.output.style.hold_symbol_position,
            use_system_fonts=use_system_fonts,
            show_layer_indicators=config.output.style.show_layer_indicators,
        )
        thumb_cluster_width = layout.thumb_cluster_width
        left_thumb_pos, right_thumb_pos = layout.thumb_cluster_positions()

        left_thumb = ThumbClusterComponent(
            keymap_cluster=layer0.left.thumb,
            side=KeyboardSide.LEFT,
            layout=Boundary(width=thumb_cluster_width, pos=left_thumb_pos),
            render_context=thumb_render_context,
        )
        d.append(left_thumb.build())

        right_thumb = ThumbClusterComponent(
            keymap_cluster=layer0.right.thumb,
            side=KeyboardSide.RIGHT,
            layout=Boundary(width=thumb_cluster_width, pos=right_thumb_pos),
            render_context=thumb_render_context,
        )
        d.append(right_thumb.build())

    # ---------------------------------------------------------------
    # Optional copyright text at bottom-right
    # ---------------------------------------------------------------
    if config.output.copyright:
        copyright_font_size = max(6, int(canvas_height * 0.018))
        copyright_x = canvas_width - margin - inset
        copyright_y = canvas_height - margin - inset

        d.append(
            draw.Text(
                config.output.copyright,
                font_size=copyright_font_size,
                x=copyright_x,
                y=copyright_y,
                text_anchor="end",
                dominant_baseline="text-after-edge",
                font_family=title_font_family,
                fill=palette.text_color,
            )
        )

    return d
