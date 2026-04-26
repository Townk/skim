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
    phase1_redirect_left_to_down,
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

    def test_steps_carry_key_origin_attr(self):
        layout = self._layout_target()
        right = _thumb(double_down_key=_key(layer_switch=1))
        steps = build_thumb_path_list(
            left=_thumb(),
            right=right,
            layout=layout,
            source_layer=0,
            keymap_spacing=18,
        )
        assert steps[0].key_origin_attr == "double_down_key"

    def test_lt_up_special_case_carries_up_key_origin_attr(self):
        layout = self._layout_target()
        left = _thumb(up_key=_key(layer_switch=1))
        steps = build_thumb_path_list(
            left=left,
            right=_thumb(),
            layout=layout,
            source_layer=0,
            keymap_spacing=18,
        )
        assert steps[0].key_origin_attr == "up_key"


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


class TestPhase1RedirectLeftToDown:
    def test_lt_up_extends_west_then_marks_down(self):
        # LT_Down indicator at x=100, y=200; LT_Up indicator at x=80, y=180.
        lt_down = _step(Direction.DOWN, (100, 200, 8, 8))
        lt_up = _step(Direction.LEFT, (80, 180, 8, 8))
        set_initial_moveto(lt_down)
        set_initial_moveto(lt_up)
        path_list = [lt_down, lt_up]

        phase1_redirect_left_to_down(path_list, keymap_spacing=18)

        # LT_Down's last_point.x is the indicator center = 100 + 4 = 104 (DOWN moveTo).
        # New LT_Up X = 104 - 18 = 86. LT_Up's path now extends to that X.
        assert lt_up.current_point == (86.0, lt_up.current_point[1])
        assert lt_up.direction == Direction.DOWN

    def test_no_op_when_no_left_paths(self):
        step = _step(Direction.UP, (10, 20, 6, 8))
        set_initial_moveto(step)
        path_list = [step]
        # No LEFT-direction paths, no LT_Down dependency
        phase1_redirect_left_to_down(path_list, keymap_spacing=18)
        assert step.direction == Direction.UP

    def test_multiple_left_steps_all_redirect_to_same_column(self):
        # Synthetic case: two LEFT-direction steps + one DOWN partner.
        # All LEFT steps should be redirected to the same new_x and direction DOWN.
        partner = _step(Direction.DOWN, (100, 200, 8, 8))
        set_initial_moveto(partner)
        partner.key_origin_attr = "down_key"
        a = _step(Direction.LEFT, (60, 180, 8, 8))
        b = _step(Direction.LEFT, (40, 160, 8, 8))
        set_initial_moveto(a)
        set_initial_moveto(b)
        path_list = [partner, a, b]

        phase1_redirect_left_to_down(path_list, keymap_spacing=18)

        # partner.current_point[0] = 100 + 8/2 = 104; new_x = 104 - 18 = 86.
        assert a.current_point[0] == 86.0
        assert b.current_point[0] == 86.0
        assert a.direction == Direction.DOWN
        assert b.direction == Direction.DOWN

    def test_annotated_partner_wins_over_first_down_step(self):
        # Two DOWN steps, only the second is annotated as the LT_Down partner.
        # The redirect should follow the annotated partner's column, not the first.
        knuckle = _step(Direction.DOWN, (200, 200, 8, 8))
        set_initial_moveto(knuckle)
        knuckle.key_origin_attr = "knuckle_key"
        lt_down = _step(Direction.DOWN, (100, 200, 8, 8))
        set_initial_moveto(lt_down)
        lt_down.key_origin_attr = "down_key"
        lt_up = _step(Direction.LEFT, (80, 180, 8, 8))
        set_initial_moveto(lt_up)
        path_list = [knuckle, lt_down, lt_up]

        phase1_redirect_left_to_down(path_list, keymap_spacing=18)

        # Annotated partner is lt_down at x = 100 + 8/2 = 104; new_x = 104 - 18 = 86.
        # If the fallback were used, knuckle's x = 200 + 8/2 = 204, new_x = 186.
        assert lt_up.current_point[0] == 86.0
        assert lt_up.direction == Direction.DOWN
