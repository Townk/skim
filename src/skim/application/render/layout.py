# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Layout calculations for keyboard rendering.

This module provides data structures and layout calculators for positioning
keyboard clusters (finger and thumb) on the canvas, including metrics
calculation and position generation.
"""

from dataclasses import dataclass

from skim.data import FingerCluster, SkimConfig, ThumbCluster
from skim.domain import Alignment, KeyboardSide

_FINGER_CLUSTER_COUNT = 4
_FINGER_CLUSTER_HORIZONTAL_KEY_COUNT = 3
_THUMB_CLUSTER_WIDTH_PROPORTION_PER_SIDE = 0.42
_SIDE_SPACING_INSET_COUNT = 8


@dataclass(frozen=True, slots=True)
class Position:
    """A 2D position coordinate.

    Attributes:
        x: The x coordinate.
        y: The y coordinate.
    """

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Size:
    """A 2D size with width and height.

    Attributes:
        width: The width dimension.
        height: The height dimension.
    """

    width: float
    height: float


@dataclass(frozen=True, slots=True)
class Boundary:
    """A horizontal boundary with position and width.

    Attributes:
        pos: The position (x, y) of the boundary.
        width: The width of the boundary.
    """

    pos: Position
    width: float


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """A rectangular bounding box with position and size.

    Attributes:
        pos: The position (x, y) of the top-left corner.
        size: The size (width, height) of the box.
    """

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
        """Create LayoutMetrics from a SkimConfig."""
        margin = (
            config.output.layout.spacing.margin
            if not config.output.style.border
            else max(
                # The margin must be at least half the size of the border to
                # allow the render to draw the full border that is usually
                # render from its center position to the outter side.
                config.output.style.border.width / 2.0,
                config.output.layout.spacing.margin,
            )
        )
        inset = config.output.layout.spacing.inset
        width = config.output.layout.width
        # Each keyboard side should have a left **and** right padding to
        # make them visually more separated in the keymap
        side_width = (width / 2.0) - (margin + inset * _SIDE_SPACING_INSET_COUNT / 2.0)
        # We always have 4 finger clusters and 3 padding spaces between them
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


class KeymapLayout:
    """Calculates positions for finger and thumb clusters.

    This class centralizes the layout calculations to reduce duplication
    and make the code more maintainable.
    """

    def __init__(self, config: SkimConfig):
        """Initialize the layout calculator.

        Args:
            config: The SkimConfig containing layout parameters.
        """
        self.metrics = KeymapLayoutMetrics.from_config(config)

    def left_finger_positions(self):
        """Generate positions for left hand finger clusters (index to pinky).

        Yields:
            Position objects for each finger cluster from index to pinky.
        """
        m = self.metrics
        base_x = m.margin + m.inset + m.side_width
        base_y = m.margin + m.inset

        # 1. Index (inner finger, different y-offset)
        # 2. Middle
        # 3. Ring
        # 4. Pinky (outer finger, different y-offset)
        vertical_offset = [1, 0, 0, 1]
        for idx in range(4):
            yield Position(
                x=base_x - m.finger_cluster_width - (m.inset + m.finger_cluster_width) * idx,
                y=base_y + m.finger_key_size * vertical_offset[idx],
            )

    def right_finger_positions(self):
        """Calculate positions for right hand finger clusters (index to pinky)."""
        m = self.metrics
        base_x = m.width - (m.margin + m.inset) - m.side_width
        base_y = m.margin + self.metrics.inset

        # 1. Index (inner finger, different y-offset)
        # 2. Middle
        # 3. Ring
        # 4. Pinky (outer finger, different y-offset)
        vertical_offset = [1, 0, 0, 1]
        for idx in range(4):
            yield Position(
                x=base_x + (m.inset + m.finger_cluster_width) * idx,
                y=base_y + m.finger_key_size * vertical_offset[idx],
            )

    def thumb_positions(self, finger_cluster_height: float) -> tuple[Position, Position]:
        """Calculate positions for thumb clusters.

        Args:
            finger_cluster_height: Height of the finger clusters (varies with double_south).

        Returns:
            Tuple of (left_thumb_position, right_thumb_position).
        """
        m = self.metrics
        thumb_y = finger_cluster_height + m.finger_key_size + m.margin + m.inset * 5

        left_x = m.margin + m.inset * 2 + m.side_width - m.thumb_cluster_width
        right_x = m.width - (m.margin + m.inset * 2) - m.side_width

        return (
            Position(x=left_x, y=thumb_y),
            Position(x=right_x, y=thumb_y),
        )

    def canvas_height(self, finger_cluster_height: float, thumb_cluster_height: float) -> float:
        """Calculate the total canvas height.

        Args:
            finger_cluster_height: The height of the finger clusters.
            thumb_cluster_height: The height of the thumb clusters.

        Returns:
            The total canvas height including margins and spacing.
        """
        m = self.metrics
        return (
            finger_cluster_height
            + m.finger_key_size
            + thumb_cluster_height
            + m.inset * 6
            + m.margin * 2
        )


@dataclass(frozen=True, slots=True)
class KeyLayout(Boundary):
    """Layout information for a single key.

    Attributes:
        pos: The position of the key.
        width: The width of the key.
        inset: The inset/padding around the key. Default: 0.
        label_alignment_h: Horizontal label alignment. Default: CENTER.
        label_alignment_v: Vertical label alignment. Default: CENTER.
    """

    inset: float = 0
    label_alignment_h: Alignment = Alignment.CENTER
    label_alignment_v: Alignment = Alignment.CENTER


@dataclass(frozen=True, slots=True)
class ThumbClusterKeyProportions:
    """Proportional widths for thumb cluster keys.

    Attributes:
        keys_width_proportion: Proportions for each key in the cluster.
        inset_width_proportion: The inset proportion relative to cluster width.
    """

    keys_width_proportion: ThumbCluster[float]
    inset_width_proportion: float


@dataclass(frozen=True, slots=True)
class ThumbClusterKeySizes:
    """Absolute sizes for thumb cluster keys.

    Attributes:
        width: Absolute widths for each key in the cluster.
        inset: The absolute inset size.
    """

    width: ThumbCluster[float]
    inset: float

    @classmethod
    def from_proportions(cls, cluster_width: float, proportions: ThumbClusterKeyProportions):
        """Create absolute sizes from proportions and cluster width.

        Args:
            cluster_width: The total cluster width.
            proportions: The proportional sizes.

        Returns:
            A ThumbClusterKeySizes instance with absolute dimensions.
        """
        return cls(
            width=proportions.keys_width_proportion.map(lambda m: m * cluster_width),
            inset=proportions.inset_width_proportion * cluster_width,
        )


class ThumbClusterLayout:
    """Calculates layout metrics for thumb cluster keys.

    Attributes:
        metrics: ThumbCluster containing Boundary for each key.
    """

    metrics: ThumbCluster[Boundary]

    def __init__(
        self,
        cluster_side: KeyboardSide,
        cluster_boundary: BoundingBox,
        proportions: ThumbClusterKeyProportions,
    ):
        """Initialize the thumb cluster layout.

        Args:
            cluster_side: The keyboard side (LEFT or RIGHT).
            cluster_boundary: The bounding box for the cluster.
            proportions: The proportional key sizes.
        """
        self.metrics = ThumbClusterLayout._compute_layout(
            side=cluster_side,
            center=Position(
                x=cluster_boundary.size.width / 2.0,
                y=cluster_boundary.size.height / 2.0,
            ),
            cluster_metrics=ThumbClusterKeySizes.from_proportions(
                cluster_boundary.size.width, proportions
            ),
        )

    @staticmethod
    def _compute_layout(
        side: KeyboardSide, center: Position, cluster_metrics: ThumbClusterKeySizes
    ) -> ThumbCluster[Boundary]:
        """Compute the layout boundaries for all thumb cluster keys.

        Args:
            side: The keyboard side (LEFT or RIGHT).
            center: The center position of the cluster.
            cluster_metrics: The key sizes for the cluster.

        Returns:
            A ThumbCluster containing Boundary for each key.
        """
        down_key_layout = Boundary(
            width=cluster_metrics.width.down_key,
            pos=Position(x=center.x - cluster_metrics.width.down_key / 2.0, y=0),
        )
        double_down_key_layout = Boundary(
            width=cluster_metrics.width.double_down_key,
            pos=Position(
                x=center.x - cluster_metrics.width.double_down_key / 2.0,
                y=cluster_metrics.inset * 2.0,
            ),
        )
        is_left = side == KeyboardSide.LEFT
        top_left_x = (
            center.x
            - down_key_layout.width / 2.0
            - cluster_metrics.width.pad_key
            + cluster_metrics.inset / 2.0
        )
        top_right_x = center.x + down_key_layout.width / 2.0 - cluster_metrics.inset / 2.0
        pad_key_layout = Boundary(
            width=cluster_metrics.width.pad_key,
            pos=Position(
                x=top_left_x if is_left else top_right_x,
                y=cluster_metrics.inset,
            ),
        )
        top_left_x = (
            center.x
            - down_key_layout.width / 2.0
            - cluster_metrics.width.nail_key
            + cluster_metrics.inset / 2.0
        )
        nail_key_layout = Boundary(
            width=cluster_metrics.width.nail_key,
            pos=Position(
                x=top_right_x if is_left else top_left_x,
                y=pad_key_layout.pos.y,
            ),
        )
        up_left_x = center.x - cluster_metrics.width.up_key - cluster_metrics.inset / 2.0
        up_right_x = center.x + cluster_metrics.inset / 2.0
        up_key_layout = Boundary(
            width=cluster_metrics.width.up_key,
            pos=Position(
                x=up_left_x if is_left else up_right_x,
                y=center.y - cluster_metrics.inset * 1.5,
            ),
        )
        knuckle_left_x = (
            nail_key_layout.pos.x + nail_key_layout.width - cluster_metrics.width.knuckle_key
        )
        knuckle_right_x = nail_key_layout.pos.x
        knuckle_key_layout = Boundary(
            width=cluster_metrics.width.knuckle_key,
            pos=Position(
                x=knuckle_left_x if is_left else knuckle_right_x,
                y=up_key_layout.pos.y,
            ),
        )

        return ThumbCluster(
            down_key=down_key_layout,
            double_down_key=double_down_key_layout,
            pad_key=pad_key_layout,
            nail_key=nail_key_layout,
            up_key=up_key_layout,
            knuckle_key=knuckle_key_layout,
        )


@dataclass(frozen=True, slots=True)
class FingerClusterKeyProportions:
    """Proportional widths for finger cluster keys.

    Attributes:
        center_key_width_proportion: Proportion for the center key.
        outer_key_width_proportion: Proportion for outer keys (N/S/E/W).
        inset_width_proportion: The inset proportion relative to cluster width.
    """

    center_key_width_proportion: float
    outer_key_width_proportion: float
    inset_width_proportion: float


@dataclass(frozen=True, slots=True)
class FingerClusterKeySizes:
    """Absolute sizes for finger cluster keys.

    Attributes:
        center_key_width: Absolute width for the center key.
        outer_key_width: Absolute width for outer keys (N/S/E/W).
        inset_width: The absolute inset size.
    """

    center_key_width: float
    outer_key_width: float
    inset_width: float

    @classmethod
    def from_proportions(cls, cluster_width: float, proportions: FingerClusterKeyProportions):
        """Create absolute sizes from proportions and cluster width.

        Args:
            cluster_width: The total cluster width.
            proportions: The proportional sizes.

        Returns:
            A FingerClusterKeySizes instance with absolute dimensions.
        """
        return cls(
            center_key_width=cluster_width * proportions.center_key_width_proportion,
            outer_key_width=cluster_width * proportions.outer_key_width_proportion,
            inset_width=cluster_width * proportions.inset_width_proportion,
        )


class FingerClusterLayout:
    """Calculates layout metrics for finger cluster keys.

    Attributes:
        metrics: FingerCluster containing Boundary for each key.
    """

    metrics: FingerCluster[Boundary]

    def __init__(
        self,
        cluster_boundary: Boundary,
        proportions: FingerClusterKeyProportions,
    ):
        """Initialize the finger cluster layout.

        Args:
            cluster_boundary: The boundary for the cluster.
            proportions: The proportional key sizes.
        """
        self.metrics = FingerClusterLayout._compute_layout(
            center_x=cluster_boundary.width / 2.0,
            cluster_metrics=FingerClusterKeySizes.from_proportions(
                cluster_boundary.width, proportions
            ),
        )

    @staticmethod
    def _compute_layout(
        center_x: float, cluster_metrics: FingerClusterKeySizes
    ) -> FingerCluster[Boundary]:
        """Compute the layout boundaries for all finger cluster keys.

        Args:
            center_x: The x-coordinate of the cluster center.
            cluster_metrics: The key sizes for the cluster.

        Returns:
            A FingerCluster containing Boundary for each key.
        """
        north_key_layout = Boundary(
            width=cluster_metrics.outer_key_width,
            pos=Position(
                x=center_x - cluster_metrics.outer_key_width / 2.0,
                y=0,
            ),
        )

        center_key_layout = Boundary(
            width=cluster_metrics.center_key_width,
            pos=Position(
                x=center_x - cluster_metrics.center_key_width / 2.0,
                y=north_key_layout.pos.y + north_key_layout.width + cluster_metrics.inset_width,
            ),
        )

        south_key_layout = Boundary(
            width=cluster_metrics.outer_key_width,
            pos=Position(
                x=center_x - cluster_metrics.outer_key_width / 2.0,
                y=center_key_layout.pos.y + center_key_layout.width + cluster_metrics.inset_width,
            ),
        )

        east_key_layout = Boundary(
            width=cluster_metrics.outer_key_width,
            pos=Position(
                x=center_key_layout.pos.x + center_key_layout.width + cluster_metrics.inset_width,
                y=north_key_layout.pos.y + north_key_layout.width,
            ),
        )

        west_key_layout = Boundary(
            width=cluster_metrics.outer_key_width,
            pos=Position(
                x=center_key_layout.pos.x
                - (cluster_metrics.outer_key_width + cluster_metrics.inset_width),
                y=north_key_layout.pos.y + north_key_layout.width,
            ),
        )

        double_south_key_layout = Boundary(
            width=cluster_metrics.outer_key_width,
            pos=Position(
                x=center_x - cluster_metrics.outer_key_width / 2.0,
                y=south_key_layout.pos.y + south_key_layout.width + cluster_metrics.inset_width,
            ),
        )

        return FingerCluster(
            center_key=center_key_layout,
            north_key=north_key_layout,
            east_key=east_key_layout,
            south_key=south_key_layout,
            west_key=west_key_layout,
            double_south_key=double_south_key_layout,
        )
