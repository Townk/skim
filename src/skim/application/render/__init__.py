import drawsvg as draw

from skim.application.render.components import (
    FingerClusterComponent,
    ThumbClusterComponent,
)
from skim.application.render.context import RenderContext
from skim.application.render.geometry import AspectRatio
from skim.application.render.layout import Boundary, KeymapLayout
from skim.application.render.text import Font
from skim.assets import ASSETS
from skim.data.cli import KeymapGeneratorTargets
from skim.data.config import SkimConfig
from skim.data.keyboard import SvalboardKeymap, SvalboardLayout
from skim.domain.domain_types import KeyboardSide, SvalboardTargetKey


def _draw_layer(
    config: SkimConfig, layer: SvalboardLayout[SvalboardTargetKey], layer_idx: int
) -> draw.Drawing:
    render_context = RenderContext(
        palette=config.output.style.palette,
        layer_index=layer_idx,
        has_double_south=config.keyboard.features.double_south,
        use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
        hold_symbol_position=config.output.style.hold_symbol_position,
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

    # Create thumb clusters
    left_thumb_pos, right_thumb_pos = layer_layout.thumb_positions(cluster_height)

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
    Font.embed_fonts_into(d)

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

    # Layer title
    title = (
        f"Layer {layer_idx}"
        if layer_idx >= len(config.keyboard.layers)
        else config.keyboard.layers[layer_idx].name
    )
    if "layer" not in title.lower():
        title += " Layer"

    d.append(
        draw.Text(
            title,
            font_size=canvas_height * 0.08,
            x=m.start,
            y=right_thumb.y + right_thumb.height,
            text_anchor="start",
            dominant_baseline="text-after-edge",
            font_family=Font.TITLE.value,
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


def _selected_layers(keymap: SvalboardKeymap[SvalboardTargetKey], targets: KeymapGeneratorTargets):
    if targets.selected_layers:
        for idx in targets.selected_layers:
            yield idx, keymap.layers[idx]
    elif targets.all_layers:
        for idx, layer in enumerate(keymap.layers):
            yield idx, layer


def draw_keymap(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    targets: KeymapGeneratorTargets,
) -> dict[str, draw.Drawing]:
    keymap_images: dict[str, draw.Drawing] = {}
    for idx, layer in _selected_layers(keymap, targets):
        keymap_images[f"keymap-layer-{idx}"] = _draw_layer(config, layer, idx)
    return keymap_images
