# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Overview layout calculations for multi-layer keyboard rendering.

This module calculates positions for the overview image layout which
arranges all keymap layers as horizontal rows in a table-like structure:
Row 0 is the header (logo + title), subsequent rows hold layer badges
(column 1) and finger clusters (column 2).
"""

from dataclasses import dataclass

from skim.data import SkimConfig

from .layout import KeymapLayoutMetrics, Position

# Finger cluster aspect ratio is 1:1 (square), or 3:4 with double_south
_FINGER_CLUSTER_ASPECT = 1.0
_FINGER_CLUSTER_ASPECT_DOUBLE_SOUTH = 4.0 / 3.0
# Thumb cluster aspect ratio is 1.5:1 (width:height), so height = width / 1.5
_THUMB_CLUSTER_ASPECT = 1.0 / 1.5

_FINGER_CLUSTERS_PER_SIDE = 4

# Outer key width proportion (N/S/E/W keys) — same as FingerClusterComponent
_OUTER_KEY_PROPORTION = 0.328

# Badge internal padding (SVG units)
_BADGE_PADDING_LEFT = 15.0
_BADGE_PADDING_RIGHT = 30.0


@dataclass(frozen=True, slots=True)
class BadgeDimensions:
    """Pre-computed badge sizing for the overview.

    Attributes:
        width: Uniform width for all badges (including THUMBS).
        height: Uniform height matching the E/W key size.
        border_radius: Corner radius.
    """
    width: float
    height: float
    border_radius: float


class OverviewLayout:
    """Calculates positions for the overview image layout.

    The layout is table-like:
    - Row 0 (header): logo in col 1, title in col 2
    - Rows 1..N: layer badge in col 1, 8 finger clusters in col 2
    - Last row: THUMBS badge in col 1, thumb clusters in col 2

    All finger clusters in a row share the same Y (top-aligned).

    Args:
        config: The SkimConfig containing layout and keyboard parameters.
        badge_dims: Pre-computed badge dimensions.
    """

    def __init__(
        self,
        config: SkimConfig,
        badge_dims: BadgeDimensions,
        routing_column_count: int = 0,
    ) -> None:
        self._config = config
        self._base_metrics = KeymapLayoutMetrics.from_config(config)
        self._num_layers = len(config.keyboard.layers)
        self._badge_dims = badge_dims
        self._has_double_south = config.keyboard.features.double_south
        self._routing_column_count = routing_column_count
        self._compute()

    def _compute(self) -> None:
        m = self._base_metrics
        config_width = m.width

        # Outer padding — bigger than single-layer images
        padding = max(m.inset * 2, 40.0)

        # Column 1 width: badge width + left padding
        col1_width = padding + self._badge_dims.width

        # Gap between col 1 and col 2 — at least as wide as the thumb cluster gap
        col_gap = m.inset * 4  # generous gap, refined below

        # Column 2 starts after col1 + gap.
        # Its width is based on the config width MINUS badge and routing areas.
        col2_x = col1_width + col_gap
        col2_width = config_width - col2_x - padding

        # Scale finger clusters to fit within col2.
        scale = col2_width / (m.side_width * 2 + m.inset * 2)
        finger_cluster_width = m.finger_cluster_width * scale
        finger_key_size = m.finger_key_size * scale
        thumb_cluster_width = m.thumb_cluster_width * scale
        inset = m.inset * scale
        side_width = m.side_width * scale

        # Refine col_gap: ensure it's at least the thumb cluster gap
        thumb_center_gap = col2_width - 2 * (side_width - thumb_cluster_width) - 2 * thumb_cluster_width
        col_gap = max(col_gap, thumb_center_gap, m.inset * 3)

        # Recompute col2 with refined gap
        col2_x = col1_width + col_gap
        col2_width = config_width - col2_x - padding

        # Rescale with the final col2_width
        scale = col2_width / (m.side_width * 2 + m.inset * 2)
        finger_cluster_width = m.finger_cluster_width * scale
        finger_key_size = m.finger_key_size * scale
        thumb_cluster_width = m.thumb_cluster_width * scale
        inset = m.inset * scale
        side_width = m.side_width * scale

        # N key width for routing column spacing
        nk = finger_cluster_width * _OUTER_KEY_PROPORTION

        # Routing area: to the right of the cluster area.
        # Each routing column is 1 N key wide, plus padding + 1 N key gap
        # from the rightmost cluster edge.
        routing_area_width = 0.0
        if self._routing_column_count > 0:
            routing_area_width = (
                padding  # gap between clusters and routing
                + nk  # minimum final LEFT segment
                + self._routing_column_count * nk  # routing columns
            )

        # Total canvas width = clusters area + routing area
        total_width = config_width + routing_area_width

        # Finger cluster height: 1:1 normally, 3:4 with double_south
        if self._has_double_south:
            finger_cluster_height = finger_cluster_width * _FINGER_CLUSTER_ASPECT_DOUBLE_SOUTH
        else:
            finger_cluster_height = finger_cluster_width * _FINGER_CLUSTER_ASPECT

        # Row height = cluster height (no vertical offset — all clusters top-aligned)
        row_height = finger_cluster_height

        # Finger cluster X positions (all top-aligned, no vertical offset)
        left_base_x = col2_x + side_width
        right_base_x = col2_x + col2_width - side_width

        left_xs: list[float] = []
        for idx in range(_FINGER_CLUSTERS_PER_SIDE):
            x = left_base_x - finger_cluster_width - (inset + finger_cluster_width) * idx
            left_xs.append(x)

        right_xs: list[float] = []
        for idx in range(_FINGER_CLUSTERS_PER_SIDE):
            x = right_base_x + (inset + finger_cluster_width) * idx
            right_xs.append(x)

        # Row gap = same as the center gap between left and right finger clusters
        center_gap = right_base_x - left_base_x
        row_gap = center_gap

        # Header row height (logo + title)
        header_height = max(self._badge_dims.height * 2, 50.0)

        # Y positions for layer rows (after header)
        top_y = padding + header_height + row_gap
        y_positions: list[float] = []
        for i in range(self._num_layers):
            y_positions.append(top_y + i * (row_height + row_gap))

        # Thumb row below last layer row — account for indicator circles
        # that may appear above the thumb cluster keys
        last_layer_y = y_positions[-1] if y_positions else top_y
        thumb_cluster_height = thumb_cluster_width * _THUMB_CLUSTER_ASPECT
        thumb_indicator_clearance = thumb_cluster_width * 0.15
        thumb_row_y = last_layer_y + row_height + row_gap + thumb_indicator_clearance

        # Canvas height
        canvas_height = thumb_row_y + thumb_cluster_height + padding

        # Thumb cluster X positions with indicator padding.
        # The inward-facing thumb keys (nail, knuckle) have circles that extend
        # toward the center. Use a generous padding to prevent overlap.
        indicator_padding = thumb_cluster_width * 0.18
        left_thumb_x = col2_x + inset + side_width - thumb_cluster_width - indicator_padding
        right_thumb_x = col2_x + col2_width - inset - side_width + indicator_padding

        # Store everything
        self._padding = padding
        self._col1_width = col1_width
        self._col_gap = col_gap
        self._col2_x = col2_x
        self._col2_width = col2_width
        self._canvas_width = total_width
        self._canvas_height = canvas_height
        self._header_height = header_height
        self._layer_row_y_positions = y_positions
        self._row_height = row_height
        self._thumb_row_y = thumb_row_y
        self._finger_cluster_width = finger_cluster_width
        self._finger_cluster_height = finger_cluster_height
        self._finger_key_size = finger_key_size
        self._thumb_cluster_width = thumb_cluster_width
        self._thumb_cluster_height = thumb_cluster_height
        self._left_xs = left_xs
        self._right_xs = right_xs
        self._left_thumb_x = left_thumb_x
        self._right_thumb_x = right_thumb_x

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def padding(self) -> float:
        return self._padding

    @property
    def header_height(self) -> float:
        return self._header_height

    @property
    def layer_row_y_positions(self) -> list[float]:
        return self._layer_row_y_positions

    @property
    def layer_row_heights(self) -> list[float]:
        return [self._row_height] * self._num_layers

    @property
    def thumb_row_y(self) -> float:
        return self._thumb_row_y

    @property
    def left_column_width(self) -> float:
        return self._col1_width

    @property
    def right_column_x(self) -> float:
        return self._col2_x

    @property
    def canvas_width(self) -> float:
        return self._canvas_width

    @property
    def canvas_height(self) -> float:
        return self._canvas_height

    @property
    def finger_cluster_width(self) -> float:
        return self._finger_cluster_width

    @property
    def finger_key_size(self) -> float:
        """Size of an individual finger key (E/W key width)."""
        return self._finger_key_size

    @property
    def ew_key_y_offset(self) -> float:
        """Y offset from the top of the cluster row to the E/W keys.

        E/W keys sit below the north key: their Y = north_key_height
        (north key is square, so height = outer_key_width_proportion * cluster_width).
        """
        return self._finger_cluster_width * _OUTER_KEY_PROPORTION

    @property
    def thumb_cluster_width(self) -> float:
        return self._thumb_cluster_width

    def finger_cluster_positions(self, row_idx: int) -> list[Position]:
        """Return 8 Position objects for the finger clusters in a row.

        All clusters in a row share the same Y (top-aligned).
        """
        row_y = self._layer_row_y_positions[row_idx]
        positions: list[Position] = []

        for idx in range(_FINGER_CLUSTERS_PER_SIDE):
            positions.append(Position(x=self._left_xs[idx], y=row_y))

        for idx in range(_FINGER_CLUSTERS_PER_SIDE):
            positions.append(Position(x=self._right_xs[idx], y=row_y))

        return positions

    def thumb_cluster_positions(self) -> tuple[Position, Position]:
        return (
            Position(x=self._left_thumb_x, y=self._thumb_row_y),
            Position(x=self._right_thumb_x, y=self._thumb_row_y),
        )

    def layer_row_bounding_box(self, row_idx: int) -> tuple[float, float, float, float]:
        row_y = self._layer_row_y_positions[row_idx]
        x = self._col2_x
        w = self._col2_width
        return (x, row_y, w, self._row_height)
