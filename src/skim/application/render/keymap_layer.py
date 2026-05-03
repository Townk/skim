# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Per-layer keymap composables.

Mirrors the special-keys document pattern from
:mod:`keymap_document`:

* :func:`KeymapLayer` — the keyboard area (two
  :func:`KeyboardHalf` instances + indicator chrome). Reports a
  bbox covering the halves plus any horizontal / top indicator
  overflow so the parent column / document allocates the right
  amount of space.
* :func:`KeymapLayerDocument` — the full per-layer image. Stacks
  :func:`Header`, :func:`KeymapLayer`, the optional macro / TD
  legend (re-using the same :func:`MacroSection` /
  :func:`TapDanceSection` composables the standalone special-keys
  image uses), the optional symbol legend (:func:`SymbolSection`),
  and an optional :func:`Footer` in a :class:`Column`, then wraps
  the whole thing in :func:`KeymapDocument` for the rounded
  border.
"""

from __future__ import annotations

from skim.data import (
    KeycodeMappings,
    SvalboardKeymap,
    SvalboardLayout,
)
from skim.domain import (
    KeyboardSide,
    SvalboardMacro,
    SvalboardTapDance,
    SvalboardTargetKey,
)

from .composable import Composable
from .footer import Footer
from .header import Header
from .keymap_document import KeymapDocument
from .legend import (
    collect_used_ids,
    resolve_macros,
    resolve_tap_dances,
)
from .macros import MacroSection
from .primitives import Column, Point, Row, Size
from .svalboard_halves import KeyboardHalf
from .symbol_legend import collect_used_descriptions
from .symbols import FlowDirection, SymbolSection
from .tap_dance import TapDanceSection

# The legacy ``KeymapLayoutMetrics`` keeps the central gap between
# the two halves at exactly ``2 * inset``; same constant lives here
# so :func:`KeymapLayer` doesn't have to import the legacy layout
# helpers.
_CENTER_GAP_INSET_COUNT = 2.0


# ---------------------------------------------------------------------------
# KeymapLayer — the keyboard area
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def KeymapLayer(
    ctx,
    *,
    layer: SvalboardLayout[SvalboardTargetKey],
    qmk_index: int,
    target_content_w: float,
):
    """Two :func:`KeyboardHalf` instances + indicator chrome.

    ``target_content_w`` is the column-allocated content width
    (typically ``doc_width - 2 * content_offset``). The halves
    split the budget — ``side_width = (target_content_w -
    center_gap) / 2`` — and the layer's reported width grows by
    ``2 * horizontal_chrome`` when inward indicators (nail /
    knuckle layer-switches) bleed past the keys-only edges. The
    height grows by the maximum of the two halves' top
    overflows so above-cluster indicators stay on-canvas.

    Mirrors the legacy ``_draw_layer`` half-positioning math: the
    left half stays flush-left in the keymap area; the right half
    shifts right by ``2 * horizontal_chrome``. The asymmetry was
    already in the legacy and is preserved verbatim.
    """
    config = ctx.config
    metrics = ctx.document_metrics

    content_offset = metrics.margin + metrics.border_width + metrics.inset
    _ = content_offset  # documented at the call site; the calc lives in KeymapLayerDocument
    center_gap = _CENTER_GAP_INSET_COUNT * metrics.inset
    side_width = (target_content_w - center_gap) / 2.0

    common_kwargs = {
        "min_width": side_width,
        "layer_qmk_index": qmk_index,
        "has_double_south": config.keyboard.features.double_south,
        "use_layer_colors_on_keys": config.output.style.use_layer_colors_on_keys,
        "show_layer_indicators": config.output.style.show_layer_indicators,
        "hold_symbol_position": config.output.style.hold_symbol_position,
    }

    left_half = KeyboardHalf(
        side=KeyboardSide.LEFT,
        fingers=layer.left.fingers,
        thumb=layer.left.thumb,
        **common_kwargs,
    )
    right_half = KeyboardHalf(
        side=KeyboardSide.RIGHT,
        fingers=layer.right.fingers,
        thumb=layer.right.thumb,
        **common_kwargs,
    )

    # Top chrome — the larger of the two halves' top overflows
    # (north-facing indicators above middle / ring clusters).
    top_chrome = max(
        left_half.metrics.overflow_offset.y,
        right_half.metrics.overflow_offset.y,
    )

    # Horizontal chrome — inward bleed (right edge of left half /
    # left edge of right half) widens the centre gap and pushes
    # the right half outward, mirroring the legacy
    # ``horizontal_indicator_offset`` policy.
    left_inward = max(
        0.0,
        left_half.metrics.overflow_size.width
        - left_half.size.width
        - left_half.metrics.overflow_offset.x,
    )
    right_inward = right_half.metrics.overflow_offset.x
    horizontal_chrome = max(left_inward, right_inward)

    half_height = max(left_half.size.height, right_half.size.height)
    size = Size(
        2 * side_width + center_gap + 2 * horizontal_chrome,
        top_chrome + half_height,
    )

    left_half_origin = Point(0.0, top_chrome)
    right_half_origin = Point(
        side_width + center_gap + 2 * horizontal_chrome,
        top_chrome,
    )

    def draw_at(d, origin):
        left_half.draw_at(
            d,
            Point(origin.x + left_half_origin.x, origin.y + left_half_origin.y),
        )
        right_half.draw_at(
            d,
            Point(origin.x + right_half_origin.x, origin.y + right_half_origin.y),
        )

    return size, draw_at


# ---------------------------------------------------------------------------
# KeymapLayerDocument — the full per-layer image
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def KeymapLayerDocument(
    ctx,
    *,
    layer: SvalboardLayout[SvalboardTargetKey],
    qmk_index: int,
    title: str,
    copyright: str | None = None,
    macros: tuple[SvalboardMacro[SvalboardTargetKey], ...] = (),
    tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...] = (),
    raw_layer_keycodes: list[str] | None = None,
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
):
    """The full per-layer keymap image as a single composable.

    Stacks :func:`Header`, :func:`KeymapLayer`, the optional
    macro / TD legend (:func:`MacroSection` next to
    :func:`TapDanceSection` in a :class:`Row` when both have
    content; whichever is non-empty alone otherwise), the optional
    symbol legend (:func:`SymbolSection`), and an optional
    :func:`Footer` in a :class:`Column`, then wraps in
    :func:`KeymapDocument` for the rounded background border +
    content_offset chrome.

    A falsy ``copyright`` (``None`` or ``""``) suppresses the
    footer. Macro / TD legend appears only when the style flag
    ``show_special_keys_legend`` is on AND the layer references
    at least one macro or tap-dance. Symbol legend appears only
    when ``show_symbol_legend`` is on AND
    ``raw_layer_keycodes`` + ``keycode_mappings`` are provided
    AND the layer has resolvable symbols.
    """
    config = ctx.config
    metrics = ctx.document_metrics
    content_offset = metrics.margin + metrics.border_width + metrics.inset
    doc_content_w = metrics.doc_width - 2 * content_offset

    # Build the keyboard area first — its actual width may exceed the
    # configured ``doc_content_w`` when inward indicators bleed past
    # the keys-only edges and the column has to grow. Every other
    # child of the column (header / sections / footer) sizes against
    # the keyboard area's width so they fill the column edge-to-edge
    # rather than being left-aligned with a gap on the right.
    keymap_layer = KeymapLayer(
        layer=layer,
        qmk_index=qmk_index,
        target_content_w=doc_content_w,
    )
    content_w = keymap_layer.size.width

    macro_entries: list = []
    td_entries: list = []
    if config.output.style.show_special_keys_legend:
        used_macro_ids, used_td_ids = collect_used_ids(layer)
        macro_entries = resolve_macros(used_macro_ids, macros)
        td_entries = resolve_tap_dances(used_td_ids, tap_dances)

    # Macro / TD section width split — same policy as
    # :func:`KeymapSpecialKeysDocument`. Half the content width
    # each when both have content; the full content width when
    # only one section is present.
    col_gap = metrics.column_gap
    col_w = (content_w - col_gap) / 2 if macro_entries and td_entries else content_w
    macro_section = (
        MacroSection(macros=macro_entries, content_width=col_w) if macro_entries else None
    )
    td_section = TapDanceSection(tap_dances=td_entries, max_width=col_w) if td_entries else None

    symbol_section = None
    if config.output.style.show_symbol_legend and raw_layer_keycodes and keycode_mappings:
        symbol_entries = collect_used_descriptions(
            raw_layer_keycodes,
            raw_keymap,
            keycode_mappings,
            include_transparent=not config.output.style.show_transparent_fallthrough,
        )
        if symbol_entries:
            flow_value = config.output.style.symbol_legend_flow.value
            typed_flow: FlowDirection = "row" if flow_value == "row" else "column"
            symbol_section = SymbolSection(
                entries=symbol_entries,
                max_width=content_w,
                column_count=config.output.style.symbol_legend_columns,
                flow=typed_flow,
            )

    with Column(gap=metrics.inset, align="start") as content:
        Header(
            title=title,
            min_gap=2 * metrics.inset,
            max_width=content_w,
        )
        content.add(keymap_layer)
        if macro_section and td_section:
            Row([macro_section, td_section], gap=col_gap, align="top")
        elif macro_section:
            content.add(macro_section)
        elif td_section:
            content.add(td_section)
        if symbol_section is not None:
            content.add(symbol_section)
        if copyright:
            Footer(text=copyright, max_width=content_w)

    return KeymapDocument(content=content)


__all__ = [
    "KeymapLayer",
    "KeymapLayerDocument",
]
