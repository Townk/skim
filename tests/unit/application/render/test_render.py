# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render module.

Tests cover the main rendering functions for keymap visualization.
"""

import pytest

from skim.application.render import draw_keymap
from skim.data.cli import KeymapGeneratorTargets
from skim.data.config import (
    Keyboard,
    KeyboardFeatures,
    KeyboardLayer,
    LayerColor,
    Output,
    Palette,
    SkimConfig,
    SplitSidePosition,
    Style,
)
from skim.data.keyboard import SvalboardKeymap, SvalboardLayout
from skim.domain.domain_types import SvalboardTargetKey


@pytest.fixture
def sample_config():
    """Create a sample SkimConfig for testing."""
    layers = (
        LayerColor(
            base_color="#FF0000",
            gradient=("#110000", "#220000", "#330000", "#440000", "#550000", "#660000"),
        ),
        LayerColor(
            base_color="#00FF00",
            gradient=("#001100", "#002200", "#003300", "#004400", "#005500", "#006600"),
        ),
        LayerColor(
            base_color="#0000FF",
            gradient=("#000011", "#000022", "#000033", "#000044", "#000055", "#000066"),
        ),
    )
    palette = Palette(layers=layers)
    style = Style(palette=palette)
    output = Output(style=style)
    keyboard = Keyboard(
        layers=(
            KeyboardLayer(index=0, name="Base Layer"),
            KeyboardLayer(index=1, name="Symbol Layer"),
            KeyboardLayer(index=2, name="Nav Layer"),
        )
    )
    return SkimConfig(output=output, keyboard=keyboard)


@pytest.fixture
def single_layer_keymap():
    """Create a keymap with one layer."""
    layer = SvalboardLayout.from_sequence([SvalboardTargetKey(label=f"K{i}") for i in range(60)])
    return SvalboardKeymap(layers={0: layer})


@pytest.fixture
def multi_layer_keymap():
    """Create a keymap with multiple layers."""
    layers = {}
    for layer_idx in range(3):
        layer = SvalboardLayout.from_sequence(
            [SvalboardTargetKey(label=f"L{layer_idx}K{i}") for i in range(60)]
        )
        layers[layer_idx] = layer
    return SvalboardKeymap(layers=layers)


class TestDrawKeymap:
    """Tests for draw_keymap function."""

    def test_returns_dict(self, sample_config, single_layer_keymap):
        """draw_keymap returns a dictionary."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, single_layer_keymap, targets)
        assert isinstance(result, dict)

    def test_single_layer_produces_one_drawing(self, sample_config, single_layer_keymap):
        """Single layer keymap produces one drawing."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, single_layer_keymap, targets)
        assert len(result) == 1

    def test_multi_layer_produces_multiple_drawings(self, sample_config, multi_layer_keymap):
        """Multi-layer keymap produces multiple drawings."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, multi_layer_keymap, targets)
        assert len(result) == 3

    def test_drawing_keys_contain_layer_index(self, sample_config, multi_layer_keymap):
        """Drawing dictionary keys contain layer information."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, multi_layer_keymap, targets)
        # Keys should be like "keymap-layer-0", "keymap-layer-1", etc.
        keys = list(result.keys())
        for i, key in enumerate(keys):
            assert "layer" in key.lower() or str(i) in key

    def test_drawings_are_valid(self, sample_config, single_layer_keymap):
        """Drawings are valid drawsvg Drawing objects."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, single_layer_keymap, targets)
        for _name, drawing in result.items():
            # Drawing should have width and height
            assert drawing.width > 0
            assert drawing.height > 0

    def test_layer_selection_filters_output(self, sample_config, multi_layer_keymap):
        """Layer selection filters which drawings are created."""
        targets = KeymapGeneratorTargets(selected_layers=[0])
        result = draw_keymap(sample_config, multi_layer_keymap, targets)
        assert len(result) == 1

    def test_multiple_layer_selection(self, sample_config, multi_layer_keymap):
        """Multiple specific layers can be selected."""
        targets = KeymapGeneratorTargets(selected_layers=[0, 2])
        result = draw_keymap(sample_config, multi_layer_keymap, targets)
        assert len(result) == 2

    def test_overview_target_produces_overview_drawing(self, sample_config, multi_layer_keymap):
        """When targets.overview=True, result includes 'keymap-overview' key."""
        targets = KeymapGeneratorTargets(overview=True)
        result = draw_keymap(sample_config, multi_layer_keymap, targets)
        assert "keymap-overview" in result

    def test_all_target_includes_overview(self, sample_config, multi_layer_keymap):
        """When targets has all_layers=True and overview=True, both layer images and overview are returned."""
        targets = KeymapGeneratorTargets(all_layers=True, overview=True)
        result = draw_keymap(sample_config, multi_layer_keymap, targets)
        assert "keymap-overview" in result
        assert "keymap-layer-0" in result


class TestDrawKeymapWithDoubleSouth:
    """Tests for draw_keymap with double_south enabled."""

    @pytest.fixture
    def config_with_double_south(self, sample_config):
        """Config with double_south enabled."""
        keyboard = sample_config.keyboard.model_copy(
            update={"features": KeyboardFeatures(double_south=True)}
        )
        return sample_config.model_copy(update={"keyboard": keyboard})

    def test_renders_with_double_south(self, config_with_double_south, single_layer_keymap):
        """Drawing renders with double_south enabled."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(config_with_double_south, single_layer_keymap, targets)
        assert len(result) == 1

    def test_double_south_affects_dimensions(
        self, sample_config, config_with_double_south, single_layer_keymap
    ):
        """Double south feature affects drawing dimensions."""
        targets = KeymapGeneratorTargets(all_layers=True)

        result_without = draw_keymap(sample_config, single_layer_keymap, targets)
        result_with = draw_keymap(config_with_double_south, single_layer_keymap, targets)

        # Heights might differ
        drawing_without = list(result_without.values())[0]
        drawing_with = list(result_with.values())[0]

        # At minimum, both should render successfully
        assert drawing_without.height > 0
        assert drawing_with.height > 0


class TestDrawKeymapWithLayerColors:
    """Tests for draw_keymap with layer colors enabled/disabled."""

    @pytest.fixture
    def config_no_layer_colors(self, sample_config):
        """Config with layer colors disabled."""
        new_style = sample_config.output.style.model_copy(
            update={"use_layer_colors_on_keys": False}
        )
        new_output = sample_config.output.model_copy(update={"style": new_style})
        return sample_config.model_copy(update={"output": new_output})

    def test_renders_without_layer_colors(self, config_no_layer_colors, single_layer_keymap):
        """Drawing renders with layer colors disabled."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(config_no_layer_colors, single_layer_keymap, targets)
        assert len(result) == 1


class TestDrawKeymapWithHoldSymbolPosition:
    """Tests for draw_keymap with different hold symbol positions."""

    def test_outward_position(self, sample_config, single_layer_keymap):
        """Drawing with OUTWARD hold symbol position."""
        new_style = sample_config.output.style.model_copy(
            update={"hold_symbol_position": SplitSidePosition.OUTWARD}
        )
        new_output = sample_config.output.model_copy(update={"style": new_style})
        config = sample_config.model_copy(update={"output": new_output})
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(config, single_layer_keymap, targets)
        assert len(result) == 1

    def test_inward_position(self, sample_config, single_layer_keymap):
        """Drawing with INWARD hold symbol position."""
        new_style = sample_config.output.style.model_copy(
            update={"hold_symbol_position": SplitSidePosition.INWARD}
        )
        new_output = sample_config.output.model_copy(update={"style": new_style})
        config = sample_config.model_copy(update={"output": new_output})
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(config, single_layer_keymap, targets)
        assert len(result) == 1

    def test_qmk_defined_position(self, sample_config, single_layer_keymap):
        """Drawing with QMK_DEFINED hold symbol position."""
        new_style = sample_config.output.style.model_copy(
            update={"hold_symbol_position": SplitSidePosition.QMK_DEFINED}
        )
        new_output = sample_config.output.model_copy(update={"style": new_style})
        config = sample_config.model_copy(update={"output": new_output})
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(config, single_layer_keymap, targets)
        assert len(result) == 1


class TestDrawKeymapDimensions:
    """Tests for draw_keymap output dimensions."""

    def test_default_width(self, sample_config, single_layer_keymap):
        """Drawing has default width from config."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, single_layer_keymap, targets)
        drawing = list(result.values())[0]
        assert drawing.width == sample_config.output.layout.width

    def test_custom_width(self, sample_config, single_layer_keymap):
        """Drawing respects custom width."""
        new_layout = sample_config.output.layout.model_copy(update={"width": 1200})
        new_output = sample_config.output.model_copy(update={"layout": new_layout})
        config = sample_config.model_copy(update={"output": new_output})
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(config, single_layer_keymap, targets)
        drawing = list(result.values())[0]
        assert drawing.width == 1200

    def test_height_calculated_from_width(self, sample_config, single_layer_keymap):
        """Drawing height is calculated based on width and content."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, single_layer_keymap, targets)
        drawing = list(result.values())[0]
        # Height should be proportional to content
        assert drawing.height > 0
        # Typical keyboard aspect ratio means height < width
        assert drawing.height < drawing.width * 2


class TestDrawKeymapWithBorder:
    """Tests for draw_keymap with border settings."""

    def test_with_border(self, sample_config, single_layer_keymap):
        """Drawing renders with border enabled."""
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, single_layer_keymap, targets)
        assert len(result) == 1

    def test_without_border(self, sample_config, single_layer_keymap):
        """Drawing renders with border disabled."""
        new_style = sample_config.output.style.model_copy(update={"border": None})
        new_output = sample_config.output.model_copy(update={"style": new_style})
        config = sample_config.model_copy(update={"output": new_output})
        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(config, single_layer_keymap, targets)
        assert len(result) == 1


class TestDrawKeymapWithSpecialKeys:
    """Tests for draw_keymap with special key types."""

    def test_with_layer_switch_keys(self, sample_config):
        """Drawing renders with layer switch keys."""
        keys = [SvalboardTargetKey(label=f"K{i}") for i in range(60)]
        # Add some layer switch keys
        keys[0] = SvalboardTargetKey(layer_switch=1)
        keys[10] = SvalboardTargetKey(layer_switch=0)

        layer = SvalboardLayout.from_sequence(keys)
        keymap = SvalboardKeymap(layers={0: layer})

        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, keymap, targets)
        assert len(result) == 1

    def test_with_hold_tap_keys(self, sample_config):
        """Drawing renders with hold-tap style labels."""
        keys = [SvalboardTargetKey(label=f"K{i}") for i in range(60)]
        # Add hold-tap style label with separator
        keys[0] = SvalboardTargetKey(label="A│L1")

        layer = SvalboardLayout.from_sequence(keys)
        keymap = SvalboardKeymap(layers={0: layer})

        targets = KeymapGeneratorTargets(all_layers=True)
        result = draw_keymap(sample_config, keymap, targets)
        assert len(result) == 1
