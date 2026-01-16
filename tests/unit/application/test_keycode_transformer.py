"""Unit tests for KeycodeTransformer."""

import pytest

from skim.application.keycode_transformer import KeycodeTransformer


class TestBasicKeycodeTransformation:
    def test_simple_letter_keycode(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_A": "A", "KC_B": "B"},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("KC_A") == "A"
        assert transformer.transform("KC_B") == "B"

    def test_simple_number_keycode(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_1": "1", "KC_2": "2"},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("KC_1") == "1"
        assert transformer.transform("KC_2") == "2"

    def test_nerdFont_passthrough(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_ESC": "%%nf-md-keyboard_esc;"},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("KC_ESC") == "%%nf-md-keyboard_esc;"

    def test_unknown_keycode_returns_as_is(self):
        transformer = KeycodeTransformer(
            keycodes={},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("UNKNOWN_KEY") == "UNKNOWN_KEY"


class TestAliasResolution:
    def test_simple_alias(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_MINUS": "-", "KC_MINS": "@@KC_MINUS;"},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("KC_MINS") == "-"

    def test_chained_alias(self):
        transformer = KeycodeTransformer(
            keycodes={
                "KC_ENTER": "%%nf-md-keyboard_return;",
                "KC_ENT": "@@KC_ENTER;",
                "KC_RET": "@@KC_ENT;",
            },
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("KC_RET") == "%%nf-md-keyboard_return;"

    def test_circular_alias_detection(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_A": "@@KC_B;", "KC_B": "@@KC_C;", "KC_C": "@@KC_A;"},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        with pytest.raises(ValueError, match="Circular alias"):
            transformer.transform("KC_A")

    def test_self_referencing_alias(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_A": "@@KC_A;"},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        with pytest.raises(ValueError, match="Circular alias"):
            transformer.transform("KC_A")


class TestReversedAlias:
    def test_reversed_alias_applied_first(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_EXLM": "!"},
            reversed_alias={"LSFT(KC_1)": "@@KC_EXLM;"},
            macro_functions={"LSFT": "@@KC_LEFT_SHIFT; @0;"},
            modifier_union={},
        )

        assert transformer.transform("LSFT(KC_1)") == "!"

    def test_reversed_alias_with_chained_resolution(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_TILDE": "~", "KC_TILD": "@@KC_TILDE;"},
            reversed_alias={"LSFT(KC_GRAVE)": "@@KC_TILD;"},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("LSFT(KC_GRAVE)") == "~"


class TestMacroFunctions:
    def test_simple_shift_modifier(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_A": "A", "KC_LEFT_SHIFT": "Shift"},
            reversed_alias={},
            macro_functions={"S": "@@KC_LEFT_SHIFT; @0;"},
            modifier_union={},
        )

        assert transformer.transform("S(KC_A)") == "Shift A"

    def test_control_modifier(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_C": "C", "KC_LEFT_CTRL": "Ctrl"},
            reversed_alias={},
            macro_functions={"C": "@@KC_LEFT_CTRL; @0;"},
            modifier_union={},
        )

        assert transformer.transform("C(KC_C)") == "Ctrl C"

    def test_nested_modifiers(self):
        transformer = KeycodeTransformer(
            keycodes={
                "KC_A": "A",
                "KC_LEFT_SHIFT": "Shift",
                "KC_LEFT_GUI": "Cmd",
            },
            reversed_alias={},
            macro_functions={"S": "@@KC_LEFT_SHIFT; @0;", "G": "@@KC_LEFT_GUI; @0;"},
            modifier_union={},
        )

        result = transformer.transform("S(G(KC_A))")
        assert result == "Shift Cmd A"

    def test_meh_modifier(self):
        transformer = KeycodeTransformer(
            keycodes={
                "KC_A": "A",
                "KC_LEFT_CTRL": "Ctrl",
                "KC_LEFT_SHIFT": "Shift",
                "KC_LEFT_ALT": "Alt",
            },
            reversed_alias={},
            macro_functions={
                "MEH": "@@KC_LEFT_CTRL; @@KC_LEFT_SHIFT; @@KC_LEFT_ALT; @0;"
            },
            modifier_union={},
        )

        result = transformer.transform("MEH(KC_A)")
        assert result == "Ctrl Shift Alt A"

    def test_momentary_layer_mo(self):
        transformer = KeycodeTransformer(
            keycodes={},
            reversed_alias={},
            macro_functions={"MO": "%%nf-md-layers_outline; #0;"},
            modifier_union={},
        )

        assert transformer.transform("MO(2)") == "%%nf-md-layers_outline; 3"

    def test_toggle_layer_tg(self):
        transformer = KeycodeTransformer(
            keycodes={},
            reversed_alias={},
            macro_functions={"TG": "%%nf-md-layers_triple; #0;"},
            modifier_union={},
        )

        assert transformer.transform("TG(3)") == "%%nf-md-layers_triple; 4"

    def test_layer_tap_lt(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_SPACE": "Space"},
            reversed_alias={},
            macro_functions={"LT": "%%nf-md-layers_outline; #0;|;@1;"},
            modifier_union={},
        )

        result = transformer.transform("LT(2,KC_SPACE)")
        assert result == "%%nf-md-layers_outline; 3│Space"

    def test_modifier_tap_lsft_t(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_A": "A", "KC_LEFT_SHIFT": "Shift"},
            reversed_alias={},
            macro_functions={"LSFT_T": "@@KC_LEFT_SHIFT;|;@0;"},
            modifier_union={},
        )

        result = transformer.transform("LSFT_T(KC_A)")
        assert result == "Shift│A"

    def test_unknown_macro_function_returns_as_is(self):
        transformer = KeycodeTransformer(
            keycodes={},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("UNKNOWN_FUNC(KC_A)") == "UNKNOWN_FUNC(KC_A)"


class TestModifierUnion:
    def test_single_modifier_bit(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_LEFT_CTRL": "Ctrl"},
            reversed_alias={},
            macro_functions={"OSM": "@0;¹"},
            modifier_union={"MOD_LCTL": "@@KC_LEFT_CTRL;"},
        )

        result = transformer.transform("OSM(MOD_LCTL)")
        assert result == "Ctrl¹"

    def test_combined_modifier_bits(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_LEFT_CTRL": "Ctrl", "KC_LEFT_SHIFT": "Shift"},
            reversed_alias={},
            macro_functions={"OSM": "@0;¹"},
            modifier_union={
                "MOD_LCTL": "@@KC_LEFT_CTRL;",
                "MOD_LSFT": "@@KC_LEFT_SHIFT;",
            },
        )

        result = transformer.transform("OSM(MOD_LCTL|MOD_LSFT)")
        assert result == "Ctrl Shift¹"

    def test_lm_with_modifier_union(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_LEFT_SHIFT": "Shift"},
            reversed_alias={},
            macro_functions={"LM": "@1; %%nf-md-layers_outline; #0;"},
            modifier_union={"MOD_LSFT": "@@KC_LEFT_SHIFT;"},
        )

        result = transformer.transform("LM(2,MOD_LSFT)")
        assert result == "Shift %%nf-md-layers_outline; 3"


class TestBatchTransform:
    def test_transform_list(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_A": "A", "KC_B": "B", "KC_1": "1"},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        input_keys = ["KC_A", "KC_B", "KC_1"]
        result = transformer.transform_list(input_keys)

        assert result == ["A", "B", "1"]

    def test_transform_list_with_modifiers(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_A": "A", "KC_B": "B", "KC_LEFT_SHIFT": "Shift"},
            reversed_alias={},
            macro_functions={"S": "@@KC_LEFT_SHIFT; @0;"},
            modifier_union={},
        )

        input_keys = ["KC_A", "S(KC_B)", "KC_A"]
        result = transformer.transform_list(input_keys)

        assert result == ["A", "Shift B", "A"]


class TestEdgeCases:
    def test_empty_keycode(self):
        transformer = KeycodeTransformer(
            keycodes={},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("") == ""

    def test_transparent_key(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_TRANSPARENT": "", "KC_TRNS": "@@KC_TRANSPARENT;"},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("KC_TRNS") == ""

    def test_no_key(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_NO": "", "XXXXXXX": "@@KC_NO;"},
            reversed_alias={},
            macro_functions={},
            modifier_union={},
        )

        assert transformer.transform("KC_NO") == ""
        assert transformer.transform("XXXXXXX") == ""

    def test_malformed_function_no_closing_paren(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_A": "A"},
            reversed_alias={},
            macro_functions={"S": "@@KC_LEFT_SHIFT; @0;"},
            modifier_union={},
        )

        assert transformer.transform("S(KC_A") == "S(KC_A"

    def test_extract_layer_id(self):
        transformer = KeycodeTransformer(
            keycodes={},
            reversed_alias={},
            macro_functions={"MO": "%%nf-md-layers_outline; #0;"},
            modifier_union={},
        )

        assert transformer.extract_layer_id("MO(2)") == "2"
        assert transformer.extract_layer_id("TG(5)") == "5"
        assert transformer.extract_layer_id("TG(_SYS)") == "_SYS"
        assert transformer.extract_layer_id("LT(1,KC_SPACE)") == "1"
        assert transformer.extract_layer_id("KC_A") is None


class TestFunctionArgumentParsing:
    def test_nested_function_as_argument(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_A": "A", "KC_LEFT_SHIFT": "Shift"},
            reversed_alias={},
            macro_functions={
                "LT": "%%nf-md-layers_outline; #0;|;@1;",
                "S": "@@KC_LEFT_SHIFT; @0;",
            },
            modifier_union={},
        )

        result = transformer.transform("LT(1,S(KC_A))")
        assert result == "%%nf-md-layers_outline; 2│Shift A"

    def test_multiple_arguments_with_spaces(self):
        transformer = KeycodeTransformer(
            keycodes={"KC_SPACE": "Space"},
            reversed_alias={},
            macro_functions={"LT": "%%nf-md-layers_outline; #0;|;@1;"},
            modifier_union={},
        )

        result = transformer.transform("LT( 2 , KC_SPACE )")
        assert result == "%%nf-md-layers_outline; 3│Space"

    def test_deeply_nested_functions(self):
        transformer = KeycodeTransformer(
            keycodes={
                "KC_A": "A",
                "KC_LEFT_SHIFT": "Shift",
                "KC_LEFT_CTRL": "Ctrl",
            },
            reversed_alias={},
            macro_functions={
                "S": "@@KC_LEFT_SHIFT; @0;",
                "C": "@@KC_LEFT_CTRL; @0;",
            },
            modifier_union={},
        )

        result = transformer.transform("S(C(KC_A))")
        assert result == "Shift Ctrl A"
