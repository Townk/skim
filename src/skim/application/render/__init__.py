# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Rendering module for generating keymap visualizations.

This package contains the core rendering logic for transforming
keymap data into SVG drawings. It handles:
- Layout calculation (Finger/Thumb clusters)
- Component rendering (Keys, Clusters)
- Styling and coloring
- Text and font management
- Geometry and shape generation
"""

import drawsvg as draw

from skim.assets import ASSETS
from skim.data import (
    KeymapGeneratorTargets,
    SkimConfig,
    SplitSide,
    SvalboardKeymap,
    SvalboardLayout,
)
from skim.domain import KeyboardSide, SvalboardTargetKey

from .components import FingerClusterComponent, ThumbClusterComponent
from .context import RenderContext
from .geometry import AspectRatio
from .layout import Boundary, KeymapLayout
from .overview import draw_overview
from .styling import make_gradient
from .text import Font, FontSubsetter, FontUsageAnalyzer, Label


def _draw_layer(
    config: SkimConfig,
    layer: SvalboardLayout[SvalboardTargetKey],
    config_position: int,
    qmk_index: int,
) -> draw.Drawing:
    use_system_fonts = config.output.style.use_system_fonts
    render_context = RenderContext(
        palette=config.output.style.palette,
        layer_index=config_position,
        qmk_index_to_position=config.keyboard.qmk_index_to_position,
        has_double_south=config.keyboard.features.double_south,
        use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
        hold_symbol_position=config.output.style.hold_symbol_position,
        use_system_fonts=use_system_fonts,
        show_layer_indicators=config.output.style.show_layer_indicators,
    )
    layer_layout = KeymapLayout(config)
    m = layer_layout.metrics

    finger_clusters: list[FingerClusterComponent] = []

    for i, pos in enumerate(layer_layout.left_finger_positions()):
        cluster = FingerClusterComponent(
            keymap_cluster=layer.left.fingers[i],
            side=KeyboardSide.LEFT,
            layout=Boundary(width=m.finger_cluster_width, pos=pos),
            render_context=render_context,
        )
        finger_clusters.append(cluster)

    for i, pos in enumerate(layer_layout.right_finger_positions()):
        cluster = FingerClusterComponent(
            keymap_cluster=layer.right.fingers[i],
            side=KeyboardSide.RIGHT,
            layout=Boundary(width=m.finger_cluster_width, pos=pos),
            render_context=render_context,
        )
        finger_clusters.append(cluster)

    # Reference cluster for height calculation (any things will do since they
    # all have the same height)
    cluster_height = finger_clusters[0].height

    # Add padding for indicator circles on inward thumb keys
    indicator_padding = 0.0
    if config.output.style.show_layer_indicators:
        indicator_padding = m.thumb_cluster_width * 0.1

    # Create thumb clusters
    left_thumb_pos, right_thumb_pos = layer_layout.thumb_positions(
        cluster_height, indicator_padding=indicator_padding
    )

    left_thumb = ThumbClusterComponent(
        keymap_cluster=layer.left.thumb,
        side=KeyboardSide.LEFT,
        layout=Boundary(width=m.thumb_cluster_width, pos=left_thumb_pos),
        render_context=render_context,
    )

    right_thumb = ThumbClusterComponent(
        keymap_cluster=layer.right.thumb,
        side=KeyboardSide.RIGHT,
        layout=Boundary(width=m.thumb_cluster_width, pos=right_thumb_pos),
        render_context=render_context,
    )

    canvas_height = layer_layout.canvas_height(cluster_height, left_thumb.height)

    # Create drawing
    d = draw.Drawing(m.width, canvas_height)

    # Layer title
    layer_title = (
        f"Layer {qmk_index}"
        if config_position >= len(config.keyboard.layers)
        else config.keyboard.layers[config_position].name
    )
    if "layer" not in layer_title.lower():
        layer_title += " Layer"

    labels_keymap: SvalboardLayout[Label | None] = SvalboardLayout(
        left=SplitSide(
            index=finger_clusters[0].cluster,
            middle=finger_clusters[1].cluster,
            ring=finger_clusters[2].cluster,
            pinky=finger_clusters[3].cluster,
            thumb=left_thumb.cluster,
        ),
        right=SplitSide(
            index=finger_clusters[4].cluster,
            middle=finger_clusters[5].cluster,
            ring=finger_clusters[6].cluster,
            pinky=finger_clusters[7].cluster,
            thumb=right_thumb.cluster,
        ),
    ).map(lambda key: None if key is None else key.label)

    use_system_fonts = config.output.style.use_system_fonts

    if not use_system_fonts:
        font_analyzer = FontUsageAnalyzer()
        font_analyzer.analyze_keymap(labels_keymap, layer_title)

        font_subsetter = FontSubsetter(font_analyzer)
        subsetted_css = font_subsetter.generate_subsetted_css()
        if subsetted_css:
            d.append_css(subsetted_css)
        else:
            d.append_css(font_subsetter.generate_full_fonts_css())

    # Background rectangle
    border = config.output.style.border
    d.append(
        draw.Rectangle(
            x=m.margin,
            y=m.margin,
            width=m.width - m.margin * 2.0,
            height=canvas_height - m.margin * 2.0,
            rx=border.radius if border else None,
            ry=border.radius if border else None,
            fill=config.output.style.palette.background_color,
            stroke=config.output.style.palette.border_color if border else None,
            stroke_width=border.width if border else None,
        )
    )

    # Append all clusters
    for cluster in finger_clusters:
        d.append(cluster.build())
    d.append(left_thumb.build())
    d.append(right_thumb.build())

    title_font = Font.TITLE.get_system_font_family() if use_system_fonts else Font.TITLE.value
    d.append(
        draw.Text(
            layer_title,
            font_size=canvas_height * 0.08,
            x=m.start,
            y=right_thumb.y + right_thumb.height,
            text_anchor="start",
            dominant_baseline="text-after-edge",
            font_family=title_font,
        )
    )

    # Logo
    logo_ar = AspectRatio.from_dimensions(width=2333.333, height=458.333, precision=2)
    logo_path = ASSETS.logo_svalboard
    logo_width = m.width * 0.14
    logo_height = logo_ar.height_from_width(logo_width)
    logo_svg = draw.Image(
        x=m.end - logo_width,
        y=(right_thumb.y + right_thumb.height) - logo_height,
        width=logo_width,
        height=logo_height,
        path=logo_path,
        embed=True,
    )
    d.append(logo_svg)

    return d


def _selected_layers(
    keymap: SvalboardKeymap[SvalboardTargetKey],
    targets: KeymapGeneratorTargets,
    config: SkimConfig,
):
    if targets.selected_layers:
        for qmk_idx in targets.selected_layers:
            pos = config.keyboard.qmk_index_to_position(qmk_idx)
            if pos is not None and qmk_idx in keymap.layers:
                yield qmk_idx, pos, keymap.layers[qmk_idx]
    elif targets.all_layers:
        for pos, layer_cfg in enumerate(config.keyboard.layers):
            qmk_idx = layer_cfg.index
            if qmk_idx in keymap.layers:
                yield qmk_idx, pos, keymap.layers[qmk_idx]


def draw_keymap(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    targets: KeymapGeneratorTargets,
) -> dict[str, draw.Drawing]:
    keymap_images: dict[str, draw.Drawing] = {}
    for qmk_idx, pos, layer in _selected_layers(keymap, targets, config):
        keymap_images[f"keymap-layer-{qmk_idx}"] = _draw_layer(config, layer, pos, qmk_idx)

    if targets.overview:
        keymap_images["keymap-overview"] = draw_overview(config, keymap)

    return keymap_images


__all__ = [
    "draw_keymap",
    "make_gradient",
]
