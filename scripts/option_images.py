"""Generate focused, label-free SVG snippets that demonstrate single
configuration options for the docs.

Each "option image" is a side-by-side pair (or small set) of variants
rendered through the **real** Skim composables — not bespoke doc-only
artwork — so visual changes to the renderer flow through to the docs on
the next run. Output lands in ``docs/_static/options/<option>/<variant>.svg``
and is embedded in ``docs/configuration/config-file.md`` via plain
Markdown image tags.

Run via ``just option-images``.

Adding a new option
-------------------

Append a builder function to ``BUILDERS`` (mirrors ``screenshots.py``).
Each builder yields ``(variant_name, drawsvg.Drawing)`` pairs. The
machinery below saves them under ``docs/_static/options/<option>/``.

Use :func:`_render_partial` rather than :func:`skim...composable.render`
when the snippet should match the composable's natural pixel size — the
full ``render`` entry point follows ``config.output.layout.width``, which
is correct for a complete keymap image but oversized for a single cluster.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import drawsvg as draw
import yaml

from skim.application.render.composable import Component
from skim.application.render.keymap_overview import LayerBadge
from skim.application.render.primitives import Point, Size
from skim.application.render.render_context import (
    RenderContext,
    using_render_context,
)
from skim.application.render.styling import default_layer_color
from skim.application.render.svalboard_clusters import FingerCluster, ThumbCluster
from skim.data.config import (
    KeyboardLayer,
    LayerColor,
    SkimConfig,
)
from skim.data.keyboard import (
    FingerCluster as FingerClusterData,
    SvalboardKeymap,
    SvalboardLayout,
    ThumbCluster as ThumbClusterData,
)
from skim.domain import KeyboardSide, SvalboardTargetKey

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = ROOT / "docs" / "_static" / "options"
SAMPLES = ROOT / "samples" / "config"

# Shared natural sizing for cluster snippets so finger and thumb shots
# render at matching cluster heights (the thumb's 1.5:1 aspect means
# its width is 1.5 × the finger width to land on the same height).
FINGER_CLUSTER_WIDTH = 220.0
THUMB_CLUSTER_WIDTH = FINGER_CLUSTER_WIDTH * 1.5

# Shared card dimensions: same canvas height, widths follow each
# cluster's own width plus a small frame padding. The shared height
# lets the markdown set ``height="..."`` and have all cluster figures
# line up vertically across sections.
_CARD_HEIGHT = 240.0
_CARD_PADDING = 20.0
FINGER_CARD = Size(FINGER_CLUSTER_WIDTH + _CARD_PADDING, _CARD_HEIGHT)
THUMB_CARD = Size(THUMB_CLUSTER_WIDTH + _CARD_PADDING, _CARD_HEIGHT)

# The double-south finger cluster grows vertically (the sixth key sits
# below south) — it doesn't fit in the standard ``FINGER_CARD`` height.
# The double-south pair gets its own taller card so both variants in
# the pair share the same frame even though one of them naturally fits
# in the smaller card.
DOUBLE_SOUTH_CARD = Size(FINGER_CLUSTER_WIDTH + _CARD_PADDING, 316.0)

# Re-exported so builders that wrap their own components in a card can
# reuse the same padding constant the standard helpers use.
CARD_PADDING = _CARD_PADDING

OptionBuilder = Callable[[], Iterator[tuple[str, draw.Drawing]]]


def _load_palette_layer(sample: str, position: int) -> LayerColor:
    """Pull a single :class:`LayerColor` out of a bundled sample config.

    Lets option images borrow real palette stops (with their gradients)
    from the curated sample configs in ``samples/config/`` so the docs
    look like a real keymap and not a blank reference grid.
    """
    return _load_palette_layers(sample, count=position + 1)[position]


def _load_palette_layers(sample: str, count: int) -> tuple[LayerColor, ...]:
    """Pull the first ``count`` palette stops out of a bundled sample.

    Used when an option image needs more than one layer's colour (e.g.
    a cluster that paints its own colour and renders an indicator
    pointing at a different layer's colour).
    """
    path = SAMPLES / sample
    with open(path) as f:
        data = yaml.safe_load(f)
    config = SkimConfig.model_validate(data)
    return config.output.style.palette.layers[:count]


def _build_minimal_config(
    *,
    layer_index: int = 0,
    layer_color: LayerColor | None = None,
) -> SkimConfig:
    """A SkimConfig with one layer at ``layer_index`` and system fonts on.

    Pass ``layer_color`` to substitute a real palette stop (typically
    pulled via :func:`_load_palette_layer`) so the rendered cluster
    inherits the gradient it would have in a real keymap. When
    ``None``, Skim falls back to the QMK hue-distribution default for
    that layer.

    System fonts keeps the SVG payload tiny — we don't need pixel-perfect
    typography for option illustrations, and there are usually no labels
    on these snippets anyway.
    """
    config = SkimConfig()
    keyboard = config.keyboard.model_copy(
        update={"layers": (KeyboardLayer(index=layer_index, name="Demo"),)}
    )
    style_updates: dict = {"use_system_fonts": True}
    if layer_color is not None:
        style_updates["palette"] = config.output.style.palette.model_copy(
            update={"layers": (layer_color,)}
        )
    style = config.output.style.model_copy(update=style_updates)
    output = config.output.model_copy(update={"style": style})
    return config.model_copy(update={"keyboard": keyboard, "output": output})


def _empty_keymap(*, layer_index: int) -> SvalboardKeymap[SvalboardTargetKey]:
    """A keymap with one layer of empty keys.

    The FingerCluster composable accepts cluster data directly, so the
    keymap mostly exists to satisfy ``RenderContext.build``. An empty
    label means the per-key composable paints background + border but no
    text.
    """
    blank = SvalboardTargetKey(label="")
    layout = SvalboardLayout.from_sequence([blank] * 60)
    return SvalboardKeymap(layers={layer_index: layout})


def _empty_finger_cluster() -> FingerClusterData[SvalboardTargetKey]:
    """A finger cluster with empty labels in every slot."""
    blank = SvalboardTargetKey(label="")
    return FingerClusterData(blank)


def _build_palette_config(
    *,
    num_layers: int,
    palette_layers: tuple[LayerColor, ...] | None = None,
) -> SkimConfig:
    """Build a SkimConfig with N keyboard layers and matching palette stops.

    Composables that paint layer indicators read the destination layer's
    colour off ``ctx.theme.palette.layers[layer_switch]``. If the palette
    is empty the lookup falls back to neutral grey, which loses the
    "this key sends you to layer X" signal we want for these snippets.

    Pass ``palette_layers`` to use the curated colours from a sample
    config (typically loaded via :func:`_load_palette_layers`) so the
    snippets read like a real keymap. When ``None``, falls back to the
    auto-generated :func:`default_layer_color` palette.
    """
    config = SkimConfig()
    keyboard = config.keyboard.model_copy(
        update={
            "layers": tuple(
                KeyboardLayer(index=i, name=f"Layer {i}") for i in range(num_layers)
            )
        }
    )
    if palette_layers is None:
        palette_layers = tuple(
            LayerColor(base_color=default_layer_color(i)) for i in range(num_layers)
        )
    palette = config.output.style.palette.model_copy(update={"layers": palette_layers})
    style = config.output.style.model_copy(
        update={"use_system_fonts": True, "palette": palette}
    )
    output = config.output.model_copy(update={"style": style})
    return config.model_copy(update={"keyboard": keyboard, "output": output})


def _render_partial(component: Component) -> draw.Drawing:
    """Render a single composable into an SVG sized to its natural bbox.

    Differs from :func:`composable.render` in two ways: it ignores
    ``config.output.layout.width`` (we want the natural cluster size,
    not a full-keymap canvas), and it does not subset fonts (system
    fonts are on for option snippets, so the embedded-font path is
    skipped anyway).
    """
    canvas_w = component.size.width
    canvas_h = component.size.height
    d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")
    # Snippets use system fonts, so no @font-face CSS is needed.
    component.draw_at(d, Point(0, 0))
    return d


def _render_in_card(
    component: Component,
    *,
    canvas: Size,
    corner_radius: float = 18.0,
    stroke_color: str = "#D4D8DD",
    stroke_width: float = 1.0,
    fill: str = "#FFFFFF",
) -> draw.Drawing:
    """Render a component centred inside a fixed-size rounded-rect "card".

    Used when a row of option images mixes composables of different
    natural heights — without a fixed-size container, an
    HTML ``<img width="...">`` attribute scales each SVG independently
    and the thumb cluster ends up half the height of the finger cluster.
    Wrapping both in the same canvas size gives the figures matching
    display heights and a consistent visual frame.

    The component is centred inside the canvas, preserving its natural
    proportions; whatever space remains becomes white margin.
    """
    canvas_w, canvas_h = canvas.width, canvas.height
    d = draw.Drawing(canvas_w, canvas_h, viewBox=f"0 0 {canvas_w} {canvas_h}")
    inset = stroke_width / 2.0  # keep the stroke fully inside the canvas
    d.append(
        draw.Rectangle(
            x=inset,
            y=inset,
            width=canvas_w - stroke_width,
            height=canvas_h - stroke_width,
            rx=corner_radius,
            ry=corner_radius,
            fill=fill,
            stroke=stroke_color,
            stroke_width=stroke_width,
        )
    )
    offset_x = (canvas_w - component.size.width) / 2.0
    offset_y = (canvas_h - component.size.height) / 2.0
    component.draw_at(d, Point(offset_x, offset_y))
    return d


def _build_double_south() -> Iterator[tuple[str, draw.Drawing]]:
    """Two finger clusters: one with the double-south key, one without.

    Uses the COLEMAK sample's layer-0 palette stop (teal-green gradient)
    so the snippet reads like a real keymap rather than a cold default.
    Wraps each cluster in the shared white rounded-rect card so the
    pair matches the visual frame of the other cluster snippets.
    """
    palette = _load_palette_layers("SvalCOLEMAK-config.yaml", count=1)
    config = _build_palette_config(num_layers=1, palette_layers=palette)
    keymap = _empty_keymap(layer_index=0)
    ctx = RenderContext.build(config=config, keymap=keymap)

    cluster_data = _empty_finger_cluster()
    cluster_width = FINGER_CLUSTER_WIDTH

    with using_render_context(ctx):
        for variant, has_double_south in (("without", False), ("with", True)):
            component = FingerCluster(
                cluster=cluster_data,
                side=KeyboardSide.LEFT,
                width=cluster_width,
                layer_qmk_index=0,
                has_double_south=has_double_south,
                use_layer_colors_on_keys=False,
                show_layer_indicators=False,
            )
            yield variant, _render_in_card(component, canvas=DOUBLE_SOUTH_CARD)


def _build_keyboard_layers() -> Iterator[tuple[str, draw.Drawing]]:
    """Four small visuals showing where ``keyboard.layers`` data shows up
    in the rendered keymap: the ``index`` field surfaces in layer
    indicators on switch keys and in the layer badges of the overview
    image.

    Pulls palette colours from the bundled COLEMAK sample so the
    snippets share the visual identity of the other cluster shots
    (which load from the same source).
    """
    palette = _load_palette_layers("SvalCOLEMAK-config.yaml", count=4)
    config = _build_palette_config(num_layers=4, palette_layers=palette)
    keymap = _empty_keymap(layer_index=0)
    ctx = RenderContext.build(config=config, keymap=keymap)

    blank = SvalboardTargetKey(label="")
    badge_height = FINGER_CLUSTER_WIDTH * 0.328  # matches _OUTER_KEY_PROPORTION

    with using_render_context(ctx):
        # 1. Finger cluster, layer indicator on the centre key (layer 3).
        finger_cluster = FingerClusterData(
            blank,
            center_key=SvalboardTargetKey(label="", layer_switch=3),
        )
        yield (
            "finger-with-indicator",
            _render_in_card(
                FingerCluster(
                    cluster=finger_cluster,
                    side=KeyboardSide.LEFT,
                    width=FINGER_CLUSTER_WIDTH,
                    layer_qmk_index=0,
                    has_double_south=False,
                    use_layer_colors_on_keys=False,
                    show_layer_indicators=True,
                ),
                canvas=FINGER_CARD,
            ),
        )

        # 2. Thumb cluster, layer indicator on the down key (layer 2).
        thumb_cluster = ThumbClusterData(
            blank,
            down_key=SvalboardTargetKey(label="", layer_switch=2),
        )
        yield (
            "thumb-with-indicator",
            _render_in_card(
                ThumbCluster(
                    cluster=thumb_cluster,
                    side=KeyboardSide.LEFT,
                    width=THUMB_CLUSTER_WIDTH,
                    layer_qmk_index=0,
                    use_layer_colors_on_keys=False,
                    show_layer_indicators=True,
                ),
                canvas=THUMB_CARD,
            ),
        )

        # 3 & 4. Layer badges from the overview image — one for an
        # auto-named layer, one with a custom name. Widths chosen to fit
        # the longest text comfortably.
        badge_layer_3_color = config.output.style.palette.layers[3].base_color
        yield (
            "badge-unnamed",
            _render_partial(
                LayerBadge(
                    text="LAYER 3",
                    badge_width=260.0,
                    badge_height=badge_height,
                    border_radius=badge_height * 0.2,
                    fill_color=badge_layer_3_color,
                )
            ),
        )

        badge_layer_2_color = config.output.style.palette.layers[2].base_color
        yield (
            "badge-named",
            _render_partial(
                LayerBadge(
                    text="2 MY CUSTOM NAME",
                    badge_width=400.0,
                    badge_height=badge_height,
                    border_radius=badge_height * 0.2,
                    fill_color=badge_layer_2_color,
                )
            ),
        )

        # 5. Layer badge with a variant label below it (the `variant`
        #    field in keyboard.layers). Layer 0 of the COLEMAK sample.
        #    Wrapped in the shared white card so the variant text reads
        #    cleanly even when the docs are viewed in dark mode.
        badge_layer_0_color = config.output.style.palette.layers[0].base_color
        variant_badge = LayerBadge(
            text="0 LETTERS",
            badge_width=300.0,
            badge_height=badge_height,
            border_radius=badge_height * 0.2,
            fill_color=badge_layer_0_color,
            variant="QWERTY",
            variant_color=badge_layer_0_color,
        )
        variant_card = Size(
            variant_badge.size.width + _CARD_PADDING,
            variant_badge.size.height + _CARD_PADDING,
        )
        yield (
            "badge-with-variant",
            _render_in_card(variant_badge, canvas=variant_card),
        )


BUILDERS: dict[str, OptionBuilder] = {
    "double-south": _build_double_south,
    "keyboard-layers": _build_keyboard_layers,
}


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    total = 0
    for option_name, builder in BUILDERS.items():
        option_dir = OUTPUT_ROOT / option_name
        option_dir.mkdir(parents=True, exist_ok=True)
        for variant, drawing in builder():
            target = option_dir / f"{variant}.svg"
            drawing.save_svg(str(target))
            size_kb = target.stat().st_size // 1024
            print(f"  {target.relative_to(ROOT)} ({size_kb} KB)")
            total += 1
    print(f"Wrote {total} option image(s) to {OUTPUT_ROOT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
