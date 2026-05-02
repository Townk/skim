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
from skim.domain import KeyboardSide, SvalboardMacro, SvalboardTapDance, SvalboardTargetKey

from .footer import append_footer, footer_layout_height
from .header import append_header, header_layout_height
from .layout import KeymapLayout
from .legend import (
    build_legend,
    collect_used_ids,
    legend_height,
    plan_layout,
    resolve_macros,
    resolve_tap_dances,
)
from .macros import draw_macros_image
from .overview import HeaderDims, compute_header_dims, draw_overview
from .primitives import Point as ComposablePoint
from .render_context import RenderContext as ComposableRenderContext, using_render_context
from .special_keys import draw_special_keys_image
from .styling import make_gradient
from .svalboard_halves import KeyboardHalf
from .symbol_legend import (
    build_symbol_legend,
    collect_used_descriptions,
    symbol_legend_height,
)
from .symbols import collect_symbol_entries, draw_symbols_image
from .tap_dance import draw_tap_dances_image
from .text import Font, FontSubsetter, FontUsageAnalyzer, Label

logger = logging.getLogger(__name__)

# Vertical gap between the macro/TD legend block and the symbol legend block,
# expressed as a fraction of the document width.
_SYMBOL_LEGEND_GAP_RATIO = 24 / 1600


def _draw_layer(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    layer: SvalboardLayout[SvalboardTargetKey],
    config_position: int,
    qmk_index: int,
    header_dims: HeaderDims,
    macros: tuple[SvalboardMacro[SvalboardTargetKey], ...] = (),
    tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...] = (),
    raw_layer_keycodes: list[str] | None = None,
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
) -> draw.Drawing:
    use_system_fonts = config.output.style.use_system_fonts
    layer_layout = KeymapLayout(config)
    m = layer_layout.metrics

    # Layer title — needed both as the header text and as input to the
    # header's "shrink-to-fit" sizing (the logo height matches the title's
    # rendered glyph bbox, so the body offset depends on the title text).
    layer_title = (
        f"Layer {qmk_index}"
        if config_position >= len(config.keyboard.layers)
        else config.keyboard.layers[config_position].name
    )
    if "layer" not in layer_title.lower():
        layer_title += " Layer"

    # Header strip (title + logo) sits at the top of the canvas. Sizes, outer
    # padding, and the gap below the header all come from the overview (see
    # compute_header_dims) so typography and spacing match it verbatim. The
    # header component sizes the logo to the title's rendered bbox, so the
    # natural header height is just the title's bbox at ``title_font_size``.
    title_font_size = header_dims.title_font_size
    outer_padding = header_dims.outer_padding
    gap_below_header = header_dims.gap_below_header
    header_height = header_layout_height(layer_title, title_font_size)
    # The cluster top is conventionally at margin + inset + top_indicator_offset.
    # We want it at outer_padding + header_height + gap_below_header, so add the
    # difference as header_offset.
    header_offset = outer_padding - m.margin - m.inset + header_height + gap_below_header

    common_half_kwargs = {
        "min_width": m.side_width,
        "layer_qmk_index": qmk_index,
        "has_double_south": config.keyboard.features.double_south,
        "use_layer_colors_on_keys": config.output.style.use_layer_colors_on_keys,
        "show_layer_indicators": config.output.style.show_layer_indicators,
        "hold_symbol_position": config.output.style.hold_symbol_position,
    }

    composable_ctx = ComposableRenderContext.build(config, keymap)
    with using_render_context(composable_ctx):
        left_half = KeyboardHalf(
            side=KeyboardSide.LEFT,
            fingers=layer.left.fingers,
            thumb=layer.left.thumb,
            **common_half_kwargs,
        )
        right_half = KeyboardHalf(
            side=KeyboardSide.RIGHT,
            fingers=layer.right.fingers,
            thumb=layer.right.thumb,
            **common_half_kwargs,
        )

    # Canvas chrome — read the halves' overflow metrics. Each half's
    # ``overflow_offset`` measures how far its overflow bbox extends
    # PAST its keys-only ``(0, 0)`` (i.e., above and left of the
    # half's top-left); ``overflow_size - size - overflow_offset``
    # measures how far past the bottom-right. We aggregate across
    # both halves to size the canvas.
    top_indicator_offset = max(
        left_half.metrics.overflow_offset.y,
        right_half.metrics.overflow_offset.y,
    )
    # Inward bleed — left half's RIGHT edge, right half's LEFT edge.
    # When inward indicators (nail / knuckle) bleed past the keys-only
    # bbox, halves push apart so the centre gap stays clear. Mirroring
    # the legacy growth pattern: canvas grows by ``2 * offset`` on the
    # right and the right half shifts right by the same amount, which
    # leaves the keyboard area centred on the (now wider) canvas.
    left_inward = max(
        0.0,
        left_half.metrics.overflow_size.width
        - left_half.size.width
        - left_half.metrics.overflow_offset.x,
    )
    right_inward = right_half.metrics.overflow_offset.x
    horizontal_indicator_offset = max(left_inward, right_inward)

    half_origin_y = m.margin + m.inset + header_offset + top_indicator_offset
    left_half_origin = ComposablePoint(m.margin + m.inset, half_origin_y)
    right_half_origin_x = (
        m.width - (m.margin + m.inset) - m.side_width + 2 * horizontal_indicator_offset
    )
    right_half_origin = ComposablePoint(right_half_origin_x, half_origin_y)

    canvas_width = layer_layout.canvas_width(
        horizontal_indicator_offset=horizontal_indicator_offset
    )
    # Keyboard-area height — the half is positioned at ``half_origin_y``
    # and its size already covers fingers + thumb (the thumb's top
    # overflow is absorbed into the inset gap inside KeyboardHalf). Add
    # a one-inset + margin band below the half to mirror the top
    # spacing.
    keyboard_canvas_h = half_origin_y + left_half.size.height + m.inset + m.margin
    bottom_inset = m.inset + m.margin
    copyright_font_size = header_dims.copyright_font_size
    copyright_text = config.output.copyright or ""
    copyright_h = footer_layout_height(copyright_text, copyright_font_size)
    copyright_extra = copyright_h + bottom_inset if copyright_text else 0.0

    # Plan the macro/TD legend and reserve its vertical space.
    if config.output.style.show_special_keys_legend:
        used_macro_ids, used_td_ids = collect_used_ids(layer)
        macro_entries = resolve_macros(used_macro_ids, macros)
        td_entries = resolve_tap_dances(used_td_ids, tap_dances)
        legend_plan = plan_layout(macro_entries, td_entries)
    else:
        legend_plan = None

    # Plan the symbol legend.
    if config.output.style.show_symbol_legend and raw_layer_keycodes and keycode_mappings:
        symbol_entries = collect_used_descriptions(
            raw_layer_keycodes,
            raw_keymap,
            keycode_mappings,
            include_transparent=not config.output.style.show_transparent_fallthrough,
        )
    else:
        symbol_entries = []

    symbol_legend_gap = m.width * _SYMBOL_LEGEND_GAP_RATIO
    content_width = canvas_width - 2 * outer_padding
    legend_h = legend_height(legend_plan, content_width, doc_width=m.width)
    sym_h = symbol_legend_height(symbol_entries, content_width, doc_width=m.width)

    if legend_h > 0 and sym_h > 0:
        legend_block_h = legend_h + symbol_legend_gap + sym_h
    elif legend_h > 0:
        legend_block_h = legend_h
    else:
        legend_block_h = sym_h

    # Symmetric spacing: the legend block sits at the natural bottom edge of
    # the keyboard area (reusing the existing bottom inset above the legend),
    # with a matching ``bottom_inset`` gap below before the copyright footer.
    legend_top = keyboard_canvas_h if legend_block_h > 0 else None

    canvas_height = keyboard_canvas_h
    if legend_block_h > 0:
        canvas_height += legend_block_h + bottom_inset
    canvas_height += copyright_extra

    # The natural canvas may grow past the user-requested width — horizontal
    # indicator offsets push the right edge out beyond ``m.width``. Honour the
    # user's request by setting the SVG's ``width`` to the configured value
    # and scaling the height proportionally; the natural coordinates stay in
    # ``viewBox`` so the layout itself is untouched.
    display_w = m.width
    display_h = canvas_height * (display_w / canvas_width) if canvas_width else canvas_height
    d = draw.Drawing(display_w, display_h, viewBox=f"0 0 {canvas_width} {canvas_height}")

    def _finger_label(key: SvalboardTargetKey | None) -> Label | None:
        return Label(key.label, Font.FINGER_KEY, text_color="#000") if key and key.label else None

    def _thumb_label(key: SvalboardTargetKey | None) -> Label | None:
        return Label(key.label, Font.THUMB_KEY, text_color="#000") if key and key.label else None

    labels_keymap: SvalboardLayout[Label | None] = SvalboardLayout(
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

    # Paint the keyboard area — one :func:`KeyboardHalf` per side. The
    # halves were built inside ``using_render_context`` above; their
    # ``draw_at`` closures already captured everything they need from
    # the context, so the paint calls don't need to re-enter it.
    left_half.draw_at(d, left_half_origin)
    right_half.draw_at(d, right_half_origin)

    append_header(
        d,
        canvas_w=canvas_width,
        padding=outer_padding,
        title_text=layer_title,
        title_color=config.output.style.palette.text_color,
        title_font_max_size=title_font_size,
        use_system_fonts=use_system_fonts,
    )

    if copyright_text:
        append_footer(
            d,
            canvas_w=canvas_width,
            canvas_h=canvas_height,
            padding=outer_padding,
            bottom_inset=bottom_inset,
            text=copyright_text,
            text_color=config.output.style.palette.text_color,
            font_max_size=copyright_font_size,
            use_system_fonts=use_system_fonts,
        )

    if legend_plan is not None and legend_top is not None:
        legend_group = build_legend(
            layout=legend_plan,
            x=outer_padding,
            y=legend_top,
            content_width=content_width,
            palette=config.output.style.palette,
            use_system_fonts=use_system_fonts,
            doc_width=m.width,
        )
        if legend_group is not None:
            d.append(legend_group)

    # Symbol legend — placed after the macro/TD legend (or directly after
    # the keyboard when there's no macro/TD legend).
    if symbol_entries and legend_top is not None:
        sym_legend_y = legend_top + legend_h + symbol_legend_gap if legend_h > 0 else legend_top
        sym_group = build_symbol_legend(
            entries=symbol_entries,
            x=outer_padding,
            y=sym_legend_y,
            content_width=content_width,
            palette=config.output.style.palette,
            use_system_fonts=use_system_fonts,
            flow=config.output.style.symbol_legend_flow.value,
            doc_width=m.width,
        )
        if sym_group is not None:
            d.append(sym_group)

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
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
) -> dict[str, draw.Drawing]:
    keymap_images: dict[str, draw.Drawing] = {}
    header_dims = compute_header_dims(config, keymap)
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
            header_dims,
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
