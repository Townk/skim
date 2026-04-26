# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.overview_layout module."""

import pytest

from skim.application.render.overview_layout import BadgeDimensions, OverviewLayout
from skim.data.config import (
    Keyboard,
    KeyboardFeatures,
    KeyboardLayer,
    LayerColor,
    Output,
    Palette,
    SkimConfig,
    Style,
)


def _make_config(num_layers: int, width: float = 1600, double_south: bool = False) -> SkimConfig:
    layers_cfg = tuple(KeyboardLayer(index=i, name=f"Layer {i}") for i in range(num_layers))
    layer_colors = tuple(
        LayerColor(base_color=f"#{i + 1:02x}{i + 1:02x}{i + 1:02x}") for i in range(num_layers)
    )
    return SkimConfig(
        keyboard=Keyboard(layers=layers_cfg, features=KeyboardFeatures(double_south=double_south)),
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

    def test_ew_key_y_offset_includes_inset(self):
        """ew_key_y_offset is the Y of the E/W key TOP, which sits one inset below the north key.

        Was previously returning just ``outer * cluster_width`` (= north_key bottom),
        which is the inset shy of the actual E/W top.
        """
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        cw = layout.finger_cluster_width
        assert layout.ew_key_y_offset == pytest.approx(cw * (0.328 + 0.018))

    def test_outer_key_size_property(self):
        """outer_key_size returns the side of an outer key (N/S/E/W)."""
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        cw = layout.finger_cluster_width
        assert layout.outer_key_size == pytest.approx(cw * 0.328)

    def test_thumb_pad_key_y_offset(self):
        """thumb_pad_key_y_offset is the Y of the pad_key TOP within the thumb cluster.

        Pad key sits one thumb cluster inset below the down key (which is at y=0).
        """
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        thumb_w = layout.thumb_cluster_width
        # Thumb cluster's inset proportion is 0.038 (per ThumbClusterComponent).
        assert layout.thumb_pad_key_y_offset == pytest.approx(thumb_w * 0.038)

    def test_finger_to_thumb_gap_equals_inter_row_gap(self):
        """Without indicators, the gap between the last finger row and the thumb row
        equals the inter-row gap. Same rhythm everywhere.
        """
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)

        last_row_bottom = layout.layer_row_y_positions[-1] + layout.layer_row_heights[-1]
        thumb_gap = layout.thumb_row_y - last_row_bottom

        inter_row_gap = (
            layout.layer_row_y_positions[1]
            - layout.layer_row_y_positions[0]
            - layout.layer_row_heights[0]
        )

        assert thumb_gap == pytest.approx(inter_row_gap)

    def test_inter_row_gap_equals_south_key_height(self):
        """row_gap matches the south_key height — one key of breathing room.

        Anchoring the inter-row gap to a key dimension keeps the visual rhythm
        consistent across keymaps with different canvas widths and DS settings.
        """
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)

        inter_row_gap = (
            layout.layer_row_y_positions[1]
            - layout.layer_row_y_positions[0]
            - layout.layer_row_heights[0]
        )
        south_key_height = layout.finger_cluster_width * 0.328
        assert inter_row_gap == pytest.approx(south_key_height)

    def test_title_to_first_row_gap_matches_inter_row_gap(self):
        """The gap from header content bottom to first layer row equals the inter-row gap.

        This keeps the visual rhythm consistent: the title sits "one row apart"
        from layer row 0, just like layer rows are spaced "one row apart" from
        each other.
        """
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)

        # Logo dimensions mirror what overview.py renders: width = badge.width * 1.06
        # with the Svalboard logo aspect ratio (458.333:2333.333).
        logo_width = _DEFAULT_BADGE.width * 1.06
        logo_height = logo_width * (458.333 / 2333.333)
        header_content_bottom = layout.padding + logo_height

        first_row_top = layout.layer_row_y_positions[0]
        title_to_row_gap = first_row_top - header_content_bottom

        inter_row_gap = (
            layout.layer_row_y_positions[1]
            - layout.layer_row_y_positions[0]
            - layout.layer_row_heights[0]
        )

        assert title_to_row_gap == pytest.approx(inter_row_gap)

    def test_bottom_inset_is_one_inset(self):
        """Space between the thumb cluster bottom and the canvas bottom is one inset.

        Mirrors the per-layer canvas rule — the bottom shouldn't have the larger
        outer padding the sides use.
        """
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)

        thumb_height = layout.thumb_cluster_width * (1.0 / 1.5)  # 1.5:1 aspect
        thumb_bottom = layout.thumb_row_y + thumb_height
        bottom_inset = layout.canvas_height - thumb_bottom

        expected = config.output.layout.spacing.inset
        assert bottom_inset == pytest.approx(expected)

    def test_canvas_width_no_routing_when_zero_columns(self):
        """When routing_column_count=0, _compute() should not reserve any
        right-side routing space — extra_right_padding will carry that.

        Regression for over-allocation in draw_overview where the constructor
        pre-reserved routing width AND the connector router added it again
        via adjust_canvas_width.
        """
        config = _make_config(3)
        layout_with_routing = OverviewLayout(config, _DEFAULT_BADGE, routing_column_count=3)
        layout_without_routing = OverviewLayout(config, _DEFAULT_BADGE, routing_column_count=0)
        assert layout_without_routing.canvas_width < layout_with_routing.canvas_width

    def test_col_gap_equals_4_keymap_spacings(self):
        """The gap between col 1 (layer badges) and col 2 (L4 cluster) must be
        exactly ``4 * KEYMAP_SPACING``, where ``KEYMAP_SPACING = outer_key_size * 0.6``.

        Locks the closed-form fixed-point computation against accidental drift
        back to the inset-based formula.
        """
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE)
        actual_gap = layout.right_column_x - layout.left_column_width
        expected = 4 * layout.outer_key_size * 0.6
        assert actual_gap == pytest.approx(expected)

    def test_cluster_to_thumb_gap_matches_between_double_south_and_single_south(self):
        """The gap from finger cluster content bottom to thumb top must be the same in DS and NDS.

        The bbox aspect ratio (1:1 / 4:3) doesn't perfectly contain the keys —
        the overshoot is much larger in DS, which previously made the visible
        gap to the thumb row tighter when DS was enabled.
        """
        config_no_ds = _make_config(3)
        config_ds = _make_config(3, double_south=True)
        layout_no_ds = OverviewLayout(config_no_ds, _DEFAULT_BADGE)
        layout_ds = OverviewLayout(config_ds, _DEFAULT_BADGE)

        # Content extent uses the finger cluster's actual key proportions
        # (outer/center/inset). Both layouts share the same finger_cluster_width.
        cw = layout_no_ds.finger_cluster_width
        assert cw == pytest.approx(layout_ds.finger_cluster_width)
        nds_content = cw * (2 * 0.328 + 0.309 + 2 * 0.018)
        ds_content = cw * (3 * 0.328 + 0.309 + 3 * 0.018)

        nds_last_row_content_bottom = layout_no_ds.layer_row_y_positions[-1] + nds_content
        ds_last_row_content_bottom = layout_ds.layer_row_y_positions[-1] + ds_content

        nds_gap = layout_no_ds.thumb_row_y - nds_last_row_content_bottom
        ds_gap = layout_ds.thumb_row_y - ds_last_row_content_bottom

        assert nds_gap == pytest.approx(ds_gap)


class TestShiftLayerRowAndBelow:
    def test_shifts_target_row_and_every_row_below(self):
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE, routing_column_count=0)
        ys_before = list(layout.layer_row_y_positions)
        thumb_before = layout.thumb_row_y
        canvas_before = layout.canvas_height

        layout.shift_layer_row_and_below(row_idx=1, amount=20.0)

        assert layout.layer_row_y_positions[0] == ys_before[0]
        assert layout.layer_row_y_positions[1] == ys_before[1] + 20.0
        assert layout.layer_row_y_positions[2] == ys_before[2] + 20.0
        assert layout.thumb_row_y == thumb_before + 20.0
        assert layout.canvas_height == canvas_before + 20.0

    def test_noop_on_non_positive_amount(self):
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE, routing_column_count=0)
        ys_before = list(layout.layer_row_y_positions)
        canvas_before = layout.canvas_height

        layout.shift_layer_row_and_below(row_idx=1, amount=0.0)
        layout.shift_layer_row_and_below(row_idx=1, amount=-5.0)

        assert layout.layer_row_y_positions == ys_before
        assert layout.canvas_height == canvas_before


class TestShiftBelowLayerRow:
    def test_shifts_rows_strictly_below_target(self):
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE, routing_column_count=0)
        ys_before = list(layout.layer_row_y_positions)
        thumb_before = layout.thumb_row_y
        canvas_before = layout.canvas_height

        layout.shift_below_layer_row(row_idx=1, amount=20.0)

        assert layout.layer_row_y_positions[0] == ys_before[0]
        assert layout.layer_row_y_positions[1] == ys_before[1]  # NOT shifted
        assert layout.layer_row_y_positions[2] == ys_before[2] + 20.0
        assert layout.thumb_row_y == thumb_before + 20.0
        assert layout.canvas_height == canvas_before + 20.0

    def test_noop_on_non_positive_amount(self):
        config = _make_config(3)
        layout = OverviewLayout(config, _DEFAULT_BADGE, routing_column_count=0)
        ys_before = list(layout.layer_row_y_positions)
        canvas_before = layout.canvas_height

        layout.shift_below_layer_row(row_idx=1, amount=0.0)
        layout.shift_below_layer_row(row_idx=1, amount=-5.0)

        assert layout.layer_row_y_positions == ys_before
        assert layout.canvas_height == canvas_before
