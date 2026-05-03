# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Per-layer keymap composables.

Mirrors the special-keys document pattern from
:mod:`keymap_document`:

* :func:`KeymapLayer` — the keyboard area, built from four
  composables placed directly: left :func:`FingerHalf`, right
  :func:`FingerHalf`, left :func:`ThumbCluster`, right
  :func:`ThumbCluster`. Each component is positioned so its
  overflow rectangle lands fully inside the layer's bbox, so
  :func:`KeymapLayer` exposes no overflow itself.
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
from .svalboard_clusters import ThumbCluster
from .svalboard_halves import FingerHalf
from .symbol_legend import collect_used_descriptions
from .symbols import FlowDirection, SymbolSection
from .tap_dance import TapDanceSection

# Central gap between the two keyboard sides, in units of
# ``DocumentMetrics.inset``. Mirrors the legacy
# ``_CENTER_GAP_INSET_COUNT`` constant from ``layout.py`` so the
# central gap behaves identically without importing the legacy
# layout helper.
_CENTER_GAP_INSET_COUNT = 2.0

# Thumb cluster width as a proportion of one keyboard side's width.
# Mirrors the legacy ``_THUMB_CLUSTER_WIDTH_PROPORTION_PER_SIDE`` —
# the thumb sits inside the same horizontal extent as a finger half
# but is narrower so the inward edge of the half stays clear of
# the centre gap.
_THUMB_CLUSTER_WIDTH_PROPORTION = 0.42


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
    """Keyboard area: 4 components positioned so all chrome lives inside.

    Builds the four pieces directly — left + right
    :func:`FingerHalf`, left + right :func:`ThumbCluster` — and
    places each so its overflow rectangle lands fully INSIDE the
    layer's reported bbox. The layer therefore exposes no overflow
    itself: the parent column reads ``size`` and has no extra chrome
    to reserve.

    Placement rules (with the convention that
    ``overflow_offset.{x,y}`` is ``0`` on a side without chrome and
    NEGATIVE by the chrome magnitude on a side that has it):

    * Left fingers placed at ``x = -overflow_offset.x`` so their
      overflow's top-left corner lands at the layer's left edge
      (``x = 0``).
    * Right fingers placed at ``left_fingers_x + size.width +
      min_horizontal_gap + 2 * inward_bleed``, where
      ``inward_bleed`` is the larger of (left-side right-edge
      overflow, right-side left-edge overflow) across both fingers
      and thumbs. Both sides shift outward by the same amount so
      the central gap stays clear and the keyboard reads as
      symmetric.
    * Both finger halves share a top ``y = max top-edge bleed``,
      whichever half's top indicators reach higher above its
      keys-only origin.
    * Left thumb right-aligned with left fingers' keys-only right
      edge (inward side of the left half); right thumb left-aligned
      with right fingers' keys-only left edge (inward side of the
      right half).
    * Thumb top ``y`` sits at ``fingers_y + fingers.size.height +
      fingers_bottom_bleed + min_vertical_gap + thumbs_top_bleed``
      so the inset gap between fingers and thumb clears
      bottom-of-finger overflow (south_key indicators) AND
      top-of-thumb overflow (DD indicator) without overlap.

    The reported size is exactly the bbox of the rightmost finger
    overflow extent (horizontally) and the deepest thumb bottom
    overflow (vertically).
    """
    config = ctx.config
    metrics = ctx.document_metrics

    min_horizontal_gap = _CENTER_GAP_INSET_COUNT * metrics.inset
    min_vertical_gap = metrics.inset

    side_width = (target_content_w - min_horizontal_gap) / 2.0
    thumb_cluster_width = side_width * _THUMB_CLUSTER_WIDTH_PROPORTION

    common_finger_kwargs = {
        "min_width": side_width,
        "layer_qmk_index": qmk_index,
        "stagger_middle_fingers": True,
        "has_double_south": config.keyboard.features.double_south,
        "use_layer_colors_on_keys": config.output.style.use_layer_colors_on_keys,
        "show_layer_indicators": config.output.style.show_layer_indicators,
        "hold_symbol_position": config.output.style.hold_symbol_position,
    }
    common_thumb_kwargs = {
        "width": thumb_cluster_width,
        "layer_qmk_index": qmk_index,
        "use_layer_colors_on_keys": config.output.style.use_layer_colors_on_keys,
        "show_layer_indicators": config.output.style.show_layer_indicators,
        "hold_symbol_position": config.output.style.hold_symbol_position,
    }

    left_fingers = FingerHalf(
        side=KeyboardSide.LEFT, fingers=layer.left.fingers, **common_finger_kwargs
    )
    right_fingers = FingerHalf(
        side=KeyboardSide.RIGHT, fingers=layer.right.fingers, **common_finger_kwargs
    )
    left_thumb = ThumbCluster(
        side=KeyboardSide.LEFT, cluster=layer.left.thumb, **common_thumb_kwargs
    )
    right_thumb = ThumbCluster(
        side=KeyboardSide.RIGHT, cluster=layer.right.thumb, **common_thumb_kwargs
    )

    # Right-edge overflow magnitude (left-side components bleed
    # inward toward the centre). With negative-for-left-overflow
    # offset semantics, ``(overflow_size - size) + overflow_offset``
    # = ``(left + right) + (-left)`` = ``right``.
    left_fingers_right_bleed = (
        left_fingers.metrics.overflow_size.width - left_fingers.size.width
    ) + left_fingers.metrics.overflow_offset.x
    left_thumb_right_bleed = (
        left_thumb.metrics.overflow_size.width - left_thumb.size.width
    ) + left_thumb.metrics.overflow_offset.x
    # Inward bleed on each side; pull halves apart by the larger of
    # the two so neither side's overflow encroaches the other's.
    inward_bleed = max(
        left_fingers_right_bleed,
        left_thumb_right_bleed,
        -right_fingers.metrics.overflow_offset.x,
        -right_thumb.metrics.overflow_offset.x,
    )

    # Bottom overflow magnitude on finger halves (south-pointing
    # south-key indicators below the cluster) — analogous to
    # right-edge overflow above.
    left_fingers_bottom_bleed = (
        left_fingers.metrics.overflow_size.height - left_fingers.size.height
    ) + left_fingers.metrics.overflow_offset.y
    right_fingers_bottom_bleed = (
        right_fingers.metrics.overflow_size.height - right_fingers.size.height
    ) + right_fingers.metrics.overflow_offset.y
    fingers_bottom_bleed = max(left_fingers_bottom_bleed, right_fingers_bottom_bleed)

    # Top overflow magnitude on thumb clusters (DD-key NORTH
    # indicator above the cluster).
    thumbs_top_bleed = max(
        -left_thumb.metrics.overflow_offset.y,
        -right_thumb.metrics.overflow_offset.y,
    )

    # Bottom overflow on thumb clusters — rare, but kept symmetric.
    left_thumb_bottom_bleed = (
        left_thumb.metrics.overflow_size.height - left_thumb.size.height
    ) + left_thumb.metrics.overflow_offset.y
    right_thumb_bottom_bleed = (
        right_thumb.metrics.overflow_size.height - right_thumb.size.height
    ) + right_thumb.metrics.overflow_offset.y
    thumbs_bottom_bleed = max(left_thumb_bottom_bleed, right_thumb_bottom_bleed)

    # Origins.
    left_fingers_x = -left_fingers.metrics.overflow_offset.x
    right_fingers_x = (
        left_fingers_x + left_fingers.size.width + min_horizontal_gap + 2 * inward_bleed
    )
    fingers_y = max(
        -left_fingers.metrics.overflow_offset.y,
        -right_fingers.metrics.overflow_offset.y,
    )

    left_thumb_x = (left_fingers_x + left_fingers.size.width) - left_thumb.size.width
    right_thumb_x = right_fingers_x
    thumbs_y = (
        fingers_y
        + left_fingers.size.height
        + fingers_bottom_bleed
        + min_vertical_gap
        + thumbs_top_bleed
    )

    left_fingers_origin = Point(left_fingers_x, fingers_y)
    right_fingers_origin = Point(right_fingers_x, fingers_y)
    left_thumb_origin = Point(left_thumb_x, thumbs_y)
    right_thumb_origin = Point(right_thumb_x, thumbs_y)

    # The layer's bbox: from x=0 (left fingers' overflow TL) out to
    # the right fingers' overflow right edge horizontally, and from
    # y=0 (fingers' overflow TL) down to the right thumb's overflow
    # bottom vertically. All chrome is inside, so we expose ``size``
    # only.
    size = Size(
        right_fingers_x
        + right_fingers.metrics.overflow_offset.x
        + right_fingers.metrics.overflow_size.width,
        thumbs_y + right_thumb.size.height + thumbs_bottom_bleed,
    )

    def draw_at(d, origin):
        left_fingers.draw_at(
            d, Point(origin.x + left_fingers_origin.x, origin.y + left_fingers_origin.y)
        )
        right_fingers.draw_at(
            d, Point(origin.x + right_fingers_origin.x, origin.y + right_fingers_origin.y)
        )
        left_thumb.draw_at(d, Point(origin.x + left_thumb_origin.x, origin.y + left_thumb_origin.y))
        right_thumb.draw_at(
            d, Point(origin.x + right_thumb_origin.x, origin.y + right_thumb_origin.y)
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
