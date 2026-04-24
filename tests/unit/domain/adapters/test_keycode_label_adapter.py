# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import pytest

from skim.data.config import Keyboard, KeyboardLayer
from skim.domain.adapters.keycode_label_adapter import (
    _LAYER_FUNCTIONS,
    _LAYER_FUNCTIONS_HOLD,
    KeycodeLabelAdapter,
)
from skim.domain.domain_types import SEPARATOR_CHAR


def make_keyboard_with_layers(count: int) -> Keyboard:
    """Create a keyboard with the specified number of layers (no explicit ids)."""
    return Keyboard(layers=[KeyboardLayer(index=i, name=f"Layer {i}") for i in range(count)])


def make_mappings(
    keycodes: dict[str, str] | None = None,
    pre_processing: dict[str, str] | None = None,
    macro_functions: dict[str, str] | None = None,
    modifier_union: dict[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    """Create a keycode mappings dict for testing."""
    return {
        "keycodes": keycodes or {},
        "pre_processing": pre_processing or {},
        "macro_functions": macro_functions or {},
        "modifier_union": modifier_union or {},
    }


def make_adapter(
    mappings: dict[str, dict[str, str]],
    keyboard: Keyboard | None = None,
) -> KeycodeLabelAdapter:
    """Helper to create an adapter with default keyboard config."""
    return KeycodeLabelAdapter(keyboard or Keyboard(), mappings)


class TestLayerFunctionsTrie:
    def test_recognizes_layer_functions(self):
        for func in ["DF", "PDF", "MO", "LM", "LT", "OSL", "TG", "TO", "TT"]:
            assert _LAYER_FUNCTIONS.get_matching_prefix(f"{func}(") == func

    def test_does_not_match_non_layer_functions(self):
        assert _LAYER_FUNCTIONS.get_matching_prefix("KC_A") is None
        assert _LAYER_FUNCTIONS.get_matching_prefix("S(KC_A)") is None


class TestLayerFunctionsHold:
    def test_contains_lt_and_lm(self):
        assert "LT" in _LAYER_FUNCTIONS_HOLD
        assert "LM" in _LAYER_FUNCTIONS_HOLD
        assert len(_LAYER_FUNCTIONS_HOLD) == 2


class TestKeycodeLabelAdapterInit:
    def test_initializes_with_loader(self):
        loader = make_mappings(
            keycodes={"KC_A": "A"},
            pre_processing={"OLD": "NEW"},
            macro_functions={"MO": "L#1;"},
            modifier_union={"MOD_LCTL": "Ctrl"},
        )
        adapter = make_adapter(loader)
        assert adapter._keycodes == {"KC_A": "A"}
        assert adapter._pre_processing == {"OLD": "NEW"}
        assert adapter._macro_functions == {"MO": "L#1;"}
        assert adapter._modifier_union == {"MOD_LCTL": "Ctrl"}
        assert adapter._label_separator == SEPARATOR_CHAR

    def test_stores_keyboard_config(self):
        loader = make_mappings()
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, id="base", name="Base"),
                KeyboardLayer(index=1, id="nav", name="Navigation"),
            ]
        )
        adapter = make_adapter(loader, keyboard)
        assert adapter._keyboard_config is keyboard


class TestKeycodeLabelAdapterTransformBasic:
    def test_basic_keycode_lookup(self):
        loader = make_mappings(keycodes={"KC_A": "A", "KC_B": "B"})
        adapter = make_adapter(loader)
        result = adapter.transform("KC_A")
        assert result.label == "A"
        assert result.layer_switch is None

    def test_unknown_keycode_returns_itself(self):
        loader = make_mappings(keycodes={})
        adapter = make_adapter(loader)
        result = adapter.transform("KC_UNKNOWN")
        assert result.label == "KC_UNKNOWN"
        assert result.layer_switch is None


class TestKeycodeLabelAdapterPreProcessing:
    def test_pre_processing_applied(self):
        loader = make_mappings(
            keycodes={"KC_NORMALIZED": "Normalized"},
            pre_processing={"KC_ALIAS": "KC_NORMALIZED"},
        )
        adapter = make_adapter(loader)
        result = adapter.transform("KC_ALIAS")
        assert result.label == "Normalized"

    def test_pre_processing_not_found_returns_original(self):
        loader = make_mappings(keycodes={"KC_A": "A"}, pre_processing={})
        adapter = make_adapter(loader)
        result = adapter.transform("KC_A")
        assert result.label == "A"


class TestKeycodeLabelAdapterMacroFunctions:
    def test_mo_layer_function(self):
        loader = make_mappings(
            keycodes={},
            macro_functions={"MO": "L#0;"},
        )
        keyboard = make_keyboard_with_layers(3)  # Need layers 0, 1, 2
        adapter = make_adapter(loader, keyboard)
        result = adapter.transform("MO(2)")
        assert result.label == "L2"
        assert result.layer_switch == 2

    def test_lt_layer_tap_function(self):
        loader = make_mappings(
            keycodes={"KC_SPC": "Space"},
            macro_functions={"LT": "@1;|;L#0;"},
        )
        keyboard = make_keyboard_with_layers(2)  # Need layers 0, 1
        adapter = make_adapter(loader, keyboard)
        result = adapter.transform("LT(1, KC_SPC)")
        assert "Space" in result.label
        assert SEPARATOR_CHAR in result.label
        assert result.layer_switch == 1

    def test_macro_function_not_in_config(self):
        loader = make_mappings(keycodes={}, macro_functions={})
        adapter = make_adapter(loader)
        result = adapter.transform("UNKNOWN_FUNC(1)")
        assert result.label == "UNKNOWN_FUNC(1)"
        assert result.layer_switch is None

    def test_non_macro_format_returns_keycode(self):
        loader = make_mappings(keycodes={"KC_A": "A"}, macro_functions={"MO": "L#0;"})
        adapter = make_adapter(loader)
        result = adapter.transform("KC_A")
        assert result.label == "A"
        assert result.layer_switch is None


class TestKeycodeLabelAdapterLayerArgument:
    def test_layer_argument_1_indexed(self):
        loader = make_mappings(macro_functions={"TG": "TG#0;"})
        keyboard = make_keyboard_with_layers(1)  # Need layer 0
        adapter = make_adapter(loader, keyboard)
        result = adapter.transform("TG(0)")
        assert "0" in result.label
        assert result.layer_switch == 0

    def test_layer_argument_non_numeric_without_keyboard_config(self):
        loader = make_mappings(macro_functions={"TG": "TG#0;"})
        adapter = make_adapter(loader)
        result = adapter.transform("TG(BASE)")
        assert "BASE" in result.label
        assert result.layer_switch is None  # No keyboard config to resolve the name

    def test_layer_argument_resolved_by_keyboard_config(self):
        """Layer names are resolved to indices using keyboard config."""
        loader = make_mappings(macro_functions={"MO": "L#0;"})
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, id="base", name="Base"),
                KeyboardLayer(index=1, id="nav", name="Navigation"),
                KeyboardLayer(index=2, id="sym", name="Symbols"),
            ]
        )
        adapter = make_adapter(loader, keyboard)
        result = adapter.transform("MO(nav)")
        assert result.layer_switch == 1

    def test_layer_argument_unknown_name_returns_none(self):
        """Unknown layer names return None."""
        loader = make_mappings(macro_functions={"MO": "L#0;"})
        keyboard = Keyboard(layers=[KeyboardLayer(index=0, id="base", name="Base")])
        adapter = make_adapter(loader, keyboard)
        result = adapter.transform("MO(unknown)")
        assert result.layer_switch is None


class TestKeycodeLabelAdapterModifierUnion:
    def test_single_modifier(self):
        loader = make_mappings(
            keycodes={},
            macro_functions={"OSM": "@0;"},
            modifier_union={"MOD_LCTL": "Ctrl"},
        )
        adapter = make_adapter(loader)
        result = adapter.transform("OSM(MOD_LCTL)")
        assert result.label == "Ctrl"

    def test_modifier_union_pipe_separated(self):
        loader = make_mappings(
            keycodes={},
            macro_functions={"OSM": "@0;"},
            modifier_union={"MOD_LCTL": "Ctrl", "MOD_LSFT": "Shift"},
        )
        adapter = make_adapter(loader)
        result = adapter.transform("OSM(MOD_LCTL|MOD_LSFT)")
        assert "Ctrl" in result.label
        assert "Shift" in result.label

    def test_unknown_modifier_returned_as_is(self):
        loader = make_mappings(
            keycodes={},
            macro_functions={"OSM": "@0;"},
            modifier_union={},
        )
        adapter = make_adapter(loader)
        result = adapter.transform("OSM(MOD_UNKNOWN)")
        assert "MOD_UNKNOWN" in result.label


class TestKeycodeLabelAdapterAliasReferences:
    def test_alias_reference_resolved(self):
        loader = make_mappings(keycodes={"KC_SPC": "@@KC_SPACE;", "KC_SPACE": "Space"})
        adapter = make_adapter(loader)
        result = adapter.transform("KC_SPC")
        assert result.label == "Space"

    def test_circular_alias_raises_error(self):
        loader = make_mappings(keycodes={"KC_A": "@@KC_B;", "KC_B": "@@KC_A;"})
        adapter = make_adapter(loader)
        with pytest.raises(ValueError) as exc_info:
            adapter.transform("KC_A")
        assert "Circular alias" in str(exc_info.value)


class TestKeycodeLabelAdapterNestedMacros:
    def test_nested_macro_in_argument(self):
        loader = make_mappings(
            keycodes={"KC_A": "A"},
            macro_functions={"LT": "@1;|;L#0;", "S": "⇧@0;"},
        )
        keyboard = make_keyboard_with_layers(2)  # Need layers 0, 1
        adapter = make_adapter(loader, keyboard)
        result = adapter.transform("LT(1, S(KC_A))")
        assert "⇧" in result.label
        assert "A" in result.label
        assert result.layer_switch == 1


class TestParseFunctionArguments:
    def test_simple_args(self):
        result = KeycodeLabelAdapter._parse_function_arguments("1, KC_A")
        assert result == ["1", "KC_A"]

    def test_nested_parentheses(self):
        result = KeycodeLabelAdapter._parse_function_arguments("1, MT(MOD_LCTL, KC_A)")
        assert result == ["1", "MT(MOD_LCTL,KC_A)"]

    def test_single_arg(self):
        result = KeycodeLabelAdapter._parse_function_arguments("2")
        assert result == ["2"]

    def test_whitespace_stripped(self):
        result = KeycodeLabelAdapter._parse_function_arguments("  1  ,  KC_A  ")
        assert result == ["1", "KC_A"]

    def test_deeply_nested(self):
        result = KeycodeLabelAdapter._parse_function_arguments("LT(1, MT(MOD_LCTL, KC_A))")
        assert result == ["LT(1,MT(MOD_LCTL,KC_A))"]


class TestResolveLayerArgument:
    def test_numeric_adds_one(self):
        assert KeycodeLabelAdapter._resolve_layer_argument(["0", "KC_A"], 0) == "0"
        assert KeycodeLabelAdapter._resolve_layer_argument(["5", "KC_A"], 0) == "5"

    def test_non_numeric_unchanged(self):
        assert KeycodeLabelAdapter._resolve_layer_argument(["BASE", "KC_A"], 0) == "BASE"

    def test_out_of_bounds_returns_empty(self):
        assert KeycodeLabelAdapter._resolve_layer_argument(["0"], 5) == ""


class TestIsModifierUnion:
    def test_mod_prefix(self):
        assert KeycodeLabelAdapter._is_modifier_union("MOD_LCTL") is True
        assert KeycodeLabelAdapter._is_modifier_union("MOD_LSFT") is True

    def test_pipe_with_mod(self):
        assert KeycodeLabelAdapter._is_modifier_union("MOD_LCTL|MOD_LSFT") is True

    def test_not_modifier(self):
        assert KeycodeLabelAdapter._is_modifier_union("KC_A") is False
        assert KeycodeLabelAdapter._is_modifier_union("1") is False


class TestResolveKeycodeArgument:
    def test_keycode_in_dict(self):
        loader = make_mappings(keycodes={"KC_A": "A"})
        adapter = make_adapter(loader)
        result = adapter._resolve_keycode_argument(["KC_A"], 0)
        assert result == "A"

    def test_modifier_union(self):
        loader = make_mappings(modifier_union={"MOD_LCTL": "Ctrl"})
        adapter = make_adapter(loader)
        result = adapter._resolve_keycode_argument(["MOD_LCTL"], 0)
        assert result == "Ctrl"

    def test_recursive_transform(self):
        loader = make_mappings(
            keycodes={"KC_A": "A"},
            macro_functions={"S": "⇧@0;"},
        )
        adapter = make_adapter(loader)
        result = adapter._resolve_keycode_argument(["S(KC_A)"], 0)
        assert "⇧" in result
        assert "A" in result

    def test_out_of_bounds_returns_empty(self):
        loader = make_mappings(keycodes={})
        adapter = make_adapter(loader)
        result = adapter._resolve_keycode_argument(["KC_A"], 5)
        assert result == ""


class TestLTWithSingleArgument:
    def test_lt_shorthand_extracts_layer_from_name(self):
        loader = make_mappings(macro_functions={"LT": "L#0;", "LT0": "L#0;"})
        keyboard = make_keyboard_with_layers(1)  # Need layer 0
        adapter = make_adapter(loader, keyboard)
        result = adapter.transform("LT0(KC_A)")
        assert result.layer_switch == 0
