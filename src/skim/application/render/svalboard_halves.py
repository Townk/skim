# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable building blocks for one half of a Svalboard keymap image.

Hosts two composables that compose the cluster-level pieces in
:mod:`svalboard_clusters` into the finger / hand groupings the layer
and overview images need:

* :func:`FingerHalf` — the four finger clusters of one keyboard half,
  laid out from inner (index) to outer (pinky) along the appropriate
  direction for ``side``. Index and pinky may sit a key-cell-height
  below middle / ring (``stagger_middle_fingers=True``) so the layout
  mimics the real keyboard's finger reach. The overview image disables
  the stagger so its rows sit at a uniform baseline.

* :func:`KeyboardHalf` — :func:`FingerHalf` plus the thumb cluster,
  with the thumb's top edge anchored to the bottom of the lowest
  finger cluster (index / pinky) and a single document-inset gap
  between them. The per-layer keymap image renders one
  :func:`KeyboardHalf` per side; the overview uses :func:`FingerHalf`
  directly without the thumb.

Both halves expose two bbox shapes via their metrics:

* ``size`` — the keys-only / alignment bbox (the parent uses this
  to position the half on the canvas).
* ``overflow_size`` + ``overflow_offset`` — the bbox enclosing
  every layer-switch indicator that paints past the keys-only
  edges, plus the offset from that overflow bbox's top-left
  corner to the half's own ``(0, 0)`` origin. Callers reserve
  ``overflow_size`` of canvas chrome around the half to keep all
  indicators on-canvas.

``KeyboardHalf`` additionally absorbs the thumb cluster's TOP
overflow into the inset gap between fingers and thumb, so the
keys-only bbox already covers it — only LEFT / RIGHT / BOTTOM
overflow survives in ``overflow_size`` for the parent to reserve.
"""

from __future__ import annotations

from dataclasses import dataclass

from skim.data import SplitSidePosition
from skim.data.keyboard import FingerCluster as FingerClusterData, ThumbCluster as ThumbClusterData
from skim.domain import KeyboardSide, SvalboardTargetKey

from .composable import Composable
from .primitives import MetricsComponent, Point, Size
from .svalboard_clusters import (
    FingerCluster,
    FingerClusterMetrics,
    ThumbCluster,
    ThumbClusterMetrics,
    _overflow_from_children,
)

# Number of finger clusters in one keyboard half (index, middle, ring,
# pinky). Used to split the half's width budget across the four
# clusters with three inter-cluster gaps in between.
_FINGER_CLUSTER_COUNT = 4

# Number of horizontal key cells in one finger cluster (W → C → E).
# The cluster's horizontal proportions don't sum to exactly this — the
# centre key is slightly narrower than the outer keys — but the legacy
# layout treated ``cluster_width / 3`` as the canonical "one finger
# key cell" size and used it as the stagger amount for the W-shaped
# index/pinky drop. We keep the same approximation.
_HORIZONTAL_CELLS_PER_CLUSTER = 3

# Proportion of the half's width that the thumb cluster occupies.
# Mirrors the legacy ``_THUMB_CLUSTER_WIDTH_PROPORTION_PER_SIDE`` — the
# thumb sits inside the same horizontal extent as the finger half but
# is narrower so the inward edge of the half stays clear for the
# centre gap between the two halves of the keyboard.
_THUMB_CLUSTER_WIDTH_PROPORTION = 0.42

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class FingerHalfMetrics:
    """Metrics surfaced by a built :func:`FingerHalf`.

    Per-cluster origins are in :func:`FingerHalf`-local coordinates
    (relative to the half's ``draw_at`` origin). The parent layer or
    overview composable shifts them to canvas coordinates by adding
    its own draw origin.

    Attributes
    ----------
    index_origin / middle_origin / ring_origin / pinky_origin : Point
        Top-left origin of each finger cluster inside the half's
        bbox. With ``stagger_middle_fingers=True`` the index / pinky
        origins are shifted DOWN by the stagger amount; middle / ring
        sit at the half's top edge.
    index / middle / ring / pinky : FingerClusterMetrics
        The per-cluster metrics from each :func:`FingerCluster` build,
        carried through verbatim so the parent can read indicator
        anchors / routing geometry without re-instantiating the
        clusters.
    overflow_size / overflow_offset
        The half's overflow bbox and origin offset, aggregated by
        bbox-union of the four clusters' overflows against their
        placement origins. Mirrors
        :class:`FingerClusterMetrics`'s overflow contract — callers
        position the overflow bbox at ``parent_origin -
        overflow_offset`` to land the half's keys-only ``(0, 0)``
        at ``parent_origin``.
    """

    index_origin: Point
    middle_origin: Point
    ring_origin: Point
    pinky_origin: Point
    index: FingerClusterMetrics
    middle: FingerClusterMetrics
    ring: FingerClusterMetrics
    pinky: FingerClusterMetrics
    overflow_size: Size
    overflow_offset: Point


@dataclass(frozen=True, slots=True, kw_only=True)
class KeyboardHalfMetrics:
    """Metrics surfaced by a built :func:`KeyboardHalf`.

    Composes the :class:`FingerHalfMetrics` for the four finger
    clusters with a separate :class:`ThumbClusterMetrics` for the
    thumb. The thumb's origin is in :func:`KeyboardHalf`-local
    coordinates so the parent treats the half as a single unit.

    ``overflow_size`` and ``overflow_offset`` aggregate the finger
    half's and thumb's overflow bboxes against their placement
    origins inside the keyboard half. ``Size.height`` (the half's
    keys-only bbox) already absorbs the thumb's TOP overflow into
    the finger / thumb gap so the keys-only frame stays clean —
    only the LEFT / RIGHT / BOTTOM overflows survive in
    ``overflow_size`` for the parent to reserve canvas chrome.
    """

    fingers: FingerHalfMetrics
    thumb_origin: Point
    thumb: ThumbClusterMetrics
    overflow_size: Size
    overflow_offset: Point


# ---------------------------------------------------------------------------
# FingerHalf
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def FingerHalf(
    ctx,
    *,
    fingers: tuple[
        FingerClusterData[SvalboardTargetKey],
        FingerClusterData[SvalboardTargetKey],
        FingerClusterData[SvalboardTargetKey],
        FingerClusterData[SvalboardTargetKey],
    ],
    side: KeyboardSide,
    min_width: float,
    layer_qmk_index: int,
    stagger_middle_fingers: bool = True,
    has_double_south: bool = False,
    use_layer_colors_on_keys: bool = True,
    show_layer_indicators: bool = True,
    hold_symbol_position: SplitSidePosition = SplitSidePosition.OUTWARD,
):
    """Four finger clusters arranged into one keyboard half.

    Inputs are in canonical finger order — ``(index, middle, ring,
    pinky)`` — regardless of which keyboard half they belong to. The
    composable handles the side-aware layout direction:

    * Right hand: index sits at the inner (left) edge of the bbox,
      pinky at the outer (right) edge — clusters laid out
      left-to-right in the input tuple's order.
    * Left hand: pinky sits at the outer (left) edge, index at the
      inner (right) edge — clusters laid out right-to-left, mirrored
      from the right hand.

    The stagger raises the middle / ring clusters above the index /
    pinky baseline by one finger-key cell height (≈ ``cluster_width
    / 3``) so the visual layout mimics the keyboard's finger-reach
    geometry. Disable via ``stagger_middle_fingers=False`` for the
    overview image, which packs all clusters onto a single baseline
    row.

    ``min_width`` is the half's horizontal floor — the four clusters
    + three inter-cluster gaps fit within exactly that extent. The
    composable splits the budget using
    :attr:`document_metrics.inset` from the active render context as
    the gap size, so callers don't have to pre-compute per-cluster
    sizing. ``cluster_width = (min_width - 3 * inset) / 4``;
    ``stagger_amount = cluster_width / 3``. The reported
    :attr:`Size.width` equals ``min_width`` today, but the contract
    leaves room to grow past it once indicator overhang on the outer
    edges (and, later, overview connection routing) starts inflating
    the half's effective extent.

    Reports :class:`MetricsComponent[FingerHalfMetrics]` exposing
    each cluster's origin and metrics.
    """
    inset = ctx.document_metrics.inset
    cluster_width = (min_width - inset * (_FINGER_CLUSTER_COUNT - 1)) / _FINGER_CLUSTER_COUNT
    stagger_amount = cluster_width / _HORIZONTAL_CELLS_PER_CLUSTER

    index_data, middle_data, ring_data, pinky_data = fingers

    # 1. Build the four cluster composables. Each gets the cluster-level
    #    inputs straight through; the half doesn't know about palette
    #    layer-switch logic — the cluster handles that via
    #    :class:`RenderPalette` from ``ctx.theme.palette``.
    def _make_cluster(
        cluster: FingerClusterData[SvalboardTargetKey],
    ):
        return FingerCluster(
            cluster=cluster,
            side=side,
            width=cluster_width,
            layer_qmk_index=layer_qmk_index,
            has_double_south=has_double_south,
            use_layer_colors_on_keys=use_layer_colors_on_keys,
            show_layer_indicators=show_layer_indicators,
            hold_symbol_position=hold_symbol_position,
        )

    index_cluster = _make_cluster(index_data)
    middle_cluster = _make_cluster(middle_data)
    ring_cluster = _make_cluster(ring_data)
    pinky_cluster = _make_cluster(pinky_data)

    # 2. Per-cluster X positions in the half's local frame.
    #    Right hand: clusters in (index, middle, ring, pinky) order
    #    left-to-right. Left hand: pinky goes leftmost (outer), so
    #    we walk the same sequence in reverse.
    step = cluster_width + inset
    if side is KeyboardSide.RIGHT:
        index_x = 0.0
        middle_x = step
        ring_x = 2.0 * step
        pinky_x = 3.0 * step
    else:
        # Left hand mirrors — pinky outermost (x=0), index innermost (x=3*step).
        pinky_x = 0.0
        ring_x = step
        middle_x = 2.0 * step
        index_x = 3.0 * step

    # 3. Per-cluster Y positions. Index + pinky drop by ``stagger_amount``
    #    when staggering is enabled; middle + ring stay at the top.
    #    The overview image disables the stagger so all four sit at y=0.
    raised_y = 0.0
    dropped_y = stagger_amount if stagger_middle_fingers else 0.0
    middle_y = raised_y
    ring_y = raised_y
    index_y = dropped_y
    pinky_y = dropped_y

    index_origin = Point(index_x, index_y)
    middle_origin = Point(middle_x, middle_y)
    ring_origin = Point(ring_x, ring_y)
    pinky_origin = Point(pinky_x, pinky_y)

    # 4. Half size — keys-only bbox. Width equals ``min_width`` today
    #    (4 * cluster_width + 3 * inset reverses the cluster_width
    #    derivation above). The contract is "at least min_width", so
    #    when indicator overhang inflation lands the reported width
    #    will grow past the floor.
    cluster_height = max(
        index_cluster.size.height,
        middle_cluster.size.height,
        ring_cluster.size.height,
        pinky_cluster.size.height,
    )
    half_height = cluster_height + dropped_y
    size = Size(min_width, half_height)

    overflow_size, overflow_offset = _overflow_from_children(
        parent_size=size,
        children=(
            (
                index_origin,
                index_cluster.metrics.overflow_size,
                index_cluster.metrics.overflow_offset,
            ),
            (
                middle_origin,
                middle_cluster.metrics.overflow_size,
                middle_cluster.metrics.overflow_offset,
            ),
            (
                ring_origin,
                ring_cluster.metrics.overflow_size,
                ring_cluster.metrics.overflow_offset,
            ),
            (
                pinky_origin,
                pinky_cluster.metrics.overflow_size,
                pinky_cluster.metrics.overflow_offset,
            ),
        ),
    )

    def draw_at(d, origin):
        index_cluster.draw_at(d, Point(origin.x + index_origin.x, origin.y + index_origin.y))
        middle_cluster.draw_at(d, Point(origin.x + middle_origin.x, origin.y + middle_origin.y))
        ring_cluster.draw_at(d, Point(origin.x + ring_origin.x, origin.y + ring_origin.y))
        pinky_cluster.draw_at(d, Point(origin.x + pinky_origin.x, origin.y + pinky_origin.y))

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=FingerHalfMetrics(
            index_origin=index_origin,
            middle_origin=middle_origin,
            ring_origin=ring_origin,
            pinky_origin=pinky_origin,
            index=index_cluster.metrics,
            middle=middle_cluster.metrics,
            ring=ring_cluster.metrics,
            pinky=pinky_cluster.metrics,
            overflow_size=overflow_size,
            overflow_offset=overflow_offset,
        ),
    )


# ---------------------------------------------------------------------------
# KeyboardHalf
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def KeyboardHalf(
    ctx,
    *,
    fingers: tuple[
        FingerClusterData[SvalboardTargetKey],
        FingerClusterData[SvalboardTargetKey],
        FingerClusterData[SvalboardTargetKey],
        FingerClusterData[SvalboardTargetKey],
    ],
    thumb: ThumbClusterData[SvalboardTargetKey],
    side: KeyboardSide,
    min_width: float,
    layer_qmk_index: int,
    has_double_south: bool = False,
    use_layer_colors_on_keys: bool = True,
    show_layer_indicators: bool = True,
    hold_symbol_position: SplitSidePosition = SplitSidePosition.OUTWARD,
):
    """One full keyboard half — four finger clusters + thumb cluster.

    Composes :func:`FingerHalf` (with the stagger always enabled —
    the per-layer image's signature look) above a :func:`ThumbCluster`.
    The thumb's top edge sits one document-inset below the LOWEST
    finger cluster's bottom edge (index / pinky after stagger).

    The thumb's horizontal placement matches the legacy
    ``thumb_positions`` math: the thumb hugs the inward edge of the
    half (the side facing the keyboard's centre line). For the right
    hand the thumb's left edge is at x=0; for the left hand the
    thumb's right edge sits at the half's right edge so it hugs the
    inner side. The thumb cluster occupies
    ``min_width * _THUMB_CLUSTER_WIDTH_PROPORTION`` (≈ 42% of the
    half's width) — same proportion the legacy layout used.

    ``min_width`` is the half's horizontal floor, mirroring
    :func:`FingerHalf`. Per-cluster sizing falls out internally from
    that and ``ctx.document_metrics.inset``. The reported
    :attr:`Size.width` equals ``min_width`` today; once indicator
    overhang inflation is wired in, it'll grow past the floor on
    halves whose outer edges carry indicators.

    Reports :class:`MetricsComponent[KeyboardHalfMetrics]` —
    composes :class:`FingerHalfMetrics` with a separate
    :class:`ThumbClusterMetrics` for the thumb, plus the thumb's
    origin in half-local coordinates.
    """
    inset = ctx.document_metrics.inset
    thumb_cluster_width = min_width * _THUMB_CLUSTER_WIDTH_PROPORTION

    # 1. Build the finger half — always staggered for the per-layer
    #    keymap image (the overview composable uses :func:`FingerHalf`
    #    directly with ``stagger_middle_fingers=False``).
    finger_half = FingerHalf(
        fingers=fingers,
        side=side,
        min_width=min_width,
        layer_qmk_index=layer_qmk_index,
        stagger_middle_fingers=True,
        has_double_south=has_double_south,
        use_layer_colors_on_keys=use_layer_colors_on_keys,
        show_layer_indicators=show_layer_indicators,
        hold_symbol_position=hold_symbol_position,
    )

    # 2. Build the thumb cluster.
    thumb_cluster = ThumbCluster(
        cluster=thumb,
        side=side,
        width=thumb_cluster_width,
        layer_qmk_index=layer_qmk_index,
        use_layer_colors_on_keys=use_layer_colors_on_keys,
        show_layer_indicators=show_layer_indicators,
        hold_symbol_position=hold_symbol_position,
    )

    # 3. Place the thumb. Vertical: one-inset gap below the finger
    #    half, plus any TOP overflow the thumb cluster carries
    #    (notably the double-down badge poking above the cluster's
    #    top edge) — pushing the thumb down so that overflow sits
    #    inside the gap rather than encroaching on the finger
    #    cluster above. Horizontal: hugs the INWARD edge — right
    #    hand → thumb's left edge at the half's left edge (x=0);
    #    left hand → thumb's right edge at the half's right edge
    #    (so x = min_width - thumb_cluster_width).
    # ``overflow_offset.y`` is negative when the thumb's TOP
    # indicators (notably the double-down badge) extend above its
    # keys-only origin — subtract to push the thumb DOWN by that
    # magnitude.
    thumb_y = finger_half.size.height + inset - thumb_cluster.metrics.overflow_offset.y
    thumb_x = 0.0 if side is KeyboardSide.RIGHT else min_width - thumb_cluster_width
    thumb_origin = Point(thumb_x, thumb_y)

    # 4. Half size — the keys-only bbox. Height runs from the
    #    finger-half top to the thumb's bottom edge; the gap
    #    inflation we just applied keeps the thumb cluster's
    #    top-edge indicator overflow INSIDE this bbox, so callers
    #    don't have to think about it. Width matches the finger
    #    half (== ``min_width`` by construction).
    size = Size(min_width, thumb_y + thumb_cluster.size.height)

    overflow_size, overflow_offset = _overflow_from_children(
        parent_size=size,
        children=(
            (
                Point(0.0, 0.0),
                finger_half.metrics.overflow_size,
                finger_half.metrics.overflow_offset,
            ),
            (
                thumb_origin,
                thumb_cluster.metrics.overflow_size,
                thumb_cluster.metrics.overflow_offset,
            ),
        ),
    )

    def draw_at(d, origin):
        finger_half.draw_at(d, origin)
        thumb_cluster.draw_at(d, Point(origin.x + thumb_origin.x, origin.y + thumb_origin.y))

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=KeyboardHalfMetrics(
            fingers=finger_half.metrics,
            thumb_origin=thumb_origin,
            thumb=thumb_cluster.metrics,
            overflow_size=overflow_size,
            overflow_offset=overflow_offset,
        ),
    )


__all__ = [
    "FingerHalf",
    "FingerHalfMetrics",
    "KeyboardHalf",
    "KeyboardHalfMetrics",
]
