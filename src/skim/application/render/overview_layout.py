# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Overview layout calculations for multi-layer keyboard rendering.

This module calculates positions for the overview image layout which
arranges all keymap layers as horizontal rows stacked vertically, with
a left column for labels and a right column for cluster content.
"""

from skim.data import SkimConfig

from .layout import KeymapLayoutMetrics, Position

# Finger cluster aspect ratio is 1:1 (square), so height == width
_FINGER_CLUSTER_ASPECT_HEIGHT_OVER_WIDTH = 1.0
# Thumb cluster aspect ratio is 1.5:1 (width:height), so height = width / 1.5
_THUMB_CLUSTER_ASPECT_HEIGHT_OVER_WIDTH = 1.0 / 1.5

# Left column takes ~15% of total width
_LEFT_COLUMN_WIDTH_FRACTION = 0.15

# Number of finger clusters per side
_FINGER_CLUSTERS_PER_SIDE = 4

# Vertical offset (in key-size units) applied to index and pinky clusters
_INDEX_PINKY_VERTICAL_OFFSET = 1


class OverviewLayout:
    """Calculates positions for the overview image layout.

    The overview arranges all keymap layers as horizontal rows stacked
    vertically. Each row contains 8 finger clusters (4 left + 4 right).
    Below the last layer row, a thumb cluster row shows layer 0's thumbs.
    A left column holds the logo, "LAYERS" heading, and per-layer labels.

    Args:
        config: The SkimConfig containing layout and keyboard parameters.
    """

    def __init__(self, config: SkimConfig) -> None:
        self._config = config
        self._metrics = KeymapLayoutMetrics.from_config(config)
        self._num_layers = len(config.keyboard.layers)
        self._compute()

    def _compute(self) -> None:
        """Pre-compute all layout values."""
        m = self._metrics
        total_width = m.width

        # Left column: ~15% of total canvas width
        left_col_w = total_width * _LEFT_COLUMN_WIDTH_FRACTION
        right_col_x = left_col_w
        right_col_w = total_width - left_col_w

        # In the right column we must fit 8 finger clusters (4 per side) with
        # spacing between and around them, mirroring the standard layout.
        # The standard layout uses inset as gap between clusters and between
        # the side block and its outer boundary.  We replicate that structure
        # but scaled to the right-column width.
        #
        # Standard layout for one side:
        #   side_width = (total_width/2) - (margin + inset * 8/2)
        # We want the same proportional breakdown but within right_col_w.
        # Scale factor:  right_col_w / total_width
        scale = right_col_w / total_width
        finger_cluster_width = m.finger_cluster_width * scale
        finger_key_size = m.finger_key_size * scale
        thumb_cluster_width = m.thumb_cluster_width * scale
        inset = m.inset * scale
        margin = m.margin * scale
        side_width = m.side_width * scale

        # Height of a finger cluster (aspect 1:1 → height == width)
        finger_cluster_height = finger_cluster_width * _FINGER_CLUSTER_ASPECT_HEIGHT_OVER_WIDTH

        # The tallest a row can be: index/pinky are shifted down by 1 key size,
        # so the row height is the cluster height plus that offset.
        row_height = finger_cluster_height + finger_key_size

        # Row spacing: use inset as the gap between rows
        row_gap = inset * 3

        # Compute Y positions for each layer row, starting after a top margin
        top_margin = margin + inset
        y_positions: list[float] = []
        for i in range(self._num_layers):
            y_positions.append(top_margin + i * (row_height + row_gap))

        # Thumb row sits below the last layer row
        last_layer_y = y_positions[-1]
        thumb_cluster_height = thumb_cluster_width * _THUMB_CLUSTER_ASPECT_HEIGHT_OVER_WIDTH
        thumb_row_y = last_layer_y + row_height + row_gap

        # Total canvas height
        canvas_height = thumb_row_y + thumb_cluster_height + margin + inset

        # Finger cluster X positions (within the right column).
        # Mirror the standard layout left/right pattern scaled to right_col_w.
        # Standard left side: base_x = margin + inset + side_width, clusters go leftward.
        # Standard right side: base_x = width - (margin+inset) - side_width, clusters go rightward.
        # We re-derive using the scaled values anchored from right_col_x.
        left_base_x = right_col_x + margin + inset + side_width
        right_base_x = right_col_x + right_col_w - (margin + inset) - side_width

        # Vertical offsets: index (0) and pinky (3) are offset down by 1 key size
        vertical_offset = [1, 0, 0, 1]

        # Pre-compute X positions for each cluster index per side
        left_xs: list[float] = []
        for idx in range(_FINGER_CLUSTERS_PER_SIDE):
            x = left_base_x - finger_cluster_width - (inset + finger_cluster_width) * idx
            left_xs.append(x)

        right_xs: list[float] = []
        for idx in range(_FINGER_CLUSTERS_PER_SIDE):
            x = right_base_x + (inset + finger_cluster_width) * idx
            right_xs.append(x)

        # Thumb cluster X positions (same proportional logic as standard layout)
        left_thumb_x = right_col_x + margin + inset * 2 + side_width - thumb_cluster_width
        right_thumb_x = right_col_x + right_col_w - (margin + inset * 2) - side_width

        # Store computed values
        self._left_column_width = left_col_w
        self._right_column_x = right_col_x
        self._canvas_width = total_width
        self._canvas_height = canvas_height
        self._layer_row_y_positions = y_positions
        self._layer_row_heights = [row_height] * self._num_layers
        self._thumb_row_y = thumb_row_y
        self._finger_cluster_width = finger_cluster_width
        self._finger_cluster_height = finger_cluster_height
        self._thumb_cluster_width = thumb_cluster_width
        self._thumb_cluster_height = thumb_cluster_height
        self._left_xs = left_xs
        self._right_xs = right_xs
        self._vertical_offset = vertical_offset
        self._finger_key_size = finger_key_size
        self._left_thumb_x = left_thumb_x
        self._right_thumb_x = right_thumb_x

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def layer_row_y_positions(self) -> list[float]:
        """Y positions for each layer's finger cluster row."""
        return self._layer_row_y_positions

    @property
    def layer_row_heights(self) -> list[float]:
        """Heights for each layer row."""
        return self._layer_row_heights

    @property
    def thumb_row_y(self) -> float:
        """Y position for the thumb cluster row."""
        return self._thumb_row_y

    @property
    def left_column_width(self) -> float:
        """Width allocated to the left label column."""
        return self._left_column_width

    @property
    def right_column_x(self) -> float:
        """X coordinate where the right (clusters) column starts."""
        return self._right_column_x

    @property
    def canvas_width(self) -> float:
        """Total canvas width."""
        return self._canvas_width

    @property
    def canvas_height(self) -> float:
        """Total canvas height."""
        return self._canvas_height

    @property
    def finger_cluster_width(self) -> float:
        """Width of each finger cluster in the overview."""
        return self._finger_cluster_width

    @property
    def thumb_cluster_width(self) -> float:
        """Width of each thumb cluster in the overview."""
        return self._thumb_cluster_width

    def finger_cluster_positions(self, layer_idx: int) -> list[Position]:
        """Return 8 Position objects for the finger clusters in a layer row.

        Positions 0–3 are left-side clusters (index→pinky),
        positions 4–7 are right-side clusters (index→pinky).

        Args:
            layer_idx: The layer index (0-based).

        Returns:
            List of 8 Position objects.
        """
        row_y = self._layer_row_y_positions[layer_idx]
        positions: list[Position] = []

        # Left side: index (0) → pinky (3)
        for idx in range(_FINGER_CLUSTERS_PER_SIDE):
            y_off = self._finger_key_size * self._vertical_offset[idx]
            positions.append(Position(x=self._left_xs[idx], y=row_y + y_off))

        # Right side: index (0) → pinky (3)
        for idx in range(_FINGER_CLUSTERS_PER_SIDE):
            y_off = self._finger_key_size * self._vertical_offset[idx]
            positions.append(Position(x=self._right_xs[idx], y=row_y + y_off))

        return positions

    def thumb_cluster_positions(self) -> tuple[Position, Position]:
        """Return (left_pos, right_pos) for the thumb cluster row.

        Returns:
            Tuple of (left_thumb_position, right_thumb_position).
        """
        return (
            Position(x=self._left_thumb_x, y=self._thumb_row_y),
            Position(x=self._right_thumb_x, y=self._thumb_row_y),
        )

    def layer_row_bounding_box(self, layer_idx: int) -> tuple[float, float, float, float]:
        """Return (x, y, width, height) bounding box for a layer row.

        Useful for connector line targeting.

        Args:
            layer_idx: The layer index (0-based).

        Returns:
            Tuple of (x, y, width, height).
        """
        row_y = self._layer_row_y_positions[layer_idx]
        row_h = self._layer_row_heights[layer_idx]
        # The row spans from right_column_x to canvas_width
        x = self._right_column_x
        w = self._canvas_width - self._right_column_x
        return (x, row_y, w, row_h)
