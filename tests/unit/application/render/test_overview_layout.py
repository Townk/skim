# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.overview_layout module."""

import pytest

from skim.data.config import (
    Keyboard,
    KeyboardLayer,
    LayerColor,
    Output,
    Palette,
    SkimConfig,
    Style,
)
from skim.application.render.overview_layout import OverviewLayout


def _make_config(num_layers: int, width: float = 1600) -> SkimConfig:
    layers_cfg = tuple(
        KeyboardLayer(label=str(i), name=f"Layer {i}")
        for i in range(num_layers)
    )
    layer_colors = tuple(
        LayerColor(base_color=f"#{i+1:02x}{i+1:02x}{i+1:02x}")
        for i in range(num_layers)
    )
    return SkimConfig(
        keyboard=Keyboard(layers=layers_cfg),
        output=Output(
            style=Style(palette=Palette(layers=layer_colors)),
        ),
    )


class TestOverviewLayout:
    def test_layer_row_count_matches_layer_count(self):
        config = _make_config(4)
        layout = OverviewLayout(config)
        assert len(layout.layer_row_y_positions) == 4

    def test_rows_are_vertically_ordered(self):
        config = _make_config(4)
        layout = OverviewLayout(config)
        positions = layout.layer_row_y_positions
        for i in range(len(positions) - 1):
            assert positions[i + 1] > positions[i]

    def test_thumb_row_is_below_last_layer_row(self):
        config = _make_config(3)
        layout = OverviewLayout(config)
        last_layer_y = layout.layer_row_y_positions[-1]
        assert layout.thumb_row_y > last_layer_y

    def test_left_column_width_is_positive(self):
        config = _make_config(4)
        layout = OverviewLayout(config)
        assert layout.left_column_width > 0

    def test_canvas_height_is_positive(self):
        config = _make_config(4)
        layout = OverviewLayout(config)
        assert layout.canvas_height > 0

    def test_finger_cluster_positions_per_row(self):
        """Each row should have 8 finger cluster positions (4 left + 4 right)."""
        config = _make_config(3)
        layout = OverviewLayout(config)
        for row_idx in range(3):
            positions = layout.finger_cluster_positions(row_idx)
            assert len(positions) == 8

    def test_finger_clusters_left_side_is_left_of_right_side(self):
        config = _make_config(2)
        layout = OverviewLayout(config)
        positions = layout.finger_cluster_positions(0)
        # Left side clusters (0-3) should all have x < right side clusters (4-7)
        max_left_x = max(p.x for p in positions[:4])
        min_right_x = min(p.x for p in positions[4:])
        assert max_left_x < min_right_x

    def test_finger_cluster_width_is_positive(self):
        config = _make_config(3)
        layout = OverviewLayout(config)
        assert layout.finger_cluster_width > 0

    def test_thumb_cluster_positions_returns_two(self):
        config = _make_config(2)
        layout = OverviewLayout(config)
        left_pos, right_pos = layout.thumb_cluster_positions()
        assert left_pos.x < right_pos.x

    def test_layer_row_bounding_box_has_positive_dimensions(self):
        config = _make_config(3)
        layout = OverviewLayout(config)
        x, y, w, h = layout.layer_row_bounding_box(0)
        assert w > 0
        assert h > 0

    def test_right_column_x_equals_left_column_width(self):
        config = _make_config(3)
        layout = OverviewLayout(config)
        assert layout.right_column_x == layout.left_column_width
