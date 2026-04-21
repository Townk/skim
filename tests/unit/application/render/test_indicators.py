# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.indicators module."""

import pytest

from skim.application.render.indicators import (
    ConnectorType,
    LayerIndicator,
    LayerIndicatorOverlay,
    OffsetDirection,
)
from skim.application.render.layout import Boundary, Position
from skim.data.config import LayerColor, Palette
from skim.data.keyboard import FingerCluster, ThumbCluster
from skim.domain.domain_types import KeyboardSide, SvalboardTargetKey


@pytest.fixture
def sample_palette():
    """Create a sample palette with 3 layers for testing."""
    return Palette(
        layers=(
            LayerColor(
                base_color="#FF0000",
                color_index=2,
                gradient=("#110000", "#220000", "#330000", "#440000", "#550000", "#660000"),
            ),
            LayerColor(
                base_color="#00FF00",
                color_index=2,
                gradient=("#001100", "#002200", "#003300", "#004400", "#005500", "#006600"),
            ),
            LayerColor(
                base_color="#0000FF",
                color_index=2,
                gradient=("#000011", "#000022", "#000033", "#000044", "#000055", "#000066"),
            ),
        ),
        neutral_color="#808080",
        key_label_color="#FFFFFF",
    )


class TestLayerIndicator:
    """Tests for LayerIndicator rendering."""

    def test_creates_svg_group(self, sample_palette):
        """LayerIndicator produces a drawsvg Group."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=1,
            palette=sample_palette,
            circle_diameter=27.5,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        svg = indicator.build()
        svg_str = svg.as_svg()
        assert "<circle" in svg_str
        assert "<line" in svg_str
        assert ">1<" in svg_str

    def test_fill_color_uses_target_layer_base_color(self, sample_palette):
        """Circle fill uses the target layer's base_color."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=1,
            palette=sample_palette,
            circle_diameter=27.5,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        svg_str = indicator.build().as_svg()
        assert 'fill="#00FF00"' in svg_str

    def test_stroke_color_uses_gradient_1(self, sample_palette):
        """Circle stroke uses gradient[1] of the target layer."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=1,
            palette=sample_palette,
            circle_diameter=27.5,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        svg_str = indicator.build().as_svg()
        assert 'stroke="#002200"' in svg_str

    def test_above_offset_places_circle_above_key(self, sample_palette):
        """ABOVE offset places circle center above the key top edge."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=0,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        assert indicator.circle_center_x == pytest.approx(127.5)
        assert indicator.circle_center_y == pytest.approx(6)

    def test_left_offset_places_circle_left_of_key(self, sample_palette):
        """LEFT offset places circle center to the left of the key."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=155,
            key_width=55,
            key_height=55,
            target_layer=0,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.LEFT,
            connector_type=ConnectorType.HORIZONTAL,
        )
        assert indicator.circle_center_x == pytest.approx(76)
        assert indicator.circle_center_y == pytest.approx(182.5)

    def test_right_offset_places_circle_right_of_key(self, sample_palette):
        """RIGHT offset places circle center to the right of the key."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=155,
            key_width=55,
            key_height=55,
            target_layer=0,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.RIGHT,
            connector_type=ConnectorType.HORIZONTAL,
        )
        assert indicator.circle_center_x == pytest.approx(179)
        assert indicator.circle_center_y == pytest.approx(182.5)

    def test_diagonal_right_offset(self, sample_palette):
        """DIAGONAL_RIGHT places circle at 45-deg below-right of key center."""
        indicator = LayerIndicator(
            key_x=99,
            key_y=89,
            key_width=56,
            key_height=56,
            target_layer=0,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.DIAGONAL_RIGHT,
            connector_type=ConnectorType.DIAGONAL,
        )
        key_cx = 99 + 56 / 2
        key_cy = 89 + 56 / 2
        dx = indicator.circle_center_x - key_cx
        dy = indicator.circle_center_y - key_cy
        assert dx == pytest.approx(dy)
        assert dx > 0

    def test_out_of_range_layer_still_renders(self, sample_palette):
        """Indicator for a layer index beyond palette falls back gracefully."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=99,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        svg_str = indicator.build().as_svg()
        assert "<circle" in svg_str


def _make_finger_cluster_keys(layer_switches):
    """Helper: create FingerCluster with given layer_switch values."""
    names = ["center", "north", "east", "south", "west", "double_south"]
    return FingerCluster(**{
        f"{n}_key": SvalboardTargetKey(label=n.upper(), layer_switch=ls)
        for n, ls in zip(names, layer_switches)
    })


def _make_finger_cluster_metrics():
    """Helper: create a simple FingerCluster of Boundary for layout metrics."""
    return FingerCluster(
        center_key=Boundary(width=50, pos=Position(x=75, y=60)),
        north_key=Boundary(width=55, pos=Position(x=72, y=0)),
        east_key=Boundary(width=55, pos=Position(x=135, y=55)),
        south_key=Boundary(width=55, pos=Position(x=72, y=120)),
        west_key=Boundary(width=55, pos=Position(x=10, y=55)),
        double_south_key=Boundary(width=55, pos=Position(x=72, y=185)),
    )


class TestFingerClusterOverlay:
    def test_skips_keys_without_layer_switch(self, sample_palette):
        keys = _make_finger_cluster_keys([None, None, None, None, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys, metrics=metrics, side=KeyboardSide.LEFT,
            palette=sample_palette, circle_diameter=28, gap=10, has_double_south=True,
        )
        assert len(overlay.build()) == 0

    def test_north_key_gets_above_indicator(self, sample_palette):
        keys = _make_finger_cluster_keys([None, 2, None, None, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys, metrics=metrics, side=KeyboardSide.LEFT,
            palette=sample_palette, circle_diameter=28, gap=10, has_double_south=True,
        )
        assert len(overlay.build()) == 1

    def test_south_left_hand_gets_left_indicator(self, sample_palette):
        keys = _make_finger_cluster_keys([None, None, None, 1, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys, metrics=metrics, side=KeyboardSide.LEFT,
            palette=sample_palette, circle_diameter=28, gap=10, has_double_south=True,
        )
        assert len(overlay.build()) == 1

    def test_south_right_hand_gets_right_indicator(self, sample_palette):
        keys = _make_finger_cluster_keys([None, None, None, 1, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys, metrics=metrics, side=KeyboardSide.RIGHT,
            palette=sample_palette, circle_diameter=28, gap=10, has_double_south=True,
        )
        assert len(overlay.build()) == 1

    def test_center_left_hand_gets_diagonal_right(self, sample_palette):
        keys = _make_finger_cluster_keys([1, None, None, None, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys, metrics=metrics, side=KeyboardSide.LEFT,
            palette=sample_palette, circle_diameter=28, gap=10, has_double_south=True,
        )
        assert len(overlay.build()) == 1

    def test_center_right_hand_gets_diagonal_left(self, sample_palette):
        keys = _make_finger_cluster_keys([1, None, None, None, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys, metrics=metrics, side=KeyboardSide.RIGHT,
            palette=sample_palette, circle_diameter=28, gap=10, has_double_south=True,
        )
        assert len(overlay.build()) == 1

    def test_double_south_skipped_when_no_double_south(self, sample_palette):
        keys = _make_finger_cluster_keys([None, None, None, None, None, 2])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys, metrics=metrics, side=KeyboardSide.LEFT,
            palette=sample_palette, circle_diameter=28, gap=10, has_double_south=False,
        )
        assert len(overlay.build()) == 0

    def test_multiple_keys_produce_multiple_indicators(self, sample_palette):
        keys = _make_finger_cluster_keys([1, 2, None, 0, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys, metrics=metrics, side=KeyboardSide.LEFT,
            palette=sample_palette, circle_diameter=28, gap=10, has_double_south=True,
        )
        assert len(overlay.build()) == 3


def _make_thumb_cluster_keys(layer_switches):
    """Helper: create ThumbCluster with given layer_switch values."""
    names = ["down", "pad", "up", "nail", "knuckle", "double_down"]
    return ThumbCluster(**{
        f"{n}_key": SvalboardTargetKey(label=n.upper(), layer_switch=ls)
        for n, ls in zip(names, layer_switches)
    })


def _make_thumb_cluster_metrics():
    """Helper: create ThumbCluster of Boundary for layout metrics."""
    return ThumbCluster(
        down_key=Boundary(width=40, pos=Position(x=130, y=0)),
        pad_key=Boundary(width=110, pos=Position(x=10, y=10)),
        up_key=Boundary(width=100, pos=Position(x=30, y=80)),
        nail_key=Boundary(width=110, pos=Position(x=180, y=10)),
        knuckle_key=Boundary(width=100, pos=Position(x=180, y=80)),
        double_down_key=Boundary(width=34, pos=Position(x=133, y=20)),
    )


class TestThumbClusterOverlay:
    def test_skips_keys_without_layer_switch(self, sample_palette):
        keys = _make_thumb_cluster_keys([None, None, None, None, None, None])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys, metrics=metrics, down_key_metrics=metrics.down_key,
            side=KeyboardSide.LEFT, palette=sample_palette, circle_diameter=28, gap=10,
        )
        assert len(overlay.build()) == 0

    def test_pad_left_hand_gets_left_indicator(self, sample_palette):
        keys = _make_thumb_cluster_keys([None, 1, None, None, None, None])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys, metrics=metrics, down_key_metrics=metrics.down_key,
            side=KeyboardSide.LEFT, palette=sample_palette, circle_diameter=28, gap=10,
        )
        assert len(overlay.build()) == 1

    def test_pad_right_hand_gets_right_indicator(self, sample_palette):
        keys = _make_thumb_cluster_keys([None, 1, None, None, None, None])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys, metrics=metrics, down_key_metrics=metrics.down_key,
            side=KeyboardSide.RIGHT, palette=sample_palette, circle_diameter=28, gap=10,
        )
        assert len(overlay.build()) == 1

    def test_double_down_gets_above_indicator(self, sample_palette):
        keys = _make_thumb_cluster_keys([None, None, None, None, None, 2])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys, metrics=metrics, down_key_metrics=metrics.down_key,
            side=KeyboardSide.LEFT, palette=sample_palette, circle_diameter=28, gap=10,
        )
        assert len(overlay.build()) == 1

    def test_multiple_thumb_keys(self, sample_palette):
        keys = _make_thumb_cluster_keys([1, 2, 0, None, None, None])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys, metrics=metrics, down_key_metrics=metrics.down_key,
            side=KeyboardSide.LEFT, palette=sample_palette, circle_diameter=28, gap=10,
        )
        assert len(overlay.build()) == 3
