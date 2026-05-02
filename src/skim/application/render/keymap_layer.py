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
  legend, the optional symbol legend, and an optional
  :func:`Footer` in a :class:`Column`, then wraps the whole
  thing in :func:`KeymapDocument` for the rounded border.

The macro / TD legend and the symbol legend currently delegate
to the legacy painters (``build_legend`` /
``build_symbol_legend``) via small adapter composables — the
combined macro+TD legend layout the per-layer image uses isn't
yet expressed as composables. Replacing those adapters with
proper composables can come later without touching the document
shape.
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
    LegendLayout,
    build_legend,
    collect_used_ids,
    legend_height,
    plan_layout,
    resolve_macros,
    resolve_tap_dances,
)
from .primitives import Column, Point, Size, Spacer
from .svalboard_halves import KeyboardHalf
from .symbol_legend import (
    SymbolLegendEntry,
    build_symbol_legend,
    collect_used_descriptions,
    symbol_legend_height,
)

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
# Legend adapters — wrap the legacy painters in a composable shell so they
# slot into the document's column layout. Replaced with proper composables
# when the legend rendering migrates.
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def _LayerMacroTapDanceLegend(
    ctx,
    *,
    layout: LegendLayout | None,
    content_width: float,
):
    """Wrap the legacy combined macro / tap-dance legend painter."""
    if layout is None:
        return Spacer()

    palette = ctx.config.output.style.palette
    use_system_fonts = ctx.config.output.style.use_system_fonts
    doc_width = ctx.document_metrics.doc_width

    height = legend_height(layout, content_width, doc_width=doc_width)
    if height <= 0:
        return Spacer()
    size = Size(content_width, height)

    def draw_at(d, origin):
        group = build_legend(
            layout=layout,
            x=origin.x,
            y=origin.y,
            content_width=content_width,
            palette=palette,
            use_system_fonts=use_system_fonts,
            doc_width=doc_width,
        )
        if group is not None:
            d.append(group)

    return size, draw_at


@Composable(use_context=True)
def _LayerSymbolLegend(
    ctx,
    *,
    entries: list[SymbolLegendEntry],
    content_width: float,
):
    """Wrap the legacy per-layer symbol legend painter."""
    if not entries:
        return Spacer()

    palette = ctx.config.output.style.palette
    use_system_fonts = ctx.config.output.style.use_system_fonts
    doc_width = ctx.document_metrics.doc_width
    flow = ctx.config.output.style.symbol_legend_flow.value

    height = symbol_legend_height(entries, content_width, doc_width=doc_width)
    if height <= 0:
        return Spacer()
    size = Size(content_width, height)

    def draw_at(d, origin):
        group = build_symbol_legend(
            entries=entries,
            x=origin.x,
            y=origin.y,
            content_width=content_width,
            palette=palette,
            use_system_fonts=use_system_fonts,
            flow=flow,
            doc_width=doc_width,
        )
        if group is not None:
            d.append(group)

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
    macro / TD legend, the optional symbol legend, and an
    optional :func:`Footer` in a :class:`Column` (gap =
    ``inset``), then wraps in :func:`KeymapDocument` for the
    rounded background border + content_offset chrome.

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
    target_content_w = metrics.doc_width - 2 * content_offset

    keymap_layer = KeymapLayer(
        layer=layer,
        qmk_index=qmk_index,
        target_content_w=target_content_w,
    )

    legend_plan: LegendLayout | None = None
    if config.output.style.show_special_keys_legend:
        used_macro_ids, used_td_ids = collect_used_ids(layer)
        macro_entries = resolve_macros(used_macro_ids, macros)
        td_entries = resolve_tap_dances(used_td_ids, tap_dances)
        legend_plan = plan_layout(macro_entries, td_entries)

    symbol_entries: list[SymbolLegendEntry] = []
    if config.output.style.show_symbol_legend and raw_layer_keycodes and keycode_mappings:
        symbol_entries = collect_used_descriptions(
            raw_layer_keycodes,
            raw_keymap,
            keycode_mappings,
            include_transparent=not config.output.style.show_transparent_fallthrough,
        )

    macro_legend = _LayerMacroTapDanceLegend(
        layout=legend_plan,
        content_width=target_content_w,
    )
    sym_legend = _LayerSymbolLegend(
        entries=symbol_entries,
        content_width=target_content_w,
    )

    with Column(gap=metrics.inset, align="start") as content:
        Header(
            title=title,
            min_gap=2 * metrics.inset,
            max_width=target_content_w,
        )
        content.add(keymap_layer)
        content.add(macro_legend)
        content.add(sym_legend)
        if copyright:
            Footer(text=copyright, max_width=target_content_w)

    return KeymapDocument(content=content)


__all__ = [
    "KeymapLayer",
    "KeymapLayerDocument",
]
