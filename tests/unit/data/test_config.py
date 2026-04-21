# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.data.config module.

Tests cover LayerColor methods that are not exercised by other tests:
- __getitem__ for gradient-less colors and error handling
- __str__ representation
- Keyboard.layer_index logic
"""

import pytest

from skim.data.config import Keyboard, KeyboardLayer, LayerColor, Output, Style


class TestLayerColorGetItem:
    """Tests for LayerColor.__getitem__ indexing."""

    def test_getitem_without_gradient_returns_base_color(self):
        """When no gradient, any index returns base_color."""
        layer = LayerColor(base_color="#FF0000")
        assert layer[0] == "#FF0000"

    def test_getitem_with_gradient_index_out_of_range_raises(self):
        """IndexError raised for out-of-range gradient index."""
        layer = LayerColor(
            base_color="#FF0000",
            gradient=("#000", "#111", "#222", "#333", "#444", "#555"),
        )
        with pytest.raises(IndexError) as exc_info:
            _ = layer[6]
        assert "Gradient index 6 out of range (0-5)" in str(exc_info.value)


class TestLayerColorStr:
    """Tests for LayerColor.__str__ representation."""

    def test_str_without_gradient(self):
        """String representation with only base_color."""
        layer = LayerColor(base_color="#FFF")
        assert str(layer) == '["#FFF"]'

    def test_str_with_gradient(self):
        """String representation with gradient colors."""
        layer = LayerColor(
            base_color="#FF0000",
            gradient=("#000", "#111", "#222", "#333", "#444", "#555"),
        )
        result = str(layer)
        assert result == '["#000", "#111", "#222", "#333", "#444", "#555"]'


class TestKeyboardLayerIndex:
    """Tests for Keyboard.layer_index method."""

    def test_layer_index_with_explicit_ids(self):
        """layer_index returns index for layers with explicit ids."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(id="base", label="1", name="Base"),
                KeyboardLayer(id="nav", label="N", name="Navigation"),
            ]
        )
        assert keyboard.layer_index("base") == 0
        assert keyboard.layer_index("nav") == 1

    def test_layer_index_without_ids_uses_string_index(self):
        """layer_index uses string index for layers without explicit ids."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(label="1", name="Base"),
                KeyboardLayer(label="2", name="Symbols"),
            ]
        )
        assert keyboard.layer_index("0") == 0
        assert keyboard.layer_index("1") == 1

    def test_layer_index_unknown_key_returns_none(self):
        """layer_index returns None for unknown keys."""
        keyboard = Keyboard(layers=[KeyboardLayer(id="base", label="1", name="Base")])
        assert keyboard.layer_index("unknown") is None

    def test_layer_index_with_none_returns_none(self):
        """layer_index returns None when key is None."""
        keyboard = Keyboard(layers=[KeyboardLayer(label="1", name="Base")])
        assert keyboard.layer_index(None) is None


class TestStyleShowLayerIndicators:
    """Tests for Style.show_layer_indicators field."""

    def test_default_is_true(self):
        """show_layer_indicators defaults to True."""
        style = Style()
        assert style.show_layer_indicators is True

    def test_can_be_set_to_false(self):
        """show_layer_indicators can be explicitly set to False."""
        style = Style(show_layer_indicators=False)
        assert style.show_layer_indicators is False


class TestKeyboardLayerSubtitle:
    """Tests for KeyboardLayer.subtitle field."""

    def test_subtitle_defaults_to_none(self):
        """subtitle defaults to None when not specified."""
        layer = KeyboardLayer(label="1", name="Letters")
        assert layer.subtitle is None

    def test_subtitle_can_be_set(self):
        """subtitle can be set to a string value."""
        layer = KeyboardLayer(label="1", name="Letters", subtitle="COLEMAK")
        assert layer.subtitle == "COLEMAK"

    def test_subtitle_included_in_model_dump(self):
        """subtitle is included in model_dump output."""
        layer = KeyboardLayer(label="1", name="Letters", subtitle="COLEMAK")
        dumped = layer.model_dump()
        assert "subtitle" in dumped
        assert dumped["subtitle"] == "COLEMAK"
