# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable building block for the four finger clusters of one half.

Hosts :func:`FingerHalf` — the four finger clusters of one keyboard
half, laid out from inner (index) to outer (pinky) along the
appropriate direction for ``side``. Index and pinky may sit a
key-cell-height below middle / ring (``stagger_middle_fingers=True``)
so the layout mimics the real keyboard's finger reach. The overview
image disables the stagger so its rows sit at a uniform baseline.

The half exposes ``size`` (the keys-only / alignment bbox) along
with ``overflow_size`` + ``overflow_offset`` describing the bbox
enclosing every layer-switch indicator that paints past the
keys-only edges. ``overflow_offset`` is the vector from the half's
``(0, 0)`` origin to the overflow bbox's top-left corner — ``0``
on a side without overflow, NEGATIVE by the overflow magnitude on
a side that has it. The parent :func:`KeymapLayer` composes
``origin + overflow_offset`` to read the overflow rectangle in its
own frame.
"""

from __future__ import annotations

from dataclasses import dataclass

from skim.data import SplitSidePosition
from skim.data.keyboard import FingerCluster as FingerClusterData
from skim.domain import KeyboardSide, SvalboardTargetKey

from .composable import Composable
from .primitives import MetricsComponent, Point, Size
from .svalboard_clusters import (
    FingerCluster,
    FingerClusterMetrics,
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


__all__ = [
    "FingerHalf",
    "FingerHalfMetrics",
]
