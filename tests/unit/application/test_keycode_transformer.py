"""Unit tests for KeycodeTransformer."""

import pytest

from skim.application.keycode_transformer import KeycodeTransformer


class TestBasicKeycodeTransformation:
    """Test basic keycode to label transformation."""

    def test_simple_letter_keycode(self):
        """Transform simple letter keycodes."""
        keycodes = {"KC_A": "A", "KC_B": "B"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("KC_A") == "A"
        assert transformer.transform("KC_B") == "B"

    def test_simple_number_keycode(self):
        """Transform simple number keycodes."""
        keycodes = {"KC_1": "1", "KC_2": "2"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("KC_1") == "1"
        assert transformer.transform("KC_2") == "2"

    def test_nerdFont_passthrough(self):
        """NerdFont symbols should pass through unchanged."""
        keycodes = {"KC_ESC": "%%nf-md-keyboard_esc;"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("KC_ESC") == "%%nf-md-keyboard_esc;"

    def test_unknown_keycode_returns_as_is(self):
        """Unknown keycodes should be returned as-is."""
        keycodes = {}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("UNKNOWN_KEY") == "UNKNOWN_KEY"


class TestAliasResolution:
    """Test @@KEYCODE; alias resolution."""

    def test_simple_alias(self):
        """Resolve simple alias references."""
        keycodes = {"KC_MINUS": "-", "KC_MINS": "@@KC_MINUS;"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("KC_MINS") == "-"

    def test_chained_alias(self):
        """Resolve chained alias references."""
        keycodes = {
            "KC_ENTER": "%%nf-md-keyboard_return;",
            "KC_ENT": "@@KC_ENTER;",
            "KC_RET": "@@KC_ENT;",
        }
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("KC_RET") == "%%nf-md-keyboard_return;"

    def test_circular_alias_detection(self):
        """Detect circular alias references."""
        keycodes = {"KC_A": "@@KC_B;", "KC_B": "@@KC_C;", "KC_C": "@@KC_A;"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        with pytest.raises(ValueError, match="Circular alias"):
            transformer.transform("KC_A")

    def test_self_referencing_alias(self):
        """Detect self-referencing alias."""
        keycodes = {"KC_A": "@@KC_A;"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        with pytest.raises(ValueError, match="Circular alias"):
            transformer.transform("KC_A")


class TestReversedAlias:
    """Test reversed_alias mapping (first step in transformation)."""

    def test_reversed_alias_simple(self):
        """Apply reversed alias mapping."""
        keycodes = {"KC_EXLM": "!"}
        reversed_alias = {"LSFT(KC_1)": "@@KC_EXLM;"}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("LSFT(KC_1)") == "!"

    def test_reversed_alias_with_chained_resolution(self):
        """Reversed alias with chained keycode resolution."""
        keycodes = {"KC_TILDE": "~", "KC_TILD": "@@KC_TILDE;"}
        reversed_alias = {"LSFT(KC_GRAVE)": "@@KC_TILD;"}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("LSFT(KC_GRAVE)") == "~"


class TestModifierFunctions:
    """Test modifier function parsing (S(), C(), A(), G(), etc.)."""

    def test_simple_shift_modifier(self):
        """Parse S() modifier function."""
        keycodes = {"KC_A": "A", "KC_LEFT_SHIFT": "%%nf-md-apple_keyboard_shift;"}
        reversed_alias = {}
        modifiers = {"S": "@@KC_LEFT_SHIFT;"}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("S(KC_A)") == "%%nf-md-apple_keyboard_shift; A"

    def test_control_modifier(self):
        """Parse C() modifier function."""
        keycodes = {"KC_C": "C", "KC_LEFT_CTRL": "%%nf-md-apple_keyboard_control;"}
        reversed_alias = {}
        modifiers = {"C": "@@KC_LEFT_CTRL;"}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("C(KC_C)") == "%%nf-md-apple_keyboard_control; C"

    def test_nested_modifiers(self):
        """Parse nested modifier functions like S(G(KC_A))."""
        keycodes = {
            "KC_A": "A",
            "KC_LEFT_SHIFT": "%%nf-md-apple_keyboard_shift;",
            "KC_LEFT_GUI": "%%nf-md-apple_keyboard_command;",
        }
        reversed_alias = {}
        modifiers = {"S": "@@KC_LEFT_SHIFT;", "G": "@@KC_LEFT_GUI;"}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        result = transformer.transform("S(G(KC_A))")
        assert (
            result == "%%nf-md-apple_keyboard_shift; %%nf-md-apple_keyboard_command; A"
        )

    def test_meh_modifier(self):
        """Parse MEH() modifier (Ctrl+Shift+Alt)."""
        keycodes = {
            "KC_A": "A",
            "KC_LEFT_CTRL": "%%nf-md-apple_keyboard_control;",
            "KC_LEFT_SHIFT": "%%nf-md-apple_keyboard_shift;",
            "KC_LEFT_ALT": "%%nf-md-apple_keyboard_option;",
        }
        reversed_alias = {}
        modifiers = {"MEH": "@@KC_LEFT_CTRL; @@KC_LEFT_SHIFT; @@KC_LEFT_ALT;"}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        result = transformer.transform("MEH(KC_A)")
        expected = "%%nf-md-apple_keyboard_control; %%nf-md-apple_keyboard_shift; %%nf-md-apple_keyboard_option; A"
        assert result == expected

    def test_hypr_modifier(self):
        """Parse HYPR() modifier (Ctrl+Shift+Alt+GUI)."""
        keycodes = {
            "KC_A": "A",
            "KC_LEFT_CTRL": "%%nf-md-apple_keyboard_control;",
            "KC_LEFT_SHIFT": "%%nf-md-apple_keyboard_shift;",
            "KC_LEFT_ALT": "%%nf-md-apple_keyboard_option;",
            "KC_LEFT_GUI": "%%nf-md-apple_keyboard_command;",
        }
        reversed_alias = {}
        modifiers = {
            "HYPR": "@@KC_LEFT_CTRL; @@KC_LEFT_SHIFT; @@KC_LEFT_ALT; @@KC_LEFT_GUI;"
        }
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        result = transformer.transform("HYPR(KC_A)")
        expected = "%%nf-md-apple_keyboard_control; %%nf-md-apple_keyboard_shift; %%nf-md-apple_keyboard_option; %%nf-md-apple_keyboard_command; A"
        assert result == expected


class TestLayerFunctions:
    """Test layer function parsing (MO(), TG(), DF(), TO(), etc.)."""

    def test_momentary_layer_mo(self):
        """Parse MO() layer function."""
        keycodes = {}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {"MO": "%%nf-md-layers_outline;"}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("MO(2)") == "%%nf-md-layers_outline;"

    def test_toggle_layer_tg(self):
        """Parse TG() layer function."""
        keycodes = {}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {"TG": "%%nf-md-layers_plus;"}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("TG(3)") == "%%nf-md-layers_plus;"

    def test_default_layer_df(self):
        """Parse DF() layer function."""
        keycodes = {}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {"DF": "%%nf-md-layers;"}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("DF(1)") == "%%nf-md-layers;"

    def test_layer_tap_lt(self):
        """Parse LT() layer-tap function."""
        keycodes = {"KC_SPACE": "%%nf-md-keyboard_space;"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {"LT": "%%nf-md-layers_outline;"}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        # LT(layer, keycode) - tap for keycode, hold for layer
        assert transformer.transform("LT(2,KC_SPACE)") == "%%nf-md-layers_outline;"


class TestConfigOverrides:
    """Test that config keycodes override bundled mappings."""

    def test_override_bundled_keycode(self):
        """Config keycodes should override bundled mappings."""
        keycodes = {"KC_A": "Custom A"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("KC_A") == "Custom A"

    def test_override_with_nerdFont(self):
        """Config can override with NerdFont symbols."""
        keycodes = {"KC_CUSTOM": "%%nf-custom-icon;"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("KC_CUSTOM") == "%%nf-custom-icon;"


class TestBatchTransform:
    """Test batch transformation of multiple keycodes."""

    def test_transform_list(self):
        """Transform a list of keycodes."""
        keycodes = {"KC_A": "A", "KC_B": "B", "KC_1": "1"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        input_keys = ["KC_A", "KC_B", "KC_1"]
        result = transformer.transform_list(input_keys)

        assert result == ["A", "B", "1"]

    def test_transform_list_with_modifiers(self):
        """Transform a list with modifier functions."""
        keycodes = {
            "KC_A": "A",
            "KC_B": "B",
            "KC_LEFT_SHIFT": "%%nf-md-apple_keyboard_shift;",
        }
        reversed_alias = {}
        modifiers = {"S": "@@KC_LEFT_SHIFT;"}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        input_keys = ["KC_A", "S(KC_B)", "KC_A"]
        result = transformer.transform_list(input_keys)

        assert result == ["A", "%%nf-md-apple_keyboard_shift; B", "A"]


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_keycode(self):
        """Handle empty keycode strings."""
        keycodes = {}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("") == ""

    def test_transparent_key(self):
        """Handle transparent keys."""
        keycodes = {"KC_TRANSPARENT": "", "KC_TRNS": "@@KC_TRANSPARENT;"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("KC_TRNS") == ""

    def test_no_key(self):
        """Handle KC_NO (no key assigned)."""
        keycodes = {"KC_NO": "", "XXXXXXX": "@@KC_NO;"}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.transform("KC_NO") == ""
        assert transformer.transform("XXXXXXX") == ""

    def test_malformed_function_no_closing_paren(self):
        """Handle malformed function syntax."""
        keycodes = {"KC_A": "A"}
        reversed_alias = {}
        modifiers = {"S": "@@KC_LEFT_SHIFT;"}
        layer_symbols = {}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        # Malformed input should return as-is
        assert transformer.transform("S(KC_A") == "S(KC_A"

    def test_extract_layer_id(self):
        """Extract layer ID from layer toggle keys."""
        keycodes = {}
        reversed_alias = {}
        modifiers = {}
        layer_symbols = {"MO": "%%nf-md-layers_outline;"}

        transformer = KeycodeTransformer(
            keycodes, reversed_alias, modifiers, layer_symbols
        )

        assert transformer.extract_layer_id("MO(2)") == "2"
        assert transformer.extract_layer_id("TG(5)") == "5"
        assert transformer.extract_layer_id("TG(_SYS)") == "_SYS"
        assert transformer.extract_layer_id("KC_A") is None
