# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.connectors module."""

from unittest.mock import MagicMock

from skim.application.render.connectors import (
    ConnectorStep,
    Direction,
    build_thumb_path_list,
    set_initial_moveto,
    target_point_for,
)
from skim.data.keyboard import ThumbCluster
from skim.domain import SvalboardTargetKey


def _key(label="K", layer_switch=None):
    return SvalboardTargetKey(label=label, layer_switch=layer_switch)


def _step(direction, indicator_rect):
    """Make a step with a stub key whose indicator has the given rect."""
    step = ConnectorStep(
        key=MagicMock(),
        direction=direction,
        target_point=(0.0, 0.0),
        target_layer=0,
    )
    step.key.layer_indicator.bounding_rect = indicator_rect  # (x, y, w, h)
    return step


def _thumb(**overrides):
    """Build a ThumbCluster with all keys defaulting to no layer_switch."""
    base = {
        name: _key()
        for name in (
            "down_key",
            "pad_key",
            "up_key",
            "nail_key",
            "knuckle_key",
            "double_down_key",
        )
    }
    base.update(overrides)
    return ThumbCluster(**base)


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


class TestBuildThumbPathList:
    def _layout_target(self):
        layout = MagicMock()
        layout.layer_row_y_positions = [100, 200, 300]
        layout.layer_row_heights = [50, 50, 50]
        layout.layer_row_bounding_box = lambda idx: (
            200,
            layout.layer_row_y_positions[idx],
            600,
            50,
        )
        return layout

    def test_empty_when_no_triggers(self):
        layout = self._layout_target()
        steps = build_thumb_path_list(
            left=_thumb(),
            right=_thumb(),
            layout=layout,
            source_layer=0,
            keymap_spacing=18,
        )
        assert steps == []

    def test_right_thumb_outward_keys_come_first_with_direction_right(self):
        layout = self._layout_target()
        right = _thumb(
            double_down_key=_key(layer_switch=1),
            pad_key=_key(layer_switch=2),
        )
        steps = build_thumb_path_list(
            left=_thumb(),
            right=right,
            layout=layout,
            source_layer=0,
            keymap_spacing=18,
        )
        assert [s.key.layer_switch for s in steps] == [1, 2]
        assert all(s.direction == Direction.RIGHT for s in steps)

    def test_lt_up_goes_left_when_lt_down_also_triggers(self):
        layout = self._layout_target()
        left = _thumb(up_key=_key(layer_switch=1), down_key=_key(layer_switch=2))
        steps = build_thumb_path_list(
            left=left,
            right=_thumb(),
            layout=layout,
            source_layer=0,
            keymap_spacing=18,
        )
        # LT_Down is in the DOWN priority group; LT_Up is the special-case at the end with LEFT.
        directions = [s.direction for s in steps]
        assert Direction.DOWN in directions
        assert Direction.LEFT in directions
        # LT_Up (target_layer=1) is direction LEFT.
        lt_up_step = next(s for s in steps if s.key.layer_switch == 1)
        assert lt_up_step.direction == Direction.LEFT

    def test_lt_up_goes_down_when_lt_down_does_not_trigger(self):
        layout = self._layout_target()
        left = _thumb(up_key=_key(layer_switch=1))
        steps = build_thumb_path_list(
            left=left,
            right=_thumb(),
            layout=layout,
            source_layer=0,
            keymap_spacing=18,
        )
        assert len(steps) == 1
        assert steps[0].direction == Direction.DOWN

    def test_self_referential_trigger_is_skipped(self):
        layout = self._layout_target()
        right = _thumb(pad_key=_key(layer_switch=0))  # source_layer=0, so this is self-ref
        steps = build_thumb_path_list(
            left=_thumb(),
            right=right,
            layout=layout,
            source_layer=0,
            keymap_spacing=18,
        )
        assert steps == []


class TestSetInitialMoveTo:
    def test_up_starts_at_indicator_top_center(self):
        step = _step(Direction.UP, (10, 20, 6, 8))
        set_initial_moveto(step)
        # current_point = (x + w/2, y) = (13, 20)
        assert step.current_point == (13.0, 20.0)

    def test_right_starts_at_indicator_right_middle(self):
        step = _step(Direction.RIGHT, (10, 20, 6, 8))
        set_initial_moveto(step)
        # current_point = (x + w, y + h/2) = (16, 24)
        assert step.current_point == (16.0, 24.0)

    def test_down_starts_at_indicator_bottom_center(self):
        step = _step(Direction.DOWN, (10, 20, 6, 8))
        set_initial_moveto(step)
        # current_point = (x + w/2, y + h) = (13, 28)
        assert step.current_point == (13.0, 28.0)

    def test_left_starts_at_indicator_left_middle(self):
        step = _step(Direction.LEFT, (10, 20, 6, 8))
        set_initial_moveto(step)
        # current_point = (x, y + h/2) = (10, 24)
        assert step.current_point == (10.0, 24.0)
