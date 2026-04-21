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
from .layout import Boundary
from .overview_layout import OverviewLayout
from .text import Font, Label


# Svalboard logo aspect ratio (original dimensions: 2333.333 x 458.333)
_LOGO_ASPECT_RATIO = AspectRatio.from_dimensions(width=2333.333, height=458.333, precision=2)

# Number of finger clusters per side
_FINGER_CLUSTERS_PER_SIDE = 4


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
    from .layout import KeymapLayoutMetrics
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
        Font.LABEL.get_system_font_family() if use_system_fonts else Font.LABEL.value
        if hasattr(Font, "LABEL") else
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

    for layer_idx, layer_data in enumerate(keymap.layers):
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
