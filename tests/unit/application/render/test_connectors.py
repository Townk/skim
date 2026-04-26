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
    OverviewLayerSource,
    ThumbSource,
    allocate_columns,
    build_finger_path_list_for_cluster,
    build_finger_path_list_for_layer,
    build_thumb_path_list,
    phase1_down_to_right,
    phase1_redirect_left_to_down,
    phase1_redirect_right_to_down,
    phase1_up_to_right,
    phase2_route_to_targets,
    route_thumb_connectors,
    set_initial_moveto,
    target_point_for,
)
from skim.data.keyboard import FingerCluster, SplitSide, ThumbCluster
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


def _finger(**overrides):
    """Build a FingerCluster with all keys defaulting to no layer_switch."""
    base = {
        name: _key()
        for name in (
            "center_key",
            "north_key",
            "east_key",
            "south_key",
            "west_key",
            "double_south_key",
        )
    }
    base.update(overrides)
    return FingerCluster(**base)


def _side(*, index=None, middle=None, ring=None, pinky=None):
    """Build a SplitSide with empty FingerClusters by default."""
    return SplitSide(
        index=index or _finger(),
        middle=middle or _finger(),
        ring=ring or _finger(),
        pinky=pinky or _finger(),
        thumb=_thumb(),  # not used by finger routing — placeholder
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

    def test_default_source_cluster_attr_is_empty(self):
        step = ConnectorStep(
            key=None,
            direction=Direction.UP,
            target_point=(0.0, 0.0),
            target_layer=0,
        )
        assert step.source_cluster_attr == ""


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
        # Match the existing bbox-center landing Y (row_y + 25) so existing
        # assertions still pass; tests that need a different value override
        # this lambda explicitly.
        layout.layer_row_target_y = lambda idx: layout.layer_row_y_positions[idx] + 25
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

    def test_target_y_uses_layer_row_target_y_not_bbox_center(self):
        layout = self._layout()
        # Override target_y to a sentinel that's NOT the bbox center.
        layout.layer_row_target_y = lambda _idx: 999.0
        point = target_point_for(layout, target_layer=1, source_layer=0, keymap_spacing=18)
        assert point is not None
        assert point[1] == 999.0


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
        layout.layer_row_target_y = lambda idx: layout.layer_row_y_positions[idx] + 25
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


class TestPhase1RedirectRightToDown:
    def test_south_extends_east_then_marks_down(self):
        # S+DS pair in the same cluster.
        # South: indicator at (100, 200, 8, 8), direction=RIGHT initially.
        # DS:    indicator at (100, 220, 8, 8), direction=DOWN.
        # After set_initial_moveto:
        #   south.current_point = (rx + rw, ry + rh/2) — RIGHT moveTo edge.
        #     For (100, 200, 8, 8): (108, 204).
        #   ds.current_point = (rx + rw/2, ry + rh) — DOWN moveTo edge.
        #     For (100, 220, 8, 8): (104, 228).
        # Redirect: new_x = ds.current_point[0] + spacing = 104 + 18 = 122.
        # South path extends to (122, south.current_point[1] = 204), direction = DOWN.
        south = _step(Direction.RIGHT, (100, 200, 8, 8))
        south.key_origin_attr = "south_key"
        south.source_cluster_attr = "left.index"
        ds = _step(Direction.DOWN, (100, 220, 8, 8))
        ds.key_origin_attr = "double_south_key"
        ds.source_cluster_attr = "left.index"
        set_initial_moveto(south)
        set_initial_moveto(ds)

        phase1_redirect_right_to_down([south, ds], keymap_spacing=18)

        assert south.current_point == (122.0, 204.0)
        assert south.direction == Direction.DOWN
        # DS unchanged.
        assert ds.direction == Direction.DOWN
        assert ds.current_point == (104.0, 228.0)

    def test_no_op_when_no_right_paths(self):
        a = _step(Direction.UP, (10, 100, 6, 8))
        a.source_cluster_attr = "left.index"
        b = _step(Direction.DOWN, (20, 110, 6, 8))
        b.source_cluster_attr = "left.index"
        b.key_origin_attr = "south_key"
        set_initial_moveto(a)
        set_initial_moveto(b)

        phase1_redirect_right_to_down([a, b], keymap_spacing=18)

        assert a.direction == Direction.UP
        assert b.direction == Direction.DOWN

    def test_partner_search_scoped_to_same_cluster(self):
        # South in left.index has its DS partner in left.index, not left.middle.
        south = _step(Direction.RIGHT, (100, 200, 8, 8))
        south.key_origin_attr = "south_key"
        south.source_cluster_attr = "left.index"
        wrong_ds = _step(Direction.DOWN, (500, 220, 8, 8))
        wrong_ds.key_origin_attr = "double_south_key"
        wrong_ds.source_cluster_attr = "left.middle"
        right_ds = _step(Direction.DOWN, (100, 220, 8, 8))
        right_ds.key_origin_attr = "double_south_key"
        right_ds.source_cluster_attr = "left.index"
        set_initial_moveto(south)
        set_initial_moveto(wrong_ds)
        set_initial_moveto(right_ds)

        phase1_redirect_right_to_down([south, wrong_ds, right_ds], keymap_spacing=18)

        # Should redirect against right_ds.current_point[0] = 104, not wrong_ds.current_point[0] = 504.
        assert south.current_point[0] == 122.0
        assert south.direction == Direction.DOWN

    def test_no_partner_leaves_step_unchanged(self):
        # South is RIGHT, but no DS step exists in path_list (malformed input).
        south = _step(Direction.RIGHT, (100, 200, 8, 8))
        south.key_origin_attr = "south_key"
        south.source_cluster_attr = "left.index"
        set_initial_moveto(south)

        phase1_redirect_right_to_down([south], keymap_spacing=18)

        assert south.direction == Direction.RIGHT
        # current_point unchanged from set_initial_moveto.
        assert south.current_point == (108.0, 204.0)

    def test_multiple_right_steps_in_different_clusters(self):
        # Two S+DS pairs in two different clusters.
        s1 = _step(Direction.RIGHT, (100, 200, 8, 8))
        s1.key_origin_attr = "south_key"
        s1.source_cluster_attr = "left.index"
        ds1 = _step(Direction.DOWN, (100, 220, 8, 8))
        ds1.key_origin_attr = "double_south_key"
        ds1.source_cluster_attr = "left.index"
        s2 = _step(Direction.RIGHT, (300, 200, 8, 8))
        s2.key_origin_attr = "south_key"
        s2.source_cluster_attr = "left.middle"
        ds2 = _step(Direction.DOWN, (300, 220, 8, 8))
        ds2.key_origin_attr = "double_south_key"
        ds2.source_cluster_attr = "left.middle"
        for s in (s1, ds1, s2, ds2):
            set_initial_moveto(s)

        phase1_redirect_right_to_down([s1, ds1, s2, ds2], keymap_spacing=18)

        assert s1.direction == Direction.DOWN
        assert s2.direction == Direction.DOWN
        # Each redirected against its own cluster's DS.
        assert s1.current_point[0] == ds1.current_point[0] + 18  # 104 + 18 = 122
        assert s2.current_point[0] == ds2.current_point[0] + 18  # 304 + 18 = 322


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
        # extra_top_padding = N * keymap_spacing = 2 * 18 = 36
        assert extra == 36.0

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
        # extra_bottom_padding = (N + 0.5) * keymap_spacing = 2.5 * 18 = 45
        assert extra == 45.0

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
        layout.layer_row_target_y = lambda i: layout.layer_row_y_positions[i] + 25
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
        # 1 UP step → extra_top_padding = 1 * 18 = 18.
        assert result.extra_top_padding == 18.0
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
        # 1 DOWN step → extra_bottom_padding = (1 + 0.5) * 18 = 27.
        assert result.extra_bottom_padding == 27.0
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
        # Two DOWN steps after the LEFT→DOWN redirect → extra_bottom = (2 + 0.5)*18 = 45.
        assert result.extra_bottom_padding == 45.0
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


class TestBuildFingerPathListForCluster:
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
        layout.layer_row_target_y = lambda idx: layout.layer_row_y_positions[idx] + 25
        return layout

    def test_empty_cluster_produces_no_steps(self):
        layout = self._layout_target()
        steps = build_finger_path_list_for_cluster(
            cluster=_finger(),
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert steps == []

    def test_r4_priority_order_and_directions(self):
        # R4: N, W, S, DS, E, C → RIGHT, RIGHT, RIGHT, RIGHT, UP, DOWN
        layout = self._layout_target()
        cluster = _finger(
            north_key=_key(layer_switch=1),
            west_key=_key(layer_switch=2),
            south_key=_key(layer_switch=1),
            double_south_key=_key(layer_switch=2),
            east_key=_key(layer_switch=1),
            center_key=_key(layer_switch=2),
        )
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=True,
            cluster_attr="right.pinky",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        attrs = [s.key_origin_attr for s in steps]
        directions = [s.direction for s in steps]
        assert attrs == [
            "north_key",
            "west_key",
            "south_key",
            "double_south_key",
            "east_key",
            "center_key",
        ]
        assert directions == [
            Direction.RIGHT,
            Direction.RIGHT,
            Direction.RIGHT,
            Direction.RIGHT,
            Direction.UP,
            Direction.DOWN,
        ]

    def test_non_r4_priority_order_and_directions(self):
        # Non-R4 base table: W, N, E → UP; S, DS, C → DOWN.
        # When both S and DS trigger (as below), the S+DS special case overrides
        # south's direction to RIGHT (Phase 1 sub-step 2.1 redirects it past DS's
        # drop column). This test exercises both the priority order AND that
        # interaction in one go.
        layout = self._layout_target()
        cluster = _finger(
            west_key=_key(layer_switch=1),
            north_key=_key(layer_switch=2),
            east_key=_key(layer_switch=1),
            south_key=_key(layer_switch=2),
            double_south_key=_key(layer_switch=1),
            center_key=_key(layer_switch=2),
        )
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        attrs = [s.key_origin_attr for s in steps]
        directions = [s.direction for s in steps]
        assert attrs == [
            "west_key",
            "north_key",
            "east_key",
            "south_key",
            "double_south_key",
            "center_key",
        ]
        assert directions == [
            Direction.UP,
            Direction.UP,
            Direction.UP,
            Direction.RIGHT,  # S+DS special case overrides south's DOWN → RIGHT
            Direction.DOWN,
            Direction.DOWN,
        ]

    def test_s_and_ds_double_trigger_in_non_r4_makes_south_right(self):
        # When both south and DS trigger in a non-R4 cluster, south's initial
        # direction is RIGHT (S+DS special case).
        layout = self._layout_target()
        cluster = _finger(
            south_key=_key(layer_switch=1),
            double_south_key=_key(layer_switch=2),
        )
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        south_step = next(s for s in steps if s.key_origin_attr == "south_key")
        ds_step = next(s for s in steps if s.key_origin_attr == "double_south_key")
        assert south_step.direction == Direction.RIGHT
        assert ds_step.direction == Direction.DOWN

    def test_only_south_triggers_in_non_r4_keeps_south_down(self):
        layout = self._layout_target()
        cluster = _finger(south_key=_key(layer_switch=1))
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert len(steps) == 1
        assert steps[0].direction == Direction.DOWN

    def test_only_ds_triggers_in_non_r4_keeps_ds_down(self):
        layout = self._layout_target()
        cluster = _finger(double_south_key=_key(layer_switch=1))
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert len(steps) == 1
        assert steps[0].direction == Direction.DOWN

    def test_r4_with_s_and_ds_double_trigger_keeps_both_right(self):
        # R4's table already has S/DS as RIGHT — no special case applies.
        layout = self._layout_target()
        cluster = _finger(
            south_key=_key(layer_switch=1),
            double_south_key=_key(layer_switch=2),
        )
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=True,
            cluster_attr="right.pinky",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        directions = {s.key_origin_attr: s.direction for s in steps}
        assert directions["south_key"] == Direction.RIGHT
        assert directions["double_south_key"] == Direction.RIGHT

    def test_self_referential_trigger_skipped(self):
        layout = self._layout_target()
        cluster = _finger(north_key=_key(layer_switch=0))  # source=0, target=0
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert steps == []

    def test_steps_carry_source_cluster_attr(self):
        layout = self._layout_target()
        cluster = _finger(north_key=_key(layer_switch=1))
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert steps[0].source_cluster_attr == "left.index"


class TestBuildFingerPathListForLayer:
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
        layout.layer_row_target_y = lambda idx: layout.layer_row_y_positions[idx] + 25
        return layout

    def test_empty_layer_produces_no_steps(self):
        layout = self._layout_target()
        steps = build_finger_path_list_for_layer(
            left=_side(),
            right=_side(),
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert steps == []

    def test_cluster_iteration_order_is_l4_l3_l2_l1_r1_r2_r3_r4(self):
        # Trigger one key in each cluster so we can recover the order from
        # the resulting source_cluster_attr sequence.
        layout = self._layout_target()
        l1 = _finger(north_key=_key(layer_switch=1))
        l2 = _finger(north_key=_key(layer_switch=1))
        l3 = _finger(north_key=_key(layer_switch=1))
        l4 = _finger(north_key=_key(layer_switch=1))
        r1 = _finger(north_key=_key(layer_switch=1))
        r2 = _finger(north_key=_key(layer_switch=1))
        r3 = _finger(north_key=_key(layer_switch=1))
        r4 = _finger(north_key=_key(layer_switch=1))

        steps = build_finger_path_list_for_layer(
            left=_side(index=l1, middle=l2, ring=l3, pinky=l4),
            right=_side(index=r1, middle=r2, ring=r3, pinky=r4),
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        cluster_order = [s.source_cluster_attr for s in steps]
        assert cluster_order == [
            "left.pinky",  # L4
            "left.ring",  # L3
            "left.middle",  # L2
            "left.index",  # L1
            "right.index",  # R1
            "right.middle",  # R2
            "right.ring",  # R3
            "right.pinky",  # R4
        ]

    def test_only_r4_uses_r4_priority(self):
        # Right-pinky north_key uses R4 priority → direction RIGHT.
        # Left-pinky north_key uses non-R4 priority → direction UP.
        layout = self._layout_target()
        right = _side(pinky=_finger(north_key=_key(layer_switch=1)))
        left = _side(pinky=_finger(north_key=_key(layer_switch=1)))

        steps = build_finger_path_list_for_layer(
            left=left,
            right=right,
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        l4_step = next(s for s in steps if s.source_cluster_attr == "left.pinky")
        r4_step = next(s for s in steps if s.source_cluster_attr == "right.pinky")
        assert l4_step.direction == Direction.UP  # non-R4 priority
        assert r4_step.direction == Direction.RIGHT  # R4 priority


class TestSourceDataclasses:
    def test_overview_layer_source_field_access(self):
        left = _side()
        right = _side()
        src = OverviewLayerSource(source_layer=3, left=left, right=right)
        assert src.source_layer == 3
        assert src.left is left
        assert src.right is right

    def test_thumb_source_field_access(self):
        left = _thumb()
        right = _thumb()
        src = ThumbSource(source_layer=0, left=left, right=right)
        assert src.source_layer == 0
        assert src.left is left
        assert src.right is right
