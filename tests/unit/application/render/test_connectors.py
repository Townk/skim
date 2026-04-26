# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.connectors module."""

from unittest.mock import MagicMock

import pytest

from skim.application.render.connectors import (
    ConnectorStep,
    Direction,
    allocate_columns,
    build_thumb_path_list,
    phase1_down_to_right,
    phase1_redirect_left_to_down,
    phase1_up_to_right,
    phase2_route_to_targets,
    route_thumb_connectors,
    set_initial_moveto,
    target_point_for,
)
from skim.data.keyboard import ThumbCluster
from skim.domain import SvalboardTargetKey


def _key(label="K", layer_switch=None):
    return SvalboardTargetKey(label=label, layer_switch=layer_switch)


def _step(direction, indicator_rect):
    """Make a step carrying the given indicator rect."""
    step = ConnectorStep(
        key=MagicMock(),
        direction=direction,
        target_point=(0.0, 0.0),
        target_layer=0,
        indicator_rect=indicator_rect,
    )
    return step


def _step_at(current_y, target_y):
    s = ConnectorStep(
        key=MagicMock(),
        direction=Direction.RIGHT,
        target_point=(0.0, target_y),
        target_layer=0,
    )
    s.current_point = (0.0, current_y)
    return s


def set_initial_moveto_at(step, x, y):
    """Test helper: place the step's initial moveTo at an explicit (x, y)."""
    step.path.M(x, y)
    step.current_point = (x, y)


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

    def test_lt_up_falls_back_to_down_when_lt_down_target_is_self_referential(self):
        # Source layer 0; LT_Down targets layer 0 (self-ref → skipped);
        # LT_Up targets layer 1 (valid). LT_Up should route DOWN, not LEFT,
        # because LT_Down is not actually in the priority list.
        layout = self._layout_target()
        left = _thumb(
            up_key=_key(layer_switch=1),
            down_key=_key(layer_switch=0),  # self-ref
        )
        steps = build_thumb_path_list(
            left=left,
            right=_thumb(),
            layout=layout,
            source_layer=0,
            keymap_spacing=18,
        )
        assert len(steps) == 1
        assert steps[0].direction == Direction.DOWN  # not LEFT
        assert steps[0].key_origin_attr == "up_key"

    def test_lt_up_falls_back_to_down_when_lt_down_target_out_of_range(self):
        # LT_Down's layer_switch is out of range (no such row); skipped.
        # LT_Up must default to DOWN.
        layout = self._layout_target()  # 3 layers
        left = _thumb(
            up_key=_key(layer_switch=1),
            down_key=_key(layer_switch=99),  # out of range
        )
        steps = build_thumb_path_list(
            left=left,
            right=_thumb(),
            layout=layout,
            source_layer=0,
            keymap_spacing=18,
        )
        assert len(steps) == 1
        assert steps[0].direction == Direction.DOWN


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


class TestPhase1UpToRight:
    def test_each_up_path_takes_progressively_higher_lane(self):
        a = _step(Direction.UP, (10, 100, 6, 8))
        set_initial_moveto(a)
        b = _step(Direction.UP, (20, 110, 6, 8))
        set_initial_moveto(b)
        path_list = [a, b]
        cluster_top = 90
        extra = phase1_up_to_right(path_list, cluster_top=cluster_top, min_y=100, keymap_spacing=18)
        # First UP lane: min(90 - 18, 100 - 18) = min(72, 82) = 72.
        # Second UP lane: 72 - 18 = 54.
        assert a.current_point == (13.0, 72.0)
        assert b.current_point == (23.0, 54.0)
        assert a.direction == Direction.RIGHT
        assert b.direction == Direction.RIGHT
        # extra_top_padding = (N + 1) * keymap_spacing = (2 + 1) * 18 = 54
        assert extra == 54.0

    def test_returns_zero_when_no_up_paths(self):
        assert phase1_up_to_right([], cluster_top=0, min_y=0, keymap_spacing=18) == 0.0

    def test_only_up_steps_are_processed(self):
        up = _step(Direction.UP, (10, 100, 6, 8))
        set_initial_moveto(up)
        down = _step(Direction.DOWN, (20, 100, 6, 8))
        set_initial_moveto(down)
        right = _step(Direction.RIGHT, (30, 100, 6, 8))
        set_initial_moveto(right)
        # Snapshot non-UP state before the call
        down_before = (down.current_point, down.direction)
        right_before = (right.current_point, right.direction)

        phase1_up_to_right([up, down, right], cluster_top=90, min_y=100, keymap_spacing=18)

        assert up.direction == Direction.RIGHT
        assert (down.current_point, down.direction) == down_before
        assert (right.current_point, right.direction) == right_before


class TestPhase1DownToRight:
    def test_each_down_path_takes_progressively_lower_lane(self):
        a = _step(Direction.DOWN, (10, 100, 6, 8))
        set_initial_moveto(a)
        b = _step(Direction.DOWN, (20, 110, 6, 8))
        set_initial_moveto(b)
        path_list = [a, b]
        cluster_bottom = 130
        extra = phase1_down_to_right(
            path_list, cluster_bottom=cluster_bottom, max_y=118, keymap_spacing=18
        )
        # First DOWN lane: max(130 + 18, 118 + 18) = max(148, 136) = 148.
        # Second DOWN lane: 148 + 18 = 166.
        assert a.current_point == (13.0, 148.0)
        assert b.current_point == (23.0, 166.0)
        assert a.direction == Direction.RIGHT
        assert b.direction == Direction.RIGHT
        # extra_bottom_padding = (N + 1) * keymap_spacing = 54
        assert extra == 54.0

    def test_returns_zero_when_no_down_paths(self):
        assert phase1_down_to_right([], cluster_bottom=0, max_y=0, keymap_spacing=18) == 0.0

    def test_only_down_steps_are_processed(self):
        up = _step(Direction.UP, (10, 100, 6, 8))
        set_initial_moveto(up)
        down = _step(Direction.DOWN, (20, 100, 6, 8))
        set_initial_moveto(down)
        right = _step(Direction.RIGHT, (30, 100, 6, 8))
        set_initial_moveto(right)
        up_before = (up.current_point, up.direction)
        right_before = (right.current_point, right.direction)

        phase1_down_to_right([up, down, right], cluster_bottom=130, max_y=118, keymap_spacing=18)

        assert down.direction == Direction.RIGHT
        assert (up.current_point, up.direction) == up_before
        assert (right.current_point, right.direction) == right_before


class TestAllocateColumns:
    def test_non_overlapping_spans_share_a_column(self):
        # Span [10, 50] and span [60, 100] don't overlap; both go in column 0.
        a = _step_at(50, 10)  # span 10..50
        b = _step_at(60, 100)  # span 60..100
        used = allocate_columns([a, b], first_column_x=200, keymap_spacing=18)
        assert a.col_x == 200.0
        assert b.col_x == 200.0
        assert used == 1  # one column used

    def test_overlapping_spans_take_separate_columns(self):
        a = _step_at(50, 10)  # span 10..50
        b = _step_at(40, 80)  # span 40..80; overlaps with a (40..50)
        used = allocate_columns([a, b], first_column_x=200, keymap_spacing=18)
        assert a.col_x == 200.0
        assert b.col_x == 218.0
        assert used == 2

    def test_first_path_always_at_first_column_x(self):
        a = _step_at(10, 50)
        used = allocate_columns([a], first_column_x=200, keymap_spacing=18)
        assert a.col_x == 200.0
        assert used == 1

    def test_empty_path_list_returns_zero(self):
        assert allocate_columns([], first_column_x=200, keymap_spacing=18) == 0

    def test_three_paths_with_mixed_overlap_use_leftmost_fit(self):
        # A spans 10..50; B spans 40..80 (overlaps A so B -> col 1);
        # C spans 60..100 (overlaps B in col 1 but NOT A in col 0; so C -> col 0).
        a = _step_at(50, 10)
        b = _step_at(40, 80)
        c = _step_at(60, 100)
        used = allocate_columns([a, b, c], first_column_x=200, keymap_spacing=18)
        assert a.col_x == 200.0  # col 0
        assert b.col_x == 218.0  # col 1
        assert c.col_x == 200.0  # col 0 (greedy leftmost fits)
        assert used == 2


class TestPhase2RouteToTargets:
    def test_single_path_completes_to_target(self):
        a = _step_at(50, 100)
        set_initial_moveto_at(a, 10, 50)
        a.col_x = 200
        a.target_point = (200.0, 100.0)
        a.target_layer = 1
        phase2_route_to_targets([a])
        # Path goes:
        #   M 10 50 -> L 200 50 (east) -> L 200 100 (drop) -> L 200 100 (target, same point — implicit)
        # current_point ends at target_point (200, 100).
        assert a.current_point == (200.0, 100.0)
        assert a.direction == Direction.LEFT

    def test_two_paths_to_same_target_only_outermost_emits_final_segment(self):
        a = _step_at(50, 100)
        a.col_x = 200
        a.target_point = (200.0, 100.0)
        a.target_layer = 1
        b = _step_at(60, 100)
        b.col_x = 218
        b.target_point = (200.0, 100.0)
        b.target_layer = 1
        phase2_route_to_targets([a, b])
        # 'a' is innermost (col_x 200 = target.x). It ends at (200, 100).
        # 'b' is outermost (col_x 218). It ends at target_point (200, 100) after a final LEFT segment.
        assert a.current_point == (200.0, 100.0)
        assert b.current_point == (200.0, 100.0)

    def test_empty_path_list_is_noop(self):
        # Should not raise; no observable side effects.
        phase2_route_to_targets([])

    def test_multiple_target_layers_pick_outermost_per_group(self):
        # Layer 1 group: a (col_x=200), b (col_x=218). Outermost = b.
        # Layer 2 group: c (col_x=200), d (col_x=236). Outermost = d.
        a = _step_at(50, 100)
        a.col_x = 200
        a.target_point = (200.0, 100.0)
        a.target_layer = 1
        b = _step_at(60, 100)
        b.col_x = 218
        b.target_point = (200.0, 100.0)
        b.target_layer = 1
        c = _step_at(50, 300)
        c.col_x = 200
        c.target_point = (200.0, 300.0)
        c.target_layer = 2
        d = _step_at(70, 300)
        d.col_x = 236
        d.target_point = (200.0, 300.0)
        d.target_layer = 2

        phase2_route_to_targets([a, b, c, d])

        # All steps reach their target_point Y after the drop.
        # Outermost per group reaches the target X via the final LEFT segment.
        assert b.current_point == (200.0, 100.0)
        assert d.current_point == (200.0, 300.0)
        # Non-outermost stay at their col_x after the drop (no final segment ran for them).
        assert a.current_point == (200.0, 100.0)  # already at target_x because col_x == target_x
        assert c.current_point == (200.0, 300.0)  # same

    def test_outermost_wins_regardless_of_insertion_order(self):
        # Three paths to the same target; the MIDDLE col_x is appended last.
        # If the implementation used "last appended wins" instead of max(col_x),
        # this test would assert the wrong path got the final segment.
        inner = _step_at(50, 100)
        inner.col_x = 150
        inner.target_point = (100.0, 100.0)
        inner.target_layer = 1
        outer = _step_at(50, 100)
        outer.col_x = 250
        outer.target_point = (100.0, 100.0)
        outer.target_layer = 1
        middle = _step_at(50, 100)
        middle.col_x = 200
        middle.target_point = (100.0, 100.0)
        middle.target_layer = 1

        phase2_route_to_targets([inner, outer, middle])

        # outer is outermost (col_x = 250). Its current_point should be the target_point.
        assert outer.current_point == (100.0, 100.0)
        # inner and middle are NOT outermost — they end at (their col_x, target_y), not target_point.
        assert inner.current_point == (150.0, 100.0)
        assert middle.current_point == (200.0, 100.0)


class TestRouteThumbConnectors:
    def _layout(self):
        layout = MagicMock()
        layout.layer_row_y_positions = [100, 200, 300]
        layout.layer_row_heights = [50, 50, 50]
        layout.layer_row_bounding_box = lambda i: (200, layout.layer_row_y_positions[i], 600, 50)
        layout.thumb_cluster_y_bounds = lambda: (300.0, 400.0)
        return layout

    def test_empty_when_no_triggers(self):
        result = route_thumb_connectors(
            left=_thumb(),
            right=_thumb(),
            layout=self._layout(),
            source_layer=0,
            keymap_spacing=18,
            indicator_rects={},
        )
        assert result.paths == []
        assert result.extra_top_padding == 0
        assert result.extra_bottom_padding == 0
        assert result.extra_right_padding == 0

    def test_single_right_trigger_produces_one_path(self):
        # RT_DD triggers, target layer 1. Source layer 0.
        # Direction RIGHT, no Phase 1 escape needed (already RIGHT).
        # Phase 2 allocates one column.
        rt_dd = _key(layer_switch=1)
        right = _thumb(double_down_key=rt_dd)
        # Indicator rect for RT_DD at (700, 350, 6, 6) — fictional but plausible.
        indicator_rects = {rt_dd: (700.0, 350.0, 6.0, 6.0)}
        result = route_thumb_connectors(
            left=_thumb(),
            right=right,
            layout=self._layout(),
            source_layer=0,
            keymap_spacing=18,
            indicator_rects=indicator_rects,
        )
        assert len(result.paths) == 1
        # No UP/DOWN/LEFT redirects → no top/bottom padding.
        assert result.extra_top_padding == 0
        assert result.extra_bottom_padding == 0
        # Phase 2 used one column → (cols_used + 1) * keymap_spacing of right padding.
        assert result.extra_right_padding == 36.0

    def test_self_referential_trigger_skipped_returns_empty(self):
        rt_dd = _key(layer_switch=0)  # source_layer=0, so self-ref
        right = _thumb(double_down_key=rt_dd)
        result = route_thumb_connectors(
            left=_thumb(),
            right=right,
            layout=self._layout(),
            source_layer=0,
            keymap_spacing=18,
            indicator_rects={rt_dd: (700.0, 350.0, 6.0, 6.0)},
        )
        assert result.paths == []

    def test_up_direction_trigger_produces_top_padding(self):
        # RT_Nail triggers (UP direction in _THUMB_PRIORITY).
        rt_nail = _key(layer_switch=1)
        right = _thumb(nail_key=rt_nail)
        indicator_rects = {rt_nail: (700.0, 320.0, 6.0, 6.0)}
        result = route_thumb_connectors(
            left=_thumb(),
            right=right,
            layout=self._layout(),
            source_layer=0,
            keymap_spacing=18,
            indicator_rects=indicator_rects,
        )
        assert len(result.paths) == 1
        # 1 UP step → extra_top_padding = (1+1) * 18 = 36.
        assert result.extra_top_padding == 36.0
        assert result.extra_bottom_padding == 0
        assert result.extra_right_padding == 36.0

    def test_down_direction_trigger_produces_bottom_padding(self):
        # RT_Knuckle triggers (DOWN direction in _THUMB_PRIORITY).
        rt_knuckle = _key(layer_switch=1)
        right = _thumb(knuckle_key=rt_knuckle)
        indicator_rects = {rt_knuckle: (700.0, 380.0, 6.0, 6.0)}
        result = route_thumb_connectors(
            left=_thumb(),
            right=right,
            layout=self._layout(),
            source_layer=0,
            keymap_spacing=18,
            indicator_rects=indicator_rects,
        )
        assert len(result.paths) == 1
        assert result.extra_top_padding == 0
        # 1 DOWN step → extra_bottom_padding = (1+1) * 18 = 36.
        assert result.extra_bottom_padding == 36.0
        assert result.extra_right_padding == 36.0

    def test_lt_up_special_case_end_to_end(self):
        # LT_Up + LT_Down both trigger → LT_Up gets LEFT direction,
        # gets redirected to DOWN in Phase 1, then DOWN→RIGHT in Phase 1.
        # LT_Down stays DOWN, also DOWN→RIGHT in Phase 1.
        lt_up = _key(layer_switch=1)
        lt_down = _key(layer_switch=2)
        left = _thumb(up_key=lt_up, down_key=lt_down)
        indicator_rects = {
            lt_up: (200.0, 320.0, 6.0, 6.0),
            lt_down: (220.0, 360.0, 6.0, 6.0),
        }
        result = route_thumb_connectors(
            left=left,
            right=_thumb(),
            layout=self._layout(),
            source_layer=0,
            keymap_spacing=18,
            indicator_rects=indicator_rects,
        )
        # Two paths produced; both end up DOWN→RIGHT after Phase 1.
        assert len(result.paths) == 2
        # Two DOWN steps after the LEFT→DOWN redirect → extra_bottom = (2+1)*18 = 54.
        assert result.extra_bottom_padding == 54.0
        # No UP steps → extra_top = 0.
        assert result.extra_top_padding == 0
        # Two distinct target_layers, but they may share a column (depends on Y spans).
        # We don't assert exact column count — just that the algorithm produced output.

    def test_paths_carry_target_layer(self):
        rt_dd = _key(layer_switch=1)
        right = _thumb(double_down_key=rt_dd)
        indicator_rects = {rt_dd: (700.0, 350.0, 6.0, 6.0)}
        result = route_thumb_connectors(
            left=_thumb(),
            right=right,
            layout=self._layout(),
            source_layer=0,
            keymap_spacing=18,
            indicator_rects=indicator_rects,
        )
        assert len(result.paths) == 1
        path, target_layer = result.paths[0]
        assert target_layer == 1

    def test_innermost_path_has_keymap_spacing_left_segment_to_target(self):
        # A single RIGHT-direction trigger lands its drop at first_column_x =
        # target_point.x + keymap_spacing. The multi-target merge then emits
        # a final LEFT to target_point, giving a real keymap_spacing-long
        # final segment instead of a degenerate (zero-length) one.
        rt_dd = _key(layer_switch=1)
        right = _thumb(double_down_key=rt_dd)
        indicator_rects = {rt_dd: (700.0, 350.0, 6.0, 6.0)}
        result = route_thumb_connectors(
            left=_thumb(),
            right=right,
            layout=self._layout(),
            source_layer=0,
            keymap_spacing=18,
            indicator_rects=indicator_rects,
        )
        assert len(result.paths) == 1
        path, _target_layer = result.paths[0]
        # path.args["d"] is a string: "M{x},{y} L{x},{y} L{x},{y} ...".
        # Parse the last command's coordinates and confirm they match
        # target_point: (200 + 600 + 18, 225) = (818, 225).
        d_str = path.args["d"]
        last_cmd = d_str.split(" ")[-1]
        # Each command is "L{x},{y}" or "M{x},{y}".
        coords = last_cmd[1:].split(",")
        last_x = float(coords[0])
        last_y = float(coords[1])
        assert last_x == 818.0
        assert last_y == 225.0

    def test_missing_indicator_rect_raises_clear_error(self):
        # Triggering key NOT included in indicator_rects map.
        rt_dd = _key(layer_switch=1)
        right = _thumb(double_down_key=rt_dd)
        with pytest.raises(ValueError, match="indicator_rects missing entry"):
            route_thumb_connectors(
                left=_thumb(),
                right=right,
                layout=self._layout(),
                source_layer=0,
                keymap_spacing=18,
                indicator_rects={},  # empty — RT_DD's rect is missing
            )
