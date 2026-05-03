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

import logging

import drawsvg as draw

from skim.data import (
    KeycodeMappings,
    KeymapGeneratorTargets,
    SkimConfig,
    SplitSide,
    SvalboardKeymap,
    SvalboardLayout,
)
from skim.domain import SvalboardMacro, SvalboardTapDance, SvalboardTargetKey

from .composable import render
from .keymap_layer import KeymapLayerDocument
from .keymap_overview import draw_overview
from .macros import draw_macros_image
from .render_context import RenderContext as ComposableRenderContext, using_render_context
from .special_keys import draw_special_keys_image
from .styling import make_gradient
from .symbols import collect_symbol_entries, draw_symbols_image
from .tap_dance import draw_tap_dances_image
from .text import Font, FontSubsetter, FontUsageAnalyzer, Label

logger = logging.getLogger(__name__)


def _layer_title(config: SkimConfig, config_position: int, qmk_index: int) -> str:
    """Resolve the layer's display title.

    Combines the configured layer ``name`` and ``variant`` into the
    header string the per-layer image paints. Four cases:

    * Both name and variant: ``"{name} ({variant}) Layer"``.
    * Name only: ``"{name} Layer"`` (with the trailing ``"Layer"``
      omitted when the name already contains the word).
    * Variant only: ``"Layer {qmk_index} ({variant})"``.
    * Neither: ``"Layer {qmk_index}"``.

    Falls through to the variant-only / neither cases when
    ``config_position`` is past the end of the configured layer
    list.
    """
    layer_cfg = (
        config.keyboard.layers[config_position]
        if config_position < len(config.keyboard.layers)
        else None
    )
    name = layer_cfg.name if layer_cfg is not None else None
    variant = layer_cfg.variant if layer_cfg is not None else None

    if name and variant:
        title = f"{name} ({variant})"
    elif name:
        title = name
    elif variant:
        return f"Layer {qmk_index} ({variant})"
    else:
        return f"Layer {qmk_index}"

    if "layer" not in title.lower():
        title += " Layer"
    return title


def _layer_labels(
    layer: SvalboardLayout[SvalboardTargetKey],
) -> SvalboardLayout[Label | None]:
    """Build the ``Label`` layout used by the font-subset analyser.

    Finger keys use :data:`Font.FINGER_KEY` and thumb keys use
    :data:`Font.THUMB_KEY` so the analyser charges glyphs to the
    right per-font character set.
    """

    def _finger_label(key: SvalboardTargetKey | None) -> Label | None:
        return Label(key.label, Font.FINGER_KEY, text_color="#000") if key and key.label else None

    def _thumb_label(key: SvalboardTargetKey | None) -> Label | None:
        return Label(key.label, Font.THUMB_KEY, text_color="#000") if key and key.label else None

    return SvalboardLayout(
        left=SplitSide(
            index=layer.left.fingers[0].map(_finger_label),
            middle=layer.left.fingers[1].map(_finger_label),
            ring=layer.left.fingers[2].map(_finger_label),
            pinky=layer.left.fingers[3].map(_finger_label),
            thumb=layer.left.thumb.map(_thumb_label),
        ),
        right=SplitSide(
            index=layer.right.fingers[0].map(_finger_label),
            middle=layer.right.fingers[1].map(_finger_label),
            ring=layer.right.fingers[2].map(_finger_label),
            pinky=layer.right.fingers[3].map(_finger_label),
            thumb=layer.right.thumb.map(_thumb_label),
        ),
    )


def _layer_subset_css(
    layer: SvalboardLayout[SvalboardTargetKey],
    layer_title: str,
    copyright: str | None,
    macros: tuple[SvalboardMacro[SvalboardTargetKey], ...],
    tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...],
) -> list[str]:
    """Build font-subset CSS for one per-layer image.

    Walks the layer's labels (plus title / copyright / macros /
    tap-dances) and emits a tightly-subsetted CSS embedding only
    the glyphs the layer actually paints. Falls back to the full
    fonts CSS if the analyser produces an empty subset.
    """
    font_analyzer = FontUsageAnalyzer()
    font_analyzer.analyze_keymap(_layer_labels(layer), layer_title, copyright)
    font_analyzer.analyze_legend(macros, tap_dances)
    font_subsetter = FontSubsetter(font_analyzer)
    subsetted = font_subsetter.generate_subsetted_css()
    return [subsetted] if subsetted else [font_subsetter.generate_full_fonts_css()]


def _draw_layer(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    layer: SvalboardLayout[SvalboardTargetKey],
    config_position: int,
    qmk_index: int,
    macros: tuple[SvalboardMacro[SvalboardTargetKey], ...] = (),
    tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...] = (),
    raw_layer_keycodes: list[str] | None = None,
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
) -> draw.Drawing:
    """Build a per-layer image as a :class:`KeymapLayerDocument`.

    The composable encodes the entire layout (header, keyboard area,
    optional macro / TD legend, optional symbol legend, optional
    footer); this function only handles the entry-point bookkeeping
    — building the :class:`RenderContext`, computing per-layer
    font-subset CSS, and handing the document to :func:`render`.
    """
    layer_title = _layer_title(config, config_position, qmk_index)
    copyright_text = config.output.copyright or ""

    css = (
        _layer_subset_css(layer, layer_title, config.output.copyright, macros, tap_dances)
        if not config.output.style.use_system_fonts
        else None
    )

    with using_render_context(ComposableRenderContext.build(config, keymap)):
        return render(
            KeymapLayerDocument(
                layer=layer,
                qmk_index=qmk_index,
                title=layer_title,
                copyright=copyright_text,
                macros=macros,
                tap_dances=tap_dances,
                raw_layer_keycodes=raw_layer_keycodes,
                raw_keymap=raw_keymap,
                keycode_mappings=keycode_mappings,
            ),
            css=css,
        )


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
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
) -> dict[str, draw.Drawing]:
    keymap_images: dict[str, draw.Drawing] = {}
    for qmk_idx, pos, layer in _selected_layers(keymap, targets, config):
        # Flatten the raw keycodes for this layer (if available)
        raw_layer_keycodes: list[str] | None = None
        if raw_keymap is not None and qmk_idx in raw_keymap.layers:
            raw_layer = raw_keymap.layers[qmk_idx]
            raw_layer_keycodes = [k for k in raw_layer if k is not None]
        keymap_images[f"keymap-layer-{qmk_idx}"] = _draw_layer(
            config,
            keymap,
            layer,
            pos,
            qmk_idx,
            macros=keymap.macros,
            tap_dances=keymap.tap_dances,
            raw_layer_keycodes=raw_layer_keycodes,
            raw_keymap=raw_keymap,
            keycode_mappings=keycode_mappings,
        )

    if targets.overview:
        keymap_images["keymap-overview"] = draw_overview(
            config,
            keymap,
            raw_keymap=raw_keymap,
            keycode_mappings=keycode_mappings,
        )

    has_macros = bool(keymap.macros)
    has_tap_dances = bool(keymap.tap_dances)

    if targets.macros:
        if has_macros:
            keymap_images["keymap-macros"] = draw_macros_image(config, keymap)
        else:
            logger.warning("Skipping macros image: no macros are defined in the keymap.")

    if targets.tap_dances:
        if has_tap_dances:
            keymap_images["keymap-tap-dances"] = draw_tap_dances_image(config, keymap)
        else:
            logger.warning("Skipping tap-dances image: no tap-dances are defined in the keymap.")

    if targets.special_keys:
        if has_macros or has_tap_dances:
            keymap_images["keymap-special-keys"] = draw_special_keys_image(config, keymap)
        else:
            logger.warning(
                "Skipping special-keys image: no macros nor tap-dances are defined in the keymap."
            )

    if targets.symbols:
        if raw_keymap is None or keycode_mappings is None:
            logger.warning("Skipping symbols image: keycode mappings are not available.")
        else:
            symbol_entries = collect_symbol_entries(config, raw_keymap, keycode_mappings)
            if symbol_entries:
                keymap_images["keymap-symbols"] = draw_symbols_image(config, keymap, symbol_entries)
            else:
                logger.warning("Skipping symbols image: no resolvable symbols found in the keymap.")

    # If the only thing the user asked for were special-key images and the
    # keymap has neither macros nor tap-dances, surface a single overall
    # warning so the message lands even when individual per-image warnings
    # blur together.
    only_special_keys_requested = (
        not targets.selected_layers
        and not targets.all_layers
        and not targets.overview
        and (targets.macros or targets.tap_dances or targets.special_keys)
    )
    if only_special_keys_requested and not keymap_images:
        logger.warning(
            "No macros nor tap-dances are defined in the keymap; no images will be created."
        )

    return keymap_images


__all__ = [
    "draw_keymap",
    "make_gradient",
]
