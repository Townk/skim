# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Per-layer keymap body composable.

:func:`KeymapLayer` — the keyboard area, built from four composables
placed directly: left :func:`FingerHalf`, right :func:`FingerHalf`,
left :func:`ThumbCluster`, right :func:`ThumbCluster`. Each component
is positioned so its overflow rectangle lands fully inside the
layer's bbox, so :func:`KeymapLayer` exposes no overflow itself.

The document composable that stacks this body inside a header /
footer / legend column lives in :mod:`keymap_document` alongside the
other top-level documents.
"""

from __future__ import annotations

from skim.data import SvalboardLayout
from skim.domain import KeyboardSide, SvalboardTargetKey

from .composable import Composable
from .primitives import Point, Size
from .svalboard_clusters import ThumbCluster
from .svalboard_halves import FingerHalf

# Central gap between the two keyboard sides, in units of
# ``DocumentMetrics.column_gap``. ``column_gap`` is the canonical
# horizontal spacing for any visual column arrangement; ``inset`` is
# reserved for vertical Column spacing.
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

    # Horizontal gaps follow the new spacing convention: ``column_gap``
    # for any horizontal column arrangement (clusters across a half,
    # halves across the keyboard); ``inset`` reserved for vertical
    # spacing inside Columns.
    min_horizontal_gap = _CENTER_GAP_INSET_COUNT * metrics.column_gap
    min_vertical_gap = metrics.inset

    side_width = (target_content_w - min_horizontal_gap) / 2.0
    thumb_cluster_width = side_width * _THUMB_CLUSTER_WIDTH_PROPORTION

    common_finger_kwargs = {
        "min_width": side_width,
        "layer_qmk_index": qmk_index,
        "stagger_middle_fingers": True,
        "has_double_south": config.keyboard.features.double_south,
        "use_layer_colors_on_keys": config.output.style.use_layer_colors_on_keys,
        "show_layer_indicators": config.output.style.layer_indicator.show,
        "hold_symbol_position": config.output.style.hold_symbol_position,
    }
    common_thumb_kwargs = {
        "width": thumb_cluster_width,
        "layer_qmk_index": qmk_index,
        "use_layer_colors_on_keys": config.output.style.use_layer_colors_on_keys,
        "show_layer_indicators": config.output.style.layer_indicator.show,
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


__all__ = ["KeymapLayer"]
