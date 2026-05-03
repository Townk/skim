# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Geometry value types + document-wide layout metrics.

The composable framework owns the actual layout — this module just
exposes the few small dataclasses still consumed by composables and
helpers (``Position``, ``Size``, ``Boundary``, ``BoundingBox``) plus
:class:`KeymapLayoutMetrics`, the per-config bundle of derived
dimensions (margin, inset, side / cluster widths, etc.) that several
callers read off a single resolution rule.

The legacy ``KeymapLayout`` / ``FingerClusterLayout`` /
``ThumbClusterLayout`` classes that used to live here have retired —
the composable cluster + half composables (:func:`FingerCluster`,
:func:`ThumbCluster`, :func:`FingerHalf`) own that math now.
"""

from dataclasses import dataclass

from skim.data import SkimConfig

_FINGER_CLUSTER_COUNT = 4
_FINGER_CLUSTER_HORIZONTAL_KEY_COUNT = 3
_THUMB_CLUSTER_WIDTH_PROPORTION_PER_SIDE = 0.42
_CENTER_GAP_INSET_COUNT = 2.0


@dataclass(frozen=True, slots=True)
class Position:
    """A 2D position coordinate."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Size:
    """A 2D size with width and height."""

    width: float
    height: float


@dataclass(frozen=True, slots=True)
class Boundary:
    """A horizontal boundary with position and width."""

    pos: Position
    width: float


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """A rectangular bounding box with position and size."""

    pos: Position
    size: Size


@dataclass(frozen=True)
class KeymapLayoutMetrics:
    """Computed layout dimensions for keyboard rendering.

    All values are pre-calculated based on the SkimConfig to avoid
    repeated calculations during rendering.
    """

    width: float
    margin: float
    inset: float
    side_width: float
    finger_cluster_width: float
    finger_key_size: float
    thumb_cluster_width: float
    start: float
    end: float
    end_left_side: float
    start_right_side: float

    @classmethod
    def from_config(cls, config: SkimConfig) -> "KeymapLayoutMetrics":
        """Create LayoutMetrics from a SkimConfig.

        Reads margin and inset off a freshly-built
        :class:`DocumentMetrics` — that's the canonical source for the
        document's outer-chrome values, so margin / inset are resolved
        in exactly one place.
        """
        # Local import — :mod:`render_context` doesn't depend on this
        # module, but importing eagerly would make any module that
        # imports ``layout`` pull in the render context too.
        from .render_context import DocumentMetrics

        doc_metrics = DocumentMetrics.from_config(config)
        margin = doc_metrics.margin
        inset = doc_metrics.inset
        width = doc_metrics.doc_width
        center_gap = _CENTER_GAP_INSET_COUNT * inset
        side_width = (width - 2 * margin - 2 * inset - center_gap) / 2.0
        finger_cluster_width = (
            side_width - inset * (_FINGER_CLUSTER_COUNT - 1)
        ) / _FINGER_CLUSTER_COUNT
        finger_key_size = finger_cluster_width / _FINGER_CLUSTER_HORIZONTAL_KEY_COUNT
        thumb_cluster_width = side_width * _THUMB_CLUSTER_WIDTH_PROPORTION_PER_SIDE

        start = margin + inset
        end = width - start
        end_left_side = start + side_width
        start_right_side = end - side_width

        return cls(
            width=width,
            margin=margin,
            inset=inset,
            side_width=side_width,
            finger_cluster_width=finger_cluster_width,
            finger_key_size=finger_key_size,
            thumb_cluster_width=thumb_cluster_width,
            start=start,
            end=end,
            end_left_side=end_left_side,
            start_right_side=start_right_side,
        )
