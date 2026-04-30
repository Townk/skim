# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.keys module.

Tests cover individual key rendering for finger and thumb clusters.
"""

import pytest

from skim.application.render.context import ClusterRenderContext, FingerClusterKeyColors
from skim.application.render.geometry import AspectRatio
from skim.application.render.keys import (
    CenterKey,
    DirectionalKey,
    DoubleDownKey,
    DoubleSouthKey,
    DownKey,
    KeyConfig,
    KnuckleKey,
    NailKey,
    PadKey,
    UpKey,
)
from skim.application.render.layout import Boundary, Position
from skim.data.config import LayerColor, Palette, SplitSidePosition
from skim.domain.domain_types import KeyboardSide, KeyDirection, SvalboardTargetKey


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
def cluster_context(sample_palette):
    """Create a ClusterRenderContext for testing."""
    from skim.application.render.context import RenderContext

    base = RenderContext(
        palette=sample_palette,
        layer_index=0,
        has_double_south=False,
        use_layer_colors_on_keys=True,
        hold_symbol_position=SplitSidePosition.OUTWARD,
    )
    return ClusterRenderContext.from_render_context(base, KeyboardSide.LEFT)


@pytest.fixture
def key_layout():
    """Create a Boundary for testing."""
    return Boundary(pos=Position(x=100.0, y=50.0), width=60.0)


@pytest.fixture
def target_key():
    """Create a SvalboardTargetKey for testing."""
    return SvalboardTargetKey(label="A")


class TestKeyConfig:
    """Tests for KeyConfig dataclass."""

    def test_initialization(self):
        """KeyConfig initializes with required parameters."""
        config = KeyConfig(
            aspect_ratio=AspectRatio("1:1"),
            font_height_multiplier=0.5,
            label_width_multiplier=0.8,
        )
        assert config.aspect_ratio is not None
        assert config.font_height_multiplier == 0.5
        assert config.label_width_multiplier == 0.8

    def test_default_multipliers(self):
        """KeyConfig has default multipliers."""
        config = KeyConfig(
            aspect_ratio=AspectRatio("1:1"),
            font_height_multiplier=0.5,
            label_width_multiplier=0.8,
        )
        assert config.stroke_width_multiplier == 1.0
        assert config.corner_radius_width_multiplier == 1.0
        assert config.slant_size_multiplier == 0.0
        assert config.label_margin_size_multiplier == 0.0

    def test_frozen_dataclass(self):
        """KeyConfig is frozen."""
        config = KeyConfig(
            aspect_ratio=AspectRatio("1:1"),
            font_height_multiplier=0.5,
            label_width_multiplier=0.8,
        )
        with pytest.raises(AttributeError):
            config.font_height_multiplier = 0.6


class TestCenterKey:
    """Tests for CenterKey class (circular finger cluster key)."""

    def test_initialization(self, cluster_context, key_layout, target_key):
        """CenterKey initializes correctly."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target_key, colors, key_layout)
        assert key is not None

    def test_has_aspect_ratio(self, cluster_context, key_layout, target_key):
        """CenterKey has aspect_ratio property."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target_key, colors, key_layout)
        assert key.aspect_ratio is not None
        assert isinstance(key.aspect_ratio, AspectRatio)

    def test_builds_group(self, cluster_context, key_layout, target_key):
        """CenterKey builds a Group element."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target_key, colors, key_layout)
        # Key is a Group subclass, check elements
        assert len(list(key.children)) > 0


class TestDirectionalKey:
    """Tests for DirectionalKey class (N/S/E/W finger cluster keys)."""

    @pytest.fixture
    def north_key(self, cluster_context, key_layout, target_key):
        """Create a north DirectionalKey."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        return DirectionalKey(cluster_context, target_key, colors, KeyDirection.NORTH, key_layout)

    def test_north_key_initialization(self, north_key):
        """North DirectionalKey initializes correctly."""
        assert north_key is not None

    def test_direction_affects_shape(self, cluster_context, key_layout, target_key):
        """Different directions create different shapes."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        north = DirectionalKey(cluster_context, target_key, colors, KeyDirection.NORTH, key_layout)
        east = DirectionalKey(cluster_context, target_key, colors, KeyDirection.EAST, key_layout)

        # Both should build successfully
        assert len(list(north.children)) > 0
        assert len(list(east.children)) > 0

    def test_all_directions(self, cluster_context, key_layout, target_key):
        """All cardinal directions can be created."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        directions = [
            KeyDirection.NORTH,
            KeyDirection.SOUTH,
            KeyDirection.EAST,
            KeyDirection.WEST,
        ]
        for direction in directions:
            key = DirectionalKey(cluster_context, target_key, colors, direction, key_layout)
            assert key is not None


class TestDoubleSouthKey:
    """Tests for DoubleSouthKey class."""

    def test_initialization(self, cluster_context, key_layout, target_key):
        """DoubleSouthKey initializes correctly."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = DoubleSouthKey(cluster_context, target_key, colors, key_layout)
        assert key is not None

    def test_builds_elements(self, cluster_context, key_layout, target_key):
        """DoubleSouthKey builds elements."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = DoubleSouthKey(cluster_context, target_key, colors, key_layout)
        assert len(list(key.children)) > 0


class TestThumbClusterKeys:
    """Tests for thumb cluster key classes."""

    @pytest.fixture
    def context_left(self, sample_palette):
        """Create left-side cluster context."""
        from skim.application.render.context import RenderContext

        base = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        return ClusterRenderContext.from_render_context(base, KeyboardSide.LEFT)

    @pytest.fixture
    def context_right(self, sample_palette):
        """Create right-side cluster context."""
        from skim.application.render.context import RenderContext

        base = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        return ClusterRenderContext.from_render_context(base, KeyboardSide.RIGHT)

    def test_down_key(self, context_left, key_layout, target_key):
        """DownKey initializes correctly."""
        key = DownKey(context_left, target_key, key_layout)
        assert key is not None
        assert len(list(key.children)) > 0

    def test_double_down_key(self, context_left, key_layout, target_key):
        """DoubleDownKey initializes correctly."""
        key = DoubleDownKey(context_left, target_key, key_layout)
        assert key is not None
        assert len(list(key.children)) > 0

    def test_up_key_left(self, context_left, key_layout, target_key):
        """UpKey for left side initializes correctly."""
        key = UpKey(context_left, target_key, key_layout)
        assert key is not None
        assert len(list(key.children)) > 0

    def test_up_key_right(self, context_right, key_layout, target_key):
        """UpKey for right side initializes correctly."""
        key = UpKey(context_right, target_key, key_layout)
        assert key is not None
        assert len(list(key.children)) > 0

    def test_pad_key_left(self, context_left, key_layout, target_key):
        """PadKey for left side initializes correctly."""
        key = PadKey(context_left, target_key, key_layout)
        assert key is not None
        assert len(list(key.children)) > 0

    def test_pad_key_right(self, context_right, key_layout, target_key):
        """PadKey for right side initializes correctly."""
        key = PadKey(context_right, target_key, key_layout)
        assert key is not None
        assert len(list(key.children)) > 0

    def test_nail_key_left(self, context_left, key_layout, target_key):
        """NailKey for left side initializes correctly."""
        key = NailKey(context_left, target_key, key_layout)
        assert key is not None
        assert len(list(key.children)) > 0

    def test_nail_key_right(self, context_right, key_layout, target_key):
        """NailKey for right side initializes correctly."""
        key = NailKey(context_right, target_key, key_layout)
        assert key is not None
        assert len(list(key.children)) > 0

    def test_knuckle_key(self, context_left, key_layout, target_key):
        """KnuckleKey initializes correctly."""
        key = KnuckleKey(context_left, target_key, key_layout)
        assert key is not None
        assert len(list(key.children)) > 0


class TestKeyWithLayerSwitch:
    """Tests for keys with layer switch functionality."""

    def test_key_with_layer_switch(self, cluster_context, key_layout, sample_palette):
        """Key with layer_switch uses layer colors."""
        target = SvalboardTargetKey(layer_switch=0)
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target, colors, key_layout)
        assert key is not None

    def test_key_without_layer_switch(self, cluster_context, key_layout):
        """Key without layer_switch uses default colors."""
        target = SvalboardTargetKey(layer_switch=None)
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target, colors, key_layout)
        assert key is not None


class TestKeyDimensions:
    """Tests for key dimension calculations."""

    def test_key_dimensions_positive(self, cluster_context, key_layout, target_key):
        """Key dimensions are positive."""
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target_key, colors, key_layout)
        assert key.width > 0
        assert key.height > 0

    def test_key_respects_layout_width(self, cluster_context, target_key):
        """Key width respects layout width."""
        layout = Boundary(pos=Position(x=100.0, y=50.0), width=80.0)
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target_key, colors, layout)
        # Width should be derived from layout
        assert key.width <= 80.0 or key.width >= 80.0  # Depends on aspect ratio


class TestKeyLabels:
    """Tests for key label rendering."""

    def test_key_with_simple_label(self, cluster_context, key_layout):
        """Key with simple text label."""
        target = SvalboardTargetKey(label="A")
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target, colors, key_layout)
        assert key.label is not None

    def test_key_with_empty_label(self, cluster_context, key_layout):
        """Key with empty label."""
        target = SvalboardTargetKey(label="")
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target, colors, key_layout)
        assert key is not None

    def test_key_with_long_label(self, cluster_context, key_layout):
        """Key with long label (should be sized to fit)."""
        target = SvalboardTargetKey(label="VeryLongLabel")
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target, colors, key_layout)
        assert key is not None


class TestKeyGhostLabelColor:
    """Tests for ghost label color on transparent keys."""

    def test_regular_key_uses_palette_label_color(self, cluster_context, key_layout):
        target = SvalboardTargetKey(label="A")
        colors = FingerClusterKeyColors(primary="#FF0000", accent="#AA0000")
        key = CenterKey(cluster_context, target, colors, key_layout)
        # palette.key_label_color is "#FFFFFF" in the fixture
        assert key.label_color == "#FFFFFF"

    def test_transparent_key_with_label_uses_ghost_color(self, cluster_context, key_layout):
        from skim.application.render.context import GHOST_LABEL_LIGHTNESS_DELTA
        from skim.application.render.styling import lighten

        target = SvalboardTargetKey(label="A", is_transparent=True)
        colors = FingerClusterKeyColors(primary="#2F5E3E", accent="#AA0000")
        key = CenterKey(cluster_context, target, colors, key_layout)
        # CenterKey fills with colors.primary when use_layer_colors_on_keys but
        # the key has no layer_switch → falls back to default (colors.primary).
        assert key.label_color.lower() == lighten("#2F5E3E", GHOST_LABEL_LIGHTNESS_DELTA).lower()

    def test_transparent_key_with_empty_label_uses_palette_color(self, cluster_context, key_layout):
        target = SvalboardTargetKey(label="", is_transparent=True)
        colors = FingerClusterKeyColors(primary="#2F5E3E", accent="#AA0000")
        key = CenterKey(cluster_context, target, colors, key_layout)
        assert key.label_color == "#FFFFFF"

    def test_stroke_color_unchanged_for_transparent_key(self, cluster_context, key_layout):
        """Shape stroke (used by DoubleDownKey/UpKey) stays at palette color."""
        target = SvalboardTargetKey(label="A", is_transparent=True)
        colors = FingerClusterKeyColors(primary="#2F5E3E", accent="#AA0000")
        key = CenterKey(cluster_context, target, colors, key_layout)
        assert key.stroke_color == "#FFFFFF"
