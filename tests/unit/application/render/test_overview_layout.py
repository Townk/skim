# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.overview_layout module."""

from skim.data.config import (
    Keyboard,
    KeyboardLayer,
    LayerColor,
    Output,
    Palette,
    SkimConfig,
    Style,
)
from skim.application.render.overview_layout import BadgeDimensions, OverviewLayout


def _make_config(num_layers: int, width: float = 1600) -> SkimConfig:
    layers_cfg = tuple(
        KeyboardLayer(index=i, label=str(i), name=f"Layer {i}")
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


_DEFAULT_BADGE = BadgeDimensions(width=200, height=30, border_radius=6)


class TestOverviewLayout:
    def test_layer_row_count_matches_layer_count(self):
        config = _make_config(4)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        assert len(layout.layer_row_y_positions) == 4

    def test_rows_are_vertically_ordered(self):
        config = _make_config(4)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        positions = layout.layer_row_y_positions
        for i in range(len(positions) - 1):
            assert positions[i + 1] > positions[i]

    def test_thumb_row_is_below_last_layer_row(self):
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        last_layer_y = layout.layer_row_y_positions[-1]
        assert layout.thumb_row_y > last_layer_y

    def test_left_column_width_is_positive(self):
        config = _make_config(4)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        assert layout.left_column_width > 0

    def test_canvas_height_is_positive(self):
        config = _make_config(4)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        assert layout.canvas_height > 0

    def test_finger_cluster_positions_per_row(self):
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        for row_idx in range(3):
            positions = layout.finger_cluster_positions(row_idx)
            assert len(positions) == 8

    def test_finger_clusters_left_side_is_left_of_right_side(self):
        config = _make_config(2)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        positions = layout.finger_cluster_positions(0)
        max_left_x = max(p.x for p in positions[:4])
        min_right_x = min(p.x for p in positions[4:])
        assert max_left_x < min_right_x

    def test_finger_cluster_width_is_positive(self):
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        assert layout.finger_cluster_width > 0

    def test_thumb_cluster_positions_returns_two(self):
        config = _make_config(2)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        left_pos, right_pos = layout.thumb_cluster_positions()
        assert left_pos.x < right_pos.x

    def test_layer_row_bounding_box_has_positive_dimensions(self):
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        x, y, w, h = layout.layer_row_bounding_box(0)
        assert w > 0
        assert h > 0

    def test_all_clusters_in_row_share_same_y(self):
        """All 8 finger clusters in a row should be top-aligned (same Y)."""
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        positions = layout.finger_cluster_positions(0)
        ys = [p.y for p in positions]
        assert all(y == ys[0] for y in ys)

    def test_finger_key_size_is_positive(self):
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        assert layout.finger_key_size > 0
