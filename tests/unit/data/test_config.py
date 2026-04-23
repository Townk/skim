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
                KeyboardLayer(index=0, id="base", label="1", name="Base"),
                KeyboardLayer(index=1, id="nav", label="N", name="Navigation"),
            ]
        )
        assert keyboard.layer_index("base") == 0
        assert keyboard.layer_index("nav") == 1

    def test_layer_index_without_ids_uses_string_index(self):
        """layer_index uses string index for layers without explicit ids."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=1, label="2", name="Symbols"),
            ]
        )
        assert keyboard.layer_index("0") == 0
        assert keyboard.layer_index("1") == 1

    def test_layer_index_returns_qmk_index_not_position(self):
        """layer_index returns the QMK firmware index, not the list position."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, id="base", label="1", name="Base"),
                KeyboardLayer(index=1, id="nav", label="N", name="Navigation"),
                KeyboardLayer(index=14, id="sys", label="S", name="System"),
                KeyboardLayer(index=15, id="mouse", label="M", name="Mouse"),
            ]
        )
        assert keyboard.layer_index("sys") == 14
        assert keyboard.layer_index("mouse") == 15

    def test_layer_index_without_ids_returns_qmk_index(self):
        """layer_index returns QMK index for layers without explicit ids."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=15, label="M", name="Mouse"),
            ]
        )
        assert keyboard.layer_index("0") == 0
        assert keyboard.layer_index("1") == 15

    def test_layer_index_unknown_key_returns_none(self):
        """layer_index returns None for unknown keys."""
        keyboard = Keyboard(layers=[KeyboardLayer(index=0, id="base", label="1", name="Base")])
        assert keyboard.layer_index("unknown") is None

    def test_layer_index_with_none_returns_none(self):
        """layer_index returns None when key is None."""
        keyboard = Keyboard(layers=[KeyboardLayer(index=0, label="1", name="Base")])
        assert keyboard.layer_index(None) is None


class TestQmkIndexToPosition:
    """Tests for Keyboard.qmk_index_to_position method."""

    def test_qmk_index_to_position_sequential(self):
        """qmk_index_to_position returns position for sequential indices."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=1, label="2", name="Symbols"),
                KeyboardLayer(index=2, label="3", name="Nav"),
            ]
        )
        assert keyboard.qmk_index_to_position(0) == 0
        assert keyboard.qmk_index_to_position(1) == 1
        assert keyboard.qmk_index_to_position(2) == 2

    def test_qmk_index_to_position_non_sequential(self):
        """qmk_index_to_position returns position for non-sequential indices."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=1, label="2", name="Symbols"),
                KeyboardLayer(index=15, label="M", name="Mouse"),
            ]
        )
        assert keyboard.qmk_index_to_position(0) == 0
        assert keyboard.qmk_index_to_position(1) == 1
        assert keyboard.qmk_index_to_position(15) == 2
        assert keyboard.qmk_index_to_position(5) is None


class TestLayerQmkIndex:
    """Tests for Keyboard.layer_qmk_index method."""

    def test_layer_qmk_index(self):
        """layer_qmk_index returns the QMK index for a given position."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=1, label="2", name="Symbols"),
                KeyboardLayer(index=2, label="3", name="Nav"),
            ]
        )
        assert keyboard.layer_qmk_index(0) == 0
        assert keyboard.layer_qmk_index(1) == 1
        assert keyboard.layer_qmk_index(2) == 2

    def test_layer_index_with_non_sequential_indices(self):
        """layer_qmk_index returns correct QMK index for non-sequential layers."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=1, label="2", name="Symbols"),
                KeyboardLayer(index=15, label="M", name="Mouse"),
            ]
        )
        assert keyboard.layer_qmk_index(0) == 0
        assert keyboard.layer_qmk_index(1) == 1
        assert keyboard.layer_qmk_index(2) == 15


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
    """Tests for KeyboardLayer.variant field."""

    def test_variant_defaults_to_none(self):
        """variant defaults to None when not specified."""
        layer = KeyboardLayer(index=0, label="1", name="Letters")
        assert layer.variant is None

    def test_variant_can_be_set(self):
        """variant can be set to a string value."""
        layer = KeyboardLayer(index=0, label="1", name="Letters", variant="COLEMAK")
        assert layer.variant == "COLEMAK"

    def test_variant_included_in_model_dump(self):
        """variant is included in model_dump output."""
        layer = KeyboardLayer(index=0, label="1", name="Letters", variant="COLEMAK")
        dumped = layer.model_dump()
        assert "variant" in dumped
        assert dumped["variant"] == "COLEMAK"


class TestOutputKeymapTitle:
    """Tests for Output.keymap_title field."""

    def test_keymap_title_defaults_to_none(self):
        output = Output()
        assert output.keymap_title is None

    def test_keymap_title_can_be_set(self):
        output = Output(keymap_title="My Custom Keymap")
        assert output.keymap_title == "My Custom Keymap"


class TestOutputCopyright:
    """Tests for Output.copyright field."""

    def test_copyright_defaults_to_none(self):
        """copyright defaults to None when not specified."""
        output = Output()
        assert output.copyright is None

    def test_copyright_can_be_set(self):
        """copyright can be set to a string value."""
        output = Output(copyright="© 2026 My Layout")
        assert output.copyright == "© 2026 My Layout"
