# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.connectors module."""

from unittest.mock import MagicMock

from skim.application.render.connectors import (
    ConnectorStep,
    Direction,
    target_point_for,
)


class TestDirection:
    def test_has_four_cardinal_directions(self):
        assert {Direction.UP, Direction.RIGHT, Direction.DOWN, Direction.LEFT} == set(Direction)


class TestConnectorStep:
    def test_default_col_x_is_zero(self):
        # path is built lazily in Phase 2; col_x starts at 0 and is set during column allocation
        step = ConnectorStep(
            key=None,
            direction=Direction.UP,
            target_point=(0.0, 0.0),
            target_layer=0,
        )
        assert step.col_x == 0


class TestTargetPointFor:
    def _layout(self, layer_count=3):
        layout = MagicMock()
        # Each row at y = 100 * (i+1), height 50, right edge 800
        layout.layer_row_y_positions = [100, 200, 300]
        layout.layer_row_heights = [50, 50, 50]
        layout.right_column_x = 200  # arbitrary
        # Mock layer_row_bounding_box(idx) -> (x, y, w, h)
        layout.layer_row_bounding_box = lambda idx: (
            200,
            layout.layer_row_y_positions[idx],
            600,
            50,
        )
        return layout

    def test_returns_point_for_valid_target(self):
        layout = self._layout()
        # spacing = 18 (one outer key)
        point = target_point_for(layout, target_layer=1, source_layer=0, keymap_spacing=18)
        # right edge of layer 1's bbox = 200 + 600 = 800; vertical center = 200 + 25 = 225
        assert point == (818.0, 225.0)

    def test_returns_none_for_self_referential(self):
        layout = self._layout()
        # source layer == target layer means self-reference; no connector
        assert target_point_for(layout, target_layer=2, source_layer=2, keymap_spacing=18) is None

    def test_returns_none_for_out_of_range_target(self):
        layout = self._layout()
        assert target_point_for(layout, target_layer=99, source_layer=0, keymap_spacing=18) is None
        assert target_point_for(layout, target_layer=-1, source_layer=0, keymap_spacing=18) is None
