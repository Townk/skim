# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Rendering module for generating keymap visualizations.

This package owns every image entry point — the ``draw_*`` functions
that take a config + keymap and return a ``drawsvg.Drawing``. Each
one builds a :class:`RenderContext`, constructs the corresponding
document composable inside it, and hands the result to
:func:`render`. Composable modules (``keymap_layer.py``,
``keymap_overview.py``, ``macros.py``, ``tap_dance.py``,
``symbols.py``, etc.) own only the composables themselves; the
entry-point shims live here.

Public surface:

* :func:`draw_keymap` — top-level orchestrator. Picks which images
  to render based on :class:`KeymapGeneratorTargets` and dispatches
  to the per-image entry points below.
* :func:`draw_overview` — multi-layer overview image.
* :func:`draw_macros_image` — standalone macros image.
* :func:`draw_tap_dances_image` — standalone tap-dances image.
* :func:`draw_special_keys_image` — combined macros + tap-dances.
* :func:`draw_symbols_image` — standalone symbols image (caller
  pre-collects entries via :func:`collect_symbol_entries`).
"""

import logging

import drawsvg as draw

from skim.data import (
    KeycodeMappings,
    KeymapGeneratorTargets,
    SkimConfig,
    SvalboardKeymap,
    SvalboardLayout,
)
from skim.domain import SvalboardMacro, SvalboardTapDance, SvalboardTargetKey

from .composable import render
from .keymap_document import (
    KeymapLayerDocument,
    KeymapMacroDocument,
    KeymapOverviewDocument,
    KeymapSpecialKeysDocument,
    KeymapSymbolDocument,
    KeymapTapDanceDocument,
)
from .render_context import RenderContext, using_render_context
from .section_data import (
    all_macros,
    all_tap_dances,
    collect_used_ids,
    resolve_macros,
    resolve_tap_dances,
)
from .styling import make_gradient
from .symbols import FlowDirection, SymbolLegendEntry, collect_symbol_entries

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Title resolvers
# ---------------------------------------------------------------------------


def _resolve_image_title(config: SkimConfig) -> str:
    """Pick the keymap title for the standalone images.

    Falls back to ``"{first layer's variant or name} Layers Layout"``
    when ``output.keymap_title`` isn't configured, and to the literal
    ``"Keymap Layout"`` when there are no configured layers. Shared
    by macros / tap-dances / special-keys / symbols entry points so
    every standalone image carries the same title text.
    """
    if config.output.keymap_title:
        return config.output.keymap_title
    if config.keyboard.layers:
        first = config.keyboard.layers[0]
        return f"{first.variant or first.name} Layers Layout"
    return "Keymap Layout"


def _layer_title(config: SkimConfig, config_position: int, qmk_index: int) -> str:
    """Resolve the per-layer image's display title.

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


# ---------------------------------------------------------------------------
# Per-image entry points
# ---------------------------------------------------------------------------


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
    """Render one layer's keymap image.

    Resolves the macro / TD legend's contents up-front (the layer's
    used ids → filtered + sorted lists) so the document composable
    receives ready-to-paint data rather than reaching into the
    keymap itself. Then builds a :class:`RenderContext` and hands
    the document to :func:`render`. Embedded-font subsetting is
    automatic — :class:`FontUsageCollector` activates inside
    :func:`using_render_context` and every :func:`AdjustableText`
    registers its painted characters there during construction.
    """
    if config.output.style.show_special_keys_legend:
        used_macro_ids, used_td_ids = collect_used_ids(layer)
        layer_macros = resolve_macros(used_macro_ids, macros)
        layer_tap_dances = resolve_tap_dances(used_td_ids, tap_dances)
    else:
        layer_macros = []
        layer_tap_dances = []
    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapLayerDocument(
                layer=layer,
                qmk_index=qmk_index,
                title=_layer_title(config, config_position, qmk_index),
                copyright=config.output.copyright or "",
                macros=layer_macros,
                tap_dances=layer_tap_dances,
                raw_layer_keycodes=raw_layer_keycodes,
                raw_keymap=raw_keymap,
                keycode_mappings=keycode_mappings,
            )
        )


def draw_overview(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
) -> draw.Drawing:
    """Render the multi-layer overview image.

    Resolves the macro / TD legend's contents up-front (the parsed
    keymap's full lists, sorted) so the document composable
    receives ready-to-paint data rather than reaching into the
    keymap itself.
    """
    if config.output.style.show_special_keys_legend:
        overview_macros = all_macros(keymap.macros)
        overview_tap_dances = all_tap_dances(keymap.tap_dances)
    else:
        overview_macros = []
        overview_tap_dances = []
    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapOverviewDocument(
                keymap=keymap,
                title=_resolve_image_title(config),
                copyright=config.output.copyright or "",
                macros=overview_macros,
                tap_dances=overview_tap_dances,
                raw_keymap=raw_keymap,
                keycode_mappings=keycode_mappings,
            )
        )


def draw_macros_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the standalone macros image.

    Body-scale is read from ``config.output.style.macros_scale`` (the
    CLI ``--macros-scale`` flag updates that field upstream). Body
    chips and pills scale by this factor; the chrome (title, footer,
    outer padding) stays at the unscaled per-image size.
    """
    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapMacroDocument(
                macros=all_macros(keymap.macros),
                title=_resolve_image_title(config),
                copyright=config.output.copyright,
                scale=config.output.style.macros_scale,
            )
        )


def draw_tap_dances_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the standalone tap-dances image.

    Body-scale is read from ``config.output.style.tap_dances_scale``
    (the CLI ``--tap-dances-scale`` flag updates that field upstream).
    """
    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapTapDanceDocument(
                tap_dances=all_tap_dances(keymap.tap_dances),
                title=_resolve_image_title(config),
                copyright=config.output.copyright,
                scale=config.output.style.tap_dances_scale,
            )
        )


def draw_special_keys_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the combined special-keys image (macros left, tap-dances right)."""
    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapSpecialKeysDocument(
                macros=all_macros(keymap.macros),
                tap_dances=all_tap_dances(keymap.tap_dances),
                title=_resolve_image_title(config),
                copyright=config.output.copyright,
            )
        )


def draw_symbols_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    entries: list[SymbolLegendEntry],
) -> draw.Drawing:
    """Render the standalone symbols image from a pre-collected entry set.

    Caller is expected to gate on ``entries`` being non-empty (and on
    ``raw_keymap`` / ``keycode_mappings`` availability) — this entry
    point doesn't surface "skipping" warnings of its own. Use
    :func:`collect_symbol_entries` to build the entry set in the
    caller's preferred order.

    Body-scale is read from ``config.output.style.symbols_scale``
    (the CLI ``--symbols-scale`` flag updates that field upstream).
    """
    flow_str = config.output.style.symbol_legend_flow
    flow: FlowDirection = "row" if flow_str == "row" else "column"

    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapSymbolDocument(
                entries=entries,
                title=_resolve_image_title(config),
                copyright=config.output.copyright,
                flow=flow,
                scale=config.output.style.symbols_scale,
            )
        )


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


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
    """Top-level dispatch: render every image the targets request.

    Returns a ``{filename_stem: Drawing}`` dict the caller writes to
    disk. Per-image gating logic (skip when there are no macros to
    render, etc.) lives here so the per-image entry points stay
    config → Drawing without ``None``-returning paths.
    """
    keymap_images: dict[str, draw.Drawing] = {}
    for qmk_idx, pos, layer in _selected_layers(keymap, targets, config):
        # Flatten the raw keycodes for this layer (if available) so the
        # per-layer document can collect symbol-legend entries from the
        # actual painted layer.
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
    "draw_macros_image",
    "draw_overview",
    "draw_special_keys_image",
    "draw_symbols_image",
    "draw_tap_dances_image",
    "make_gradient",
]
