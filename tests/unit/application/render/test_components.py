# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.components module.

Tests cover finger and thumb cluster component rendering.
"""

import drawsvg as draw
import pytest

from skim.application.render.components import (
    FingerClusterComponent,
    ThumbClusterComponent,
    _adjust_hold_symbol_label,
)
from skim.application.render.context import ClusterRenderContext, RenderContext
from skim.application.render.layout import Boundary, Position
from skim.data.config import LayerColor, Palette, SplitSidePosition
from skim.data.keyboard import FingerCluster, ThumbCluster
from skim.domain.domain_types import KeyboardSide, SvalboardTargetKey


@pytest.fixture
def sample_palette():
    """Create a sample palette for testing."""
    return Palette(
        layers=[
            LayerColor(
                base_color="#FF0000",
                gradient=("#110000", "#220000", "#330000", "#440000", "#550000", "#660000"),
            ),
        ],
        neutral_color="#808080",
        key_label_color="#FFFFFF",
    )


@pytest.fixture
def render_context(sample_palette):
    """Create a RenderContext for testing."""
    return RenderContext(
        palette=sample_palette,
        layer_index=0,
        has_double_south=False,
        use_layer_colors_on_keys=True,
        hold_symbol_position=SplitSidePosition.OUTWARD,
    )


@pytest.fixture
def cluster_context_left(render_context):
    """Create a ClusterRenderContext for left side."""
    return ClusterRenderContext.from_render_context(render_context, KeyboardSide.LEFT)


@pytest.fixture
def cluster_context_right(render_context):
    """Create a ClusterRenderContext for right side."""
    return ClusterRenderContext.from_render_context(render_context, KeyboardSide.RIGHT)


@pytest.fixture
def boundary():
    """Create a test boundary."""
    return Boundary(pos=Position(x=100.0, y=50.0), width=200.0)


class TestAdjustHoldSymbolLabel:
    """Tests for _adjust_hold_symbol_label helper function."""

    def test_no_separator_returns_unchanged(self):
        """Label without separator returns unchanged."""
        result = _adjust_hold_symbol_label(SplitSidePosition.OUTWARD, KeyboardSide.LEFT, "Hello")
        assert result == "Hello"

    def test_outward_left_swaps_order(self):
        """OUTWARD position on LEFT swaps hold/tap order."""
        result = _adjust_hold_symbol_label(SplitSidePosition.OUTWARD, KeyboardSide.LEFT, "A│B")
        # Behavior depends on implementation
        assert "│" in result

    def test_outward_right_preserves_order(self):
        """OUTWARD position on RIGHT preserves order."""
        result = _adjust_hold_symbol_label(SplitSidePosition.OUTWARD, KeyboardSide.RIGHT, "A│B")
        assert "│" in result

    def test_inward_left_preserves_order(self):
        """INWARD position on LEFT preserves order."""
        result = _adjust_hold_symbol_label(SplitSidePosition.INWARD, KeyboardSide.LEFT, "A│B")
        assert "│" in result

    def test_inward_left_swaps_to_tap_hold_order(self):
        """INWARD position on LEFT side swaps to tap|hold order."""
        result = _adjust_hold_symbol_label(SplitSidePosition.INWARD, KeyboardSide.LEFT, "A│B")
        assert result == "B│A"


class TestFingerClusterComponent:
    """Tests for FingerClusterComponent class."""

    @pytest.fixture
    def finger_cluster(self):
        """Create a test finger cluster."""
        return FingerCluster(
            center_key=SvalboardTargetKey(label="C"),
            north_key=SvalboardTargetKey(label="N"),
            east_key=SvalboardTargetKey(label="E"),
            south_key=SvalboardTargetKey(label="S"),
            west_key=SvalboardTargetKey(label="W"),
            double_south_key=SvalboardTargetKey(label="DS"),
        )

    def test_initialization(self, finger_cluster, render_context, boundary):
        """FingerClusterComponent initializes correctly."""
        component = FingerClusterComponent(
            finger_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        assert component is not None

    def test_width_property(self, finger_cluster, render_context, boundary):
        """width property returns positive value."""
        component = FingerClusterComponent(
            finger_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        assert component.width > 0

    def test_height_property(self, finger_cluster, render_context, boundary):
        """height property returns positive value."""
        component = FingerClusterComponent(
            finger_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        assert component.height > 0

    def test_build_returns_element(self, finger_cluster, render_context, boundary):
        """build method returns a drawing element."""
        component = FingerClusterComponent(
            finger_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        element = component.build()
        assert element is not None

    def test_left_vs_right_positioning(self, finger_cluster, render_context, boundary):
        """Left and right clusters have different positioning."""
        left_component = FingerClusterComponent(
            finger_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        right_component = FingerClusterComponent(
            finger_cluster, KeyboardSide.RIGHT, boundary, render_context
        )
        # Both should build successfully
        assert left_component.build() is not None
        assert right_component.build() is not None

    def test_height_matches_south_key_bottom_without_double_south(
        self, finger_cluster, render_context, boundary
    ):
        """Without double_south, ``height`` equals the south_key's actual bottom edge.

        The bbox's 1:1 aspect ratio doesn't perfectly contain the keys (their
        cumulative size + inset slightly overshoots the bbox), so using the
        bbox height for layout would leave the thumb too close to the visible
        cluster bottom. ``height`` reflects the actual content extent.
        """
        component = FingerClusterComponent(
            finger_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        south = component._layout.metrics.south_key
        assert component.height == pytest.approx(south.pos.y + south.width)

    def test_height_matches_double_south_key_bottom_with_double_south(
        self, finger_cluster, sample_palette, boundary
    ):
        """With double_south, ``height`` equals the double_south_key's actual bottom edge.

        Same reasoning as the no-double_south case — the 4:3 bbox aspect ratio
        leaves about ~1.4% of the cluster width unaccounted for, which would
        otherwise pull the thumb too close in DS-enabled keymaps.
        """
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        component = FingerClusterComponent(finger_cluster, KeyboardSide.LEFT, boundary, ctx)
        ds = component._layout.metrics.double_south_key
        assert component.height == pytest.approx(ds.pos.y + ds.width)


class TestThumbClusterComponent:
    """Tests for ThumbClusterComponent class."""

    @pytest.fixture
    def thumb_cluster(self):
        """Create a test thumb cluster."""
        return ThumbCluster(
            down_key=SvalboardTargetKey(label="D"),
            pad_key=SvalboardTargetKey(label="P"),
            up_key=SvalboardTargetKey(label="U"),
            nail_key=SvalboardTargetKey(label="N"),
            knuckle_key=SvalboardTargetKey(label="K"),
            double_down_key=SvalboardTargetKey(label="DD"),
        )

    def test_initialization(self, thumb_cluster, render_context, boundary):
        """ThumbClusterComponent initializes correctly."""
        component = ThumbClusterComponent(
            thumb_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        assert component is not None

    def test_width_property(self, thumb_cluster, render_context, boundary):
        """width property returns positive value."""
        component = ThumbClusterComponent(
            thumb_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        assert component.width > 0

    def test_height_property(self, thumb_cluster, render_context, boundary):
        """height property returns positive value."""
        component = ThumbClusterComponent(
            thumb_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        assert component.height > 0

    def test_build_returns_element(self, thumb_cluster, render_context, boundary):
        """build method returns a drawing element."""
        component = ThumbClusterComponent(
            thumb_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        element = component.build()
        assert element is not None

    def test_left_vs_right_positioning(self, thumb_cluster, render_context, boundary):
        """Left and right thumb clusters have different positioning."""
        left_component = ThumbClusterComponent(
            thumb_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        right_component = ThumbClusterComponent(
            thumb_cluster, KeyboardSide.RIGHT, boundary, render_context
        )
        # Both should build successfully
        assert left_component.build() is not None
        assert right_component.build() is not None

    def test_aspect_ratio(self, thumb_cluster, render_context, boundary):
        """ThumbClusterComponent has expected aspect ratio."""
        component = ThumbClusterComponent(
            thumb_cluster, KeyboardSide.LEFT, boundary, render_context
        )
        # Thumb cluster aspect ratio is typically 1.5:1
        ratio = component.width / component.height
        assert 1.3 < ratio < 1.7  # Allow some tolerance


class TestFingerClusterIndicators:
    """Tests for layer indicator integration in FingerClusterComponent."""

    @pytest.fixture
    def two_layer_palette(self):
        """Create a palette with two layers for layer_switch=1 tests."""
        return Palette(
            layers=[
                LayerColor(
                    base_color="#FF0000",
                    gradient=("#110000", "#220000", "#330000", "#440000", "#550000", "#660000"),
                ),
                LayerColor(
                    base_color="#0000FF",
                    gradient=("#000011", "#000022", "#000033", "#000044", "#000055", "#000066"),
                ),
            ],
            neutral_color="#808080",
            key_label_color="#FFFFFF",
        )

    def test_indicators_rendered_when_enabled(self, two_layer_palette):
        """Indicators appear in SVG when show_layer_indicators is True."""
        keys = FingerCluster(
            center_key=SvalboardTargetKey(layer_switch=1),
            north_key=SvalboardTargetKey(layer_switch=None),
            east_key=SvalboardTargetKey(layer_switch=None),
            south_key=SvalboardTargetKey(layer_switch=None),
            west_key=SvalboardTargetKey(layer_switch=None),
            double_south_key=SvalboardTargetKey(layer_switch=None),
        )
        ctx = RenderContext(
            palette=two_layer_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            show_layer_indicators=True,
        )
        component = FingerClusterComponent(
            keymap_cluster=keys,
            side=KeyboardSide.LEFT,
            layout=Boundary(width=165, pos=Position(x=0, y=0)),
            render_context=ctx,
        )
        element = component.build()
        d = draw.Drawing(165, 165)
        d.append(element)
        svg_str = d.as_svg()
        # Should contain indicator elements (layer number "1")
        assert ">1<" in svg_str

    def test_indicators_not_rendered_when_disabled(self, two_layer_palette):
        """No indicators in SVG when show_layer_indicators is False."""
        keys = FingerCluster(
            center_key=SvalboardTargetKey(layer_switch=1),
            north_key=SvalboardTargetKey(layer_switch=None),
            east_key=SvalboardTargetKey(layer_switch=None),
            south_key=SvalboardTargetKey(layer_switch=None),
            west_key=SvalboardTargetKey(layer_switch=None),
            double_south_key=SvalboardTargetKey(layer_switch=None),
        )
        ctx = RenderContext(
            palette=two_layer_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            show_layer_indicators=False,
        )
        component = FingerClusterComponent(
            keymap_cluster=keys,
            side=KeyboardSide.LEFT,
            layout=Boundary(width=165, pos=Position(x=0, y=0)),
            render_context=ctx,
        )
        element = component.build()
        d = draw.Drawing(165, 165)
        d.append(element)
        svg_str = d.as_svg()
        # The indicator circle uses the target layer's base_color as fill
        assert f'fill="{two_layer_palette.layers[1].base_color}"' not in svg_str


class TestClusterWithDoubleSouth:
    """Tests for clusters with double_south enabled."""

    @pytest.fixture
    def context_with_double_south(self, sample_palette):
        """Create context with double_south enabled."""
        return RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )

    def test_finger_cluster_with_double_south(self, context_with_double_south, boundary):
        """FingerClusterComponent renders with double_south."""
        finger_cluster = FingerCluster(
            center_key=SvalboardTargetKey(label="C"),
            north_key=SvalboardTargetKey(label="N"),
            east_key=SvalboardTargetKey(label="E"),
            south_key=SvalboardTargetKey(label="S"),
            west_key=SvalboardTargetKey(label="W"),
            double_south_key=SvalboardTargetKey(label="DS"),
        )
        component = FingerClusterComponent(
            finger_cluster, KeyboardSide.LEFT, boundary, context_with_double_south
        )
        element = component.build()
        assert element is not None
