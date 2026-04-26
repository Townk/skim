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

# Thumb cluster aspect ratio is 1.5:1 (width:height), so height = width / 1.5
_THUMB_CLUSTER_ASPECT = 1.0 / 1.5

_FINGER_CLUSTERS_PER_SIDE = 4

# Finger cluster key proportions — must match FingerClusterComponent so the
# overview reserves the same content extent the cluster actually renders.
_OUTER_KEY_PROPORTION = 0.328
_CENTER_KEY_PROPORTION = 0.309
_KEY_INSET_PROPORTION = 0.018

# KEYMAP_SPACING ratio: the connector router spaces lanes/columns at this
# fraction of an outer key's width. Must match overview._CONNECTOR_SPACING_RATIO.
_KEYMAP_SPACING_RATIO_OF_OUTER_KEY = 0.6

# Gap between the layer-badge column (col 1) and the L4 finger cluster,
# expressed in KEYMAP_SPACINGs. Fixed so the visual rhythm tracks the
# connector router's lane spacing rather than canvas-relative inset units.
_BADGE_TO_CLUSTER_GAP_KS = 4

# Thumb cluster's inset proportion (between rows of thumb keys) — matches
# ThumbClusterComponent.
_THUMB_KEY_INSET_PROPORTION = 0.038

# Badge internal padding (SVG units)
_BADGE_PADDING_LEFT = 15.0
_BADGE_PADDING_RIGHT = 30.0

# Logo dimensions used for header — must mirror what overview.py renders so
# the layout reserves the right amount of header space.
_LOGO_WIDTH_TO_BADGE_WIDTH = 1.06
_LOGO_HEIGHT_TO_WIDTH = 458.333 / 2333.333


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

        # Gap between col 1 (layer badges) and col 2 (L4 finger cluster) is
        # 4 * KEYMAP_SPACING — where KEYMAP_SPACING is the connector router's
        # lane/column spacing, equal to ``outer_key_width * 0.6``. Both
        # finger_cluster_width and col_gap depend on each other, so solve the
        # fixed point in closed form. Let
        #   gap_ratio = _BADGE_TO_CLUSTER_GAP_KS * _OUTER_KEY_PROPORTION
        #             * _KEYMAP_SPACING_RATIO_OF_OUTER_KEY
        # Then col_gap = gap_ratio * fcw and
        #   fcw = m.finger_cluster_width * (config_width - col1_width
        #           - col_gap - padding) / (m.side_width * 2 + m.inset * 2)
        # Combining gives the closed form below.
        gap_ratio_of_fcw = (
            _BADGE_TO_CLUSTER_GAP_KS * _OUTER_KEY_PROPORTION * _KEYMAP_SPACING_RATIO_OF_OUTER_KEY
        )
        denom = m.side_width * 2 + m.inset * 2
        k = gap_ratio_of_fcw * m.finger_cluster_width / denom
        col_gap = k * (config_width - col1_width - padding) / (1 + k)

        # Column 2 starts after col1 + gap.
        # Its width is based on the config width MINUS badge and routing areas.
        col2_x = col1_width + col_gap
        col2_width = config_width - col2_x - padding

        # Scale finger clusters to fit within col2.
        scale = col2_width / denom
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

        # Finger cluster content height — outer keys (N, S, [DS]) stacked
        # around the center key with insets between each row. This matches
        # FingerClusterComponent.height (the content extent, not the bbox
        # aspect ratio). Without this, the bbox overshoot in DS (~1.4% of
        # cluster width) would tighten the gap to the thumb row.
        outer_rows = 3 if self._has_double_south else 2
        finger_cluster_height = finger_cluster_width * (
            outer_rows * _OUTER_KEY_PROPORTION
            + _CENTER_KEY_PROPORTION
            + outer_rows * _KEY_INSET_PROPORTION
        )

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

        # Row gap = south_key height (one key of breathing room). Keeps the
        # rhythm consistent regardless of canvas size or DS state — both badge
        # height and the gap track the same key dimension.
        row_gap = finger_cluster_width * _OUTER_KEY_PROPORTION

        # Header row height — equal to the actual content (logo dominates by
        # default; title text is centered on it). Must NOT include extra slack
        # past the content, otherwise the title-to-row-1 gap balloons beyond
        # the inter-row gap.
        logo_width = self._badge_dims.width * _LOGO_WIDTH_TO_BADGE_WIDTH
        logo_height = logo_width * _LOGO_HEIGHT_TO_WIDTH
        header_height = logo_height

        # Y positions for layer rows (after header)
        top_y = padding + header_height + row_gap
        y_positions: list[float] = []
        for i in range(self._num_layers):
            y_positions.append(top_y + i * (row_height + row_gap))

        # Thumb row below last layer row — same gap as between layer rows.
        # If a double_down key carries a layer indicator that overflows the
        # cluster top, ``shift_thumb_down`` later pushes the thumb down to
        # clear it; we don't reserve that space speculatively.
        last_layer_y = y_positions[-1] if y_positions else top_y
        thumb_cluster_height = thumb_cluster_width * _THUMB_CLUSTER_ASPECT
        thumb_row_y = last_layer_y + row_height + row_gap

        # Canvas height — bottom uses one inset of breathing room (matches the
        # per-layer canvas rule), not the larger outer padding the sides use.
        canvas_height = thumb_row_y + thumb_cluster_height + m.inset

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
        """Y offset from the top of the cluster row to the E/W key TOP.

        E/W keys sit one inset below the north key, since the inset_width
        gap between rows separates them.
        """
        return self._finger_cluster_width * (_OUTER_KEY_PROPORTION + _KEY_INSET_PROPORTION)

    @property
    def outer_key_size(self) -> float:
        """Side length of an outer (N/S/E/W) finger key."""
        return self._finger_cluster_width * _OUTER_KEY_PROPORTION

    @property
    def thumb_pad_key_y_offset(self) -> float:
        """Y offset from the thumb cluster top to the pad key TOP.

        Pad key sits one thumb-cluster inset below the down key (which is at
        cluster top). Used to align the THUMBS badge with the pad key row.
        """
        return self._thumb_cluster_width * _THUMB_KEY_INSET_PROPORTION

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

    def thumb_cluster_y_bounds(self) -> tuple[float, float]:
        """Return (top_y, bottom_y) of the thumb cluster row.

        Bottom = top + cluster height. Used by connector routing to compute
        Phase 1 escape-lane positions.
        """
        return (self._thumb_row_y, self._thumb_row_y + self._thumb_cluster_height)

    def shift_thumb_down(self, amount: float) -> None:
        """Push the thumb cluster down by ``amount`` and grow the canvas accordingly.

        Used by the connector router when ``extra_top_padding > 0``.
        """
        if amount <= 0:
            return
        self._thumb_row_y += amount
        self._canvas_height += amount

    def shift_layer_row_and_below(self, row_idx: int, amount: float) -> None:
        """Shift layer row ``row_idx`` and every row below it (plus thumb) down.

        Used to apply a layer's ``extra_top_padding`` during connector routing.
        Grows the canvas accordingly. No-op when ``amount <= 0``.
        """
        if amount <= 0:
            return
        for i in range(row_idx, len(self._layer_row_y_positions)):
            self._layer_row_y_positions[i] += amount
        self._thumb_row_y += amount
        self._canvas_height += amount

    def shift_below_layer_row(self, row_idx: int, amount: float) -> None:
        """Shift every row strictly below ``row_idx`` (plus thumb) down.

        Used to apply a layer's ``extra_bottom_padding`` — the lanes occupy
        the gap reserved between this layer's row and the next thing below.
        The row at ``row_idx`` itself does NOT move. Grows the canvas
        accordingly. No-op when ``amount <= 0``.
        """
        if amount <= 0:
            return
        for i in range(row_idx + 1, len(self._layer_row_y_positions)):
            self._layer_row_y_positions[i] += amount
        self._thumb_row_y += amount
        self._canvas_height += amount

    def adjust_canvas_width(self, needed_width: float) -> None:
        """Set canvas width to fit routing columns, shrinking if over-allocated."""
        self._canvas_width = max(needed_width, self._col2_x + self._col2_width + self._padding)

    def layer_row_bounding_box(self, row_idx: int) -> tuple[float, float, float, float]:
        row_y = self._layer_row_y_positions[row_idx]
        x = self._col2_x
        w = self._col2_width
        return (x, row_y, w, self._row_height)

    def layer_row_target_y(self, row_idx: int) -> float:
        """Return the vertical center of the row's East key.

        Connector paths terminate at this Y so they meet the E key on the layer
        row's right edge — not the row bbox's vertical center, which falls
        between S and DS (well below the E key) when Double-South is present.
        """
        row_y = self._layer_row_y_positions[row_idx]
        return row_y + self.ew_key_y_offset + self.outer_key_size / 2.0
