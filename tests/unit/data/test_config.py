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
from pydantic import ValidationError

from skim.data.config import (
    Keyboard,
    KeyboardLayer,
    LayerColor,
    Macro,
    Output,
    Style,
    TapDance,
)


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
                KeyboardLayer(index=0, id="base", name="Base"),
                KeyboardLayer(index=1, id="nav", name="Navigation"),
            ]
        )
        assert keyboard.layer_index("base") == 0
        assert keyboard.layer_index("nav") == 1

    def test_layer_index_without_ids_uses_string_index(self):
        """layer_index uses string index for layers without explicit ids."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, name="Base"),
                KeyboardLayer(index=1, name="Symbols"),
            ]
        )
        assert keyboard.layer_index("0") == 0
        assert keyboard.layer_index("1") == 1

    def test_layer_index_returns_qmk_index_not_position(self):
        """layer_index returns the QMK firmware index, not the list position."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, id="base", name="Base"),
                KeyboardLayer(index=1, id="nav", name="Navigation"),
                KeyboardLayer(index=14, id="sys", name="System"),
                KeyboardLayer(index=15, id="mouse", name="Mouse"),
            ]
        )
        assert keyboard.layer_index("sys") == 14
        assert keyboard.layer_index("mouse") == 15

    def test_layer_index_without_ids_returns_qmk_index(self):
        """layer_index returns QMK index for layers without explicit ids."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, name="Base"),
                KeyboardLayer(index=15, name="Mouse"),
            ]
        )
        assert keyboard.layer_index("0") == 0
        assert keyboard.layer_index("1") == 15

    def test_layer_index_unknown_key_returns_none(self):
        """layer_index returns None for unknown keys."""
        keyboard = Keyboard(layers=[KeyboardLayer(index=0, id="base", name="Base")])
        assert keyboard.layer_index("unknown") is None

    def test_layer_index_with_none_returns_none(self):
        """layer_index returns None when key is None."""
        keyboard = Keyboard(layers=[KeyboardLayer(index=0, name="Base")])
        assert keyboard.layer_index(None) is None


class TestQmkIndexToPosition:
    """Tests for Keyboard.qmk_index_to_position method."""

    def test_qmk_index_to_position_sequential(self):
        """qmk_index_to_position returns position for sequential indices."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, name="Base"),
                KeyboardLayer(index=1, name="Symbols"),
                KeyboardLayer(index=2, name="Nav"),
            ]
        )
        assert keyboard.qmk_index_to_position(0) == 0
        assert keyboard.qmk_index_to_position(1) == 1
        assert keyboard.qmk_index_to_position(2) == 2

    def test_qmk_index_to_position_non_sequential(self):
        """qmk_index_to_position returns position for non-sequential indices."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, name="Base"),
                KeyboardLayer(index=1, name="Symbols"),
                KeyboardLayer(index=15, name="Mouse"),
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
                KeyboardLayer(index=0, name="Base"),
                KeyboardLayer(index=1, name="Symbols"),
                KeyboardLayer(index=2, name="Nav"),
            ]
        )
        assert keyboard.layer_qmk_index(0) == 0
        assert keyboard.layer_qmk_index(1) == 1
        assert keyboard.layer_qmk_index(2) == 2

    def test_layer_index_with_non_sequential_indices(self):
        """layer_qmk_index returns correct QMK index for non-sequential layers."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, name="Base"),
                KeyboardLayer(index=1, name="Symbols"),
                KeyboardLayer(index=15, name="Mouse"),
            ]
        )
        assert keyboard.layer_qmk_index(0) == 0
        assert keyboard.layer_qmk_index(1) == 1
        assert keyboard.layer_qmk_index(2) == 15


class TestStyleShowLayerIndicators:
    """Tests for Style.layer_indicator.show field."""

    def test_default_is_true(self):
        """layer_indicator.show defaults to True."""
        style = Style()
        assert style.layer_indicator.show is True

    def test_can_be_set_to_false(self):
        """layer_indicator.show can be explicitly set to False."""
        from skim.data import LayerIndicator

        style = Style(layer_indicator=LayerIndicator(show=False))
        assert style.layer_indicator.show is False


class TestKeyboardLayerSubtitle:
    """Tests for KeyboardLayer.variant field."""

    def test_variant_defaults_to_none(self):
        """variant defaults to None when not specified."""
        layer = KeyboardLayer(index=0, name="Letters")
        assert layer.variant is None

    def test_variant_can_be_set(self):
        """variant can be set to a string value."""
        layer = KeyboardLayer(index=0, name="Letters", variant="COLEMAK")
        assert layer.variant == "COLEMAK"

    def test_variant_included_in_model_dump(self):
        """variant is included in model_dump output."""
        layer = KeyboardLayer(index=0, name="Letters", variant="COLEMAK")
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


class TestStyleShowLayerConnectors:
    """Tests for Style.layer_connector.show field."""

    def test_default_is_true(self):
        """layer_connector.show defaults to True."""
        style = Style()
        assert style.layer_connector.show is True

    def test_can_set_to_false(self):
        """layer_connector.show can be set to False."""
        from skim.data import LayerConnector

        style = Style(layer_connector=LayerConnector(show=False))
        assert style.layer_connector.show is False


class TestStyleShowTransparentFallthrough:
    """Tests for Style.show_transparent_fallthrough field."""

    def test_default_is_true(self):
        """show_transparent_fallthrough defaults to True (opt-out)."""
        assert Style().show_transparent_fallthrough is True

    def test_can_set_to_false(self):
        """show_transparent_fallthrough can be set to False."""
        assert Style(show_transparent_fallthrough=False).show_transparent_fallthrough is False


class TestMacro:
    def test_minimal_construction(self):
        m = Macro(id="0")
        assert m.id == "0"
        assert m.name is None
        assert m.preview == ""

    def test_full_construction(self):
        m = Macro(id="3", name="Em-dash", preview="[↓ E]")
        assert m.id == "3"
        assert m.name == "Em-dash"
        assert m.preview == "[↓ E]"

    def test_is_frozen(self):
        m = Macro(id="0")
        with pytest.raises(ValidationError):
            m.id = "1"  # type: ignore[misc]

    def test_is_hashable(self):
        a = Macro(id="0", name="foo", preview="bar")
        b = Macro(id="0", name="foo", preview="bar")
        assert hash(a) == hash(b)


class TestTapDance:
    def test_minimal_construction(self):
        td = TapDance(id="0")
        assert td.id == "0"
        assert td.name is None
        assert td.preview == ""

    def test_full_construction(self):
        td = TapDance(id="2", name="Quick shift", preview="t:Q h:⇧")
        assert td.name == "Quick shift"
        assert td.preview == "t:Q h:⇧"

    def test_is_frozen(self):
        td = TapDance(id="0")
        with pytest.raises(ValidationError):
            td.preview = "x"  # type: ignore[misc]


class TestKeycodesMacrosAndTapDances:
    def test_defaults_empty(self):
        from skim.data.config import Keycodes

        k = Keycodes()
        assert k.macros == ()
        assert k.tap_dances == ()

    def test_accepts_lists_and_coerces_to_tuples(self):
        from skim.data.config import Keycodes

        k = Keycodes(
            macros=[Macro(id="0"), Macro(id="1", name="x")],
            tap_dances=[TapDance(id="0", preview="t:Q")],
        )
        assert isinstance(k.macros, tuple)
        assert isinstance(k.tap_dances, tuple)
        assert k.macros[1].name == "x"

    def test_round_trips_through_model_dump(self):
        from skim.data.config import Keycodes

        original = Keycodes(
            macros=(Macro(id="0", name="A", preview="[↓ Q]"),),
            tap_dances=(TapDance(id="3", name=None, preview="t:Q"),),
        )
        dumped = original.model_dump(mode="json")
        rebuilt = Keycodes.model_validate(dumped)
        assert rebuilt == original


class TestPalette:
    def test_macro_and_tap_dance_color_defaults(self):
        from skim.data.config import Palette

        p = Palette()
        assert p.macro_color == "#89511C"
        assert p.tap_dance_color == "#41687F"

    def test_macro_and_tap_dance_color_overrides_round_trip(self):
        from skim.data.config import Palette

        p = Palette(macro_color="#FF0000", tap_dance_color="#00FF00")
        dumped = p.model_dump(mode="json")
        rebuilt = Palette.model_validate(dumped)
        assert rebuilt.macro_color == "#FF0000"
        assert rebuilt.tap_dance_color == "#00FF00"
