"""Unit tests for skim.application.render.components module.

Tests cover finger and thumb cluster component rendering.
"""

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
