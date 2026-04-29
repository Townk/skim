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
from skim.domain import KeyboardSide, SvalboardMacro, SvalboardTapDance, SvalboardTargetKey

from .components import FingerClusterComponent, ThumbClusterComponent
from .context import RenderContext
from .layout import Boundary, KeymapLayout
from .legend import (
    build_legend,
    collect_used_ids,
    legend_height,
    plan_layout,
    resolve_macros,
    resolve_tap_dances,
)
from .overview import HeaderDims, compute_header_dims, draw_overview
from .styling import make_gradient
from .text import Font, FontSubsetter, FontUsageAnalyzer, Label


def _draw_layer(
    config: SkimConfig,
    layer: SvalboardLayout[SvalboardTargetKey],
    config_position: int,
    qmk_index: int,
    header_dims: HeaderDims,
    macros: tuple[SvalboardMacro[SvalboardTargetKey], ...] = (),
    tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...] = (),
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

    # Header strip (title + logo) sits at the top of the canvas. Sizes, outer
    # padding, and the gap below the header all come from the overview (see
    # compute_header_dims) so typography and spacing match it verbatim. The
    # header zone reserves the height of the taller element, plus the
    # overview's row_gap before the clusters start.
    title_font_size = header_dims.title_font_size
    logo_width = header_dims.logo_width
    logo_height = header_dims.logo_height
    outer_padding = header_dims.outer_padding
    gap_below_header = header_dims.gap_below_header
    header_height = max(title_font_size, logo_height)
    # The cluster top is conventionally at margin + inset + top_indicator_offset.
    # We want it at outer_padding + header_height + gap_below_header, so add the
    # difference as header_offset.
    header_offset = outer_padding - m.margin - m.inset + header_height + gap_below_header

    # Reserve extra space only when a key with a layer_switch will actually render
    # an indicator that overflows the cluster bounds. The indicator dimensions
    # (circle diameter + gap) are derived from each cluster's outer-key width —
    # see ThumbClusterComponent / FingerClusterComponent for the source proportions.
    # When the horizontal offset kicks in, both finger clusters and the thumb on
    # each side shift outward together so the keyboard reads as one unit per side.
    vertical_indicator_offset = 0.0
    horizontal_indicator_offset = 0.0
    top_indicator_offset = 0.0
    if config.output.style.show_layer_indicators:
        thumb_indicator_offset = m.thumb_cluster_width * 0.25 * (0.4 + 0.18)
        finger_indicator_offset = m.finger_cluster_width * 0.328 * (0.55 + 0.18)
        if (
            layer.left.thumb.double_down_key.layer_switch is not None
            or layer.right.thumb.double_down_key.layer_switch is not None
        ):
            vertical_indicator_offset = thumb_indicator_offset
        if any(
            getattr(side.thumb, key).layer_switch is not None
            for side in (layer.left, layer.right)
            for key in ("nail_key", "knuckle_key")
        ):
            horizontal_indicator_offset = thumb_indicator_offset
        # Only the middle and ring clusters sit at the unshifted top — their
        # north_key indicators are the only ones that extend above the canvas
        # margin. Index and pinky clusters are offset down by one key, and
        # east/west indicators sit above their key (mid-cluster), not above
        # the cluster top.
        if any(
            getattr(side, finger).north_key.layer_switch is not None
            for side in (layer.left, layer.right)
            for finger in ("middle", "ring")
        ):
            top_indicator_offset = finger_indicator_offset

    finger_clusters: list[FingerClusterComponent] = []

    for i, pos in enumerate(
        layer_layout.left_finger_positions(
            horizontal_indicator_offset=horizontal_indicator_offset,
            top_indicator_offset=top_indicator_offset,
            header_offset=header_offset,
        )
    ):
        cluster = FingerClusterComponent(
            keymap_cluster=layer.left.fingers[i],
            side=KeyboardSide.LEFT,
            layout=Boundary(width=m.finger_cluster_width, pos=pos),
            render_context=render_context,
        )
        finger_clusters.append(cluster)

    for i, pos in enumerate(
        layer_layout.right_finger_positions(
            horizontal_indicator_offset=horizontal_indicator_offset,
            top_indicator_offset=top_indicator_offset,
            header_offset=header_offset,
        )
    ):
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

    # Create thumb clusters
    left_thumb_pos, right_thumb_pos = layer_layout.thumb_positions(
        cluster_height,
        vertical_indicator_offset=vertical_indicator_offset,
        horizontal_indicator_offset=horizontal_indicator_offset,
        top_indicator_offset=top_indicator_offset,
        header_offset=header_offset,
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

    canvas_width = layer_layout.canvas_width(
        horizontal_indicator_offset=horizontal_indicator_offset
    )
    # Keyboard-area height as the existing layout helper computes it. This
    # already includes the bottom inset below the thumb cluster.
    keyboard_canvas_h = layer_layout.canvas_height(
        cluster_height,
        left_thumb.height,
        vertical_indicator_offset=vertical_indicator_offset,
        top_indicator_offset=top_indicator_offset,
        header_offset=header_offset,
    )
    bottom_inset = m.inset + m.margin
    copyright_font_size = header_dims.copyright_font_size
    copyright_extra = (
        copyright_font_size + bottom_inset if config.output.copyright else 0.0
    )

    # Plan the legend and reserve its vertical space.
    if config.output.style.show_special_keys_legend:
        used_macro_ids, used_td_ids = collect_used_ids(layer)
        macro_entries = resolve_macros(used_macro_ids, macros)
        td_entries = resolve_tap_dances(used_td_ids, tap_dances)
        legend_plan = plan_layout(macro_entries, td_entries)
    else:
        legend_plan = None

    legend_top_gap = 36.0
    content_width = canvas_width - 2 * outer_padding
    legend_h = legend_height(legend_plan, content_width)
    keyboard_bottom = keyboard_canvas_h - bottom_inset
    legend_top = keyboard_bottom + legend_top_gap if legend_h > 0 else None

    canvas_height = keyboard_canvas_h
    if legend_h > 0:
        canvas_height += legend_top_gap + legend_h
    canvas_height += copyright_extra

    # Create drawing
    d = draw.Drawing(canvas_width, canvas_height)

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
        font_analyzer.analyze_keymap(labels_keymap, layer_title, config.output.copyright)
        font_analyzer.analyze_legend(macros, tap_dances)

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
            width=canvas_width - m.margin * 2.0,
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
            font_size=title_font_size,
            x=outer_padding,
            y=outer_padding,
            text_anchor="start",
            dominant_baseline="hanging",
            font_family=title_font,
        )
    )

    logo_svg = draw.Image(
        x=canvas_width - outer_padding - logo_width,
        y=outer_padding,
        width=logo_width,
        height=logo_height,
        path=ASSETS.logo_svalboard,
        embed=True,
    )
    d.append(logo_svg)

    if config.output.copyright:
        label_font = (
            Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value
        )
        d.append(
            draw.Text(
                config.output.copyright,
                font_size=copyright_font_size,
                x=canvas_width - outer_padding,
                y=canvas_height - bottom_inset,
                text_anchor="end",
                dominant_baseline="text-after-edge",
                font_family=label_font,
                fill=config.output.style.palette.text_color,
                opacity=0.6,
            )
        )

    if legend_plan is not None and legend_top is not None:
        legend_group = build_legend(
            layout=legend_plan,
            x=outer_padding,
            y=legend_top,
            content_width=content_width,
            palette=config.output.style.palette,
            use_system_fonts=use_system_fonts,
        )
        if legend_group is not None:
            d.append(legend_group)

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
    header_dims = compute_header_dims(config, keymap)
    for qmk_idx, pos, layer in _selected_layers(keymap, targets, config):
        keymap_images[f"keymap-layer-{qmk_idx}"] = _draw_layer(
            config, layer, pos, qmk_idx, header_dims,
            macros=keymap.macros,
            tap_dances=keymap.tap_dances,
        )

    if targets.overview:
        keymap_images["keymap-overview"] = draw_overview(config, keymap)

    return keymap_images


__all__ = [
    "draw_keymap",
    "make_gradient",
]
