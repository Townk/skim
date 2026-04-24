# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.context module.

Tests cover RenderContext, ClusterRenderContext, and FingerClusterKeyColors.
"""

import pytest

from skim.application.render.context import (
    ClusterRenderContext,
    FingerClusterKeyColors,
    RenderContext,
)
from skim.data.config import LayerColor, Palette, SplitSidePosition
from skim.domain.domain_types import KeyboardSide, SvalboardTargetKey


@pytest.fixture
def sample_palette():
    """Create a sample palette for testing."""
    return Palette(
        layers=[
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
        ],
        neutral_color="#808080",
        key_label_color="#FFFFFF",
    )


class TestRenderContextInit:
    """Tests for RenderContext initialization."""

    def test_basic_initialization(self, sample_palette):
        """RenderContext initializes with all required parameters."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        assert ctx.palette == sample_palette
        assert ctx.layer_index == 0
        assert ctx.has_double_south is True
        assert ctx.use_layer_colors_on_keys is True
        assert ctx.hold_symbol_position == SplitSidePosition.OUTWARD

    def test_layer_colors_populated_in_post_init(self, sample_palette):
        """layer_colors is populated from palette in __post_init__."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=1,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.INWARD,
        )
        # layer_colors should be the second layer
        assert ctx.layer_colors == sample_palette.layers[1]
        assert ctx.layer_colors.base_color == "#00FF00"

    def test_frozen_dataclass(self, sample_palette):
        """RenderContext is frozen (immutable)."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.QMK_DEFINED,
        )
        with pytest.raises(AttributeError):
            ctx.layer_index = 1


class TestRenderContextKeyFillColor:
    """Tests for RenderContext.key_fill_color method."""

    def test_returns_default_when_layer_colors_disabled(self, sample_palette):
        """Returns default color when use_layer_colors_on_keys is False."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=False,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        key = SvalboardTargetKey(layer_switch=1)
        result = ctx.key_fill_color(key, default="#AABBCC")
        assert result == "#AABBCC"

    def test_returns_default_when_no_layer_switch(self, sample_palette):
        """Returns default color when key has no layer_switch."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        key = SvalboardTargetKey(layer_switch=None)
        result = ctx.key_fill_color(key, default="#AABBCC")
        assert result == "#AABBCC"

    def test_returns_layer_color_for_layer_switch_key(self, sample_palette):
        """Returns layer color when key switches to that layer."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        key = SvalboardTargetKey(layer_switch=1)
        result = ctx.key_fill_color(key, default="#AABBCC")
        # Should return color from layer 1's gradient at color_index (2)
        assert result == "#003300"

    def test_returns_accent_color_when_use_accent_true(self, sample_palette):
        """Returns accent color (color_index - 1) when use_accent is True."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        key = SvalboardTargetKey(layer_switch=1)
        result = ctx.key_fill_color(key, default="#AABBCC", use_accent=True)
        # color_index is 2, so accent is at index 1
        assert result == "#002200"

    def test_returns_default_for_invalid_layer_switch(self, sample_palette):
        """Returns default when layer_switch is out of range."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        key = SvalboardTargetKey(layer_switch=99)
        result = ctx.key_fill_color(key, default="#AABBCC")
        assert result == "#AABBCC"

    def test_returns_default_for_negative_layer_switch(self, sample_palette):
        """Returns default when layer_switch is negative."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        key = SvalboardTargetKey(layer_switch=-1)
        result = ctx.key_fill_color(key, default="#AABBCC")
        assert result == "#AABBCC"

    def test_returns_layer_color_using_qmk_position_mapping(self, sample_palette):
        """layer_switch QMK index is mapped to palette position via qmk_index_to_position."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            qmk_index_to_position=lambda idx: {0: 0, 15: 1, 3: 2}.get(idx),
        )
        key = SvalboardTargetKey(layer_switch=15)
        result = ctx.key_fill_color(key, default="#AABBCC")
        assert result == "#003300"

    def test_returns_default_for_unmapped_layer_switch(self, sample_palette):
        """Returns default when layer_switch QMK index has no position mapping."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            qmk_index_to_position=lambda _idx: None,
        )
        key = SvalboardTargetKey(layer_switch=99)
        result = ctx.key_fill_color(key, default="#AABBCC")
        assert result == "#AABBCC"


class TestClusterRenderContext:
    """Tests for ClusterRenderContext."""

    def test_initialization(self, sample_palette):
        """ClusterRenderContext initializes with side parameter."""
        ctx = ClusterRenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            side=KeyboardSide.LEFT,
        )
        assert ctx.side == KeyboardSide.LEFT

    def test_from_render_context_left(self, sample_palette):
        """Create ClusterRenderContext from RenderContext for left side."""
        base_ctx = RenderContext(
            palette=sample_palette,
            layer_index=1,
            has_double_south=True,
            use_layer_colors_on_keys=False,
            hold_symbol_position=SplitSidePosition.INWARD,
        )
        cluster_ctx = ClusterRenderContext.from_render_context(base_ctx, KeyboardSide.LEFT)

        assert cluster_ctx.palette == sample_palette
        assert cluster_ctx.layer_index == 1
        assert cluster_ctx.has_double_south is True
        assert cluster_ctx.use_layer_colors_on_keys is False
        assert cluster_ctx.hold_symbol_position == SplitSidePosition.INWARD
        assert cluster_ctx.side == KeyboardSide.LEFT

    def test_from_render_context_right(self, sample_palette):
        """Create ClusterRenderContext from RenderContext for right side."""
        base_ctx = RenderContext(
            palette=sample_palette,
            layer_index=2,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.QMK_DEFINED,
        )
        cluster_ctx = ClusterRenderContext.from_render_context(base_ctx, KeyboardSide.RIGHT)

        assert cluster_ctx.side == KeyboardSide.RIGHT
        assert cluster_ctx.layer_index == 2

    def test_inherits_key_fill_color_method(self, sample_palette):
        """ClusterRenderContext inherits key_fill_color from RenderContext."""
        ctx = ClusterRenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            side=KeyboardSide.LEFT,
        )
        key = SvalboardTargetKey(layer_switch=1)
        result = ctx.key_fill_color(key, default="#AABBCC")
        # Should use layer colors
        assert result == "#003300"


class TestRenderContextShowLayerIndicators:
    """Tests for show_layer_indicators in RenderContext."""

    def test_default_is_false(self, sample_palette):
        """show_layer_indicators defaults to False."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        assert ctx.show_layer_indicators is False

    def test_can_be_set_to_true(self, sample_palette):
        """show_layer_indicators can be set to True."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            show_layer_indicators=True,
        )
        assert ctx.show_layer_indicators is True

    def test_cluster_context_propagates(self, sample_palette):
        """ClusterRenderContext.from_render_context propagates show_layer_indicators."""
        base = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            show_layer_indicators=True,
        )
        cluster_ctx = ClusterRenderContext.from_render_context(base, KeyboardSide.LEFT)
        assert cluster_ctx.show_layer_indicators is True


class TestFingerClusterKeyColors:
    """Tests for FingerClusterKeyColors dataclass."""

    def test_initialization(self):
        """FingerClusterKeyColors initializes with primary and accent colors."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        assert colors.primary == "#FF0000"
        assert colors.accent == "#AA0000"

    def test_frozen_dataclass(self):
        """FingerClusterKeyColors is frozen (immutable)."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        with pytest.raises(AttributeError):
            colors.primary = "#00FF00"

    def test_slots_optimization(self):
        """FingerClusterKeyColors uses slots for memory optimization."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        # Slots-based classes don't have __dict__
        assert not hasattr(colors, "__dict__")
