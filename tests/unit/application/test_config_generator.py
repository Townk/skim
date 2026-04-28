# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.config_generator module."""

import colorsys
import json
from pathlib import Path

import pytest
import yaml

from skim.application.config_generator import ConfigGenerator


class TestGenerateDefault:
    """Tests for ConfigGenerator.generate_default()."""

    def test_returns_valid_yaml(self):
        """Output is parseable YAML."""
        generator = ConfigGenerator()
        result = generator.generate_default()
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)

    def test_contains_all_top_level_keys(self):
        """Output contains keyboard, keycodes, and output sections."""
        generator = ConfigGenerator()
        result = generator.generate_default()
        parsed = yaml.safe_load(result)
        assert "keyboard" in parsed
        assert "keycodes" in parsed
        assert "output" in parsed

    def test_default_values_match_skim_config(self):
        """Default output matches SkimConfig() defaults."""
        generator = ConfigGenerator()
        result = generator.generate_default()
        parsed = yaml.safe_load(result)
        assert parsed["output"]["layout"]["width"] == 1600
        assert parsed["output"]["style"]["palette"]["neutral_color"] == "#6F768B"
        assert parsed["keyboard"]["features"]["double_south"] is False

    def test_roundtrips_through_skim_config(self):
        """Output can be loaded back as a valid SkimConfig."""
        from skim.data.config import SkimConfig

        generator = ConfigGenerator()
        result = generator.generate_default()
        parsed = yaml.safe_load(result)
        config = SkimConfig.model_validate(parsed)
        assert config.output.layout.width == 1600


class TestGenerateFromKeybard:
    """Tests for ConfigGenerator.generate_from_keybard()."""

    @pytest.fixture()
    def minimal_keybard(self) -> str:
        """Minimal .kbi JSON with 2 layers, 1 custom keycode."""
        return json.dumps(
            {
                "layers": 2,
                "keymap": [["KC_A"] * 60, ["KC_B"] * 60],
                "layer_colors": [
                    {"hue": 85, "sat": 255, "val": 255},
                    {"hue": 0, "sat": 255, "val": 255},
                ],
                "cosmetic": {"layer": {"0": "Base", "1": "Symbols"}},
                "custom_keycodes": [
                    {"name": "MY_KEY", "shortName": "My\nKey", "title": "A custom key"}
                ],
            }
        )

    def test_returns_valid_yaml(self, minimal_keybard):
        """Output is parseable YAML."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)

    def test_extracts_layer_names(self, minimal_keybard):
        """Layers from cosmetic metadata become keyboard.layers entries."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        layers = parsed["keyboard"]["layers"]
        assert len(layers) == 2
        assert layers[0]["index"] == 0
        assert layers[0]["name"] == "Base"
        assert layers[1]["index"] == 1
        assert layers[1]["name"] == "Symbols"

    def test_extracts_layer_colors(self, minimal_keybard):
        """Layer colors are converted from HSV to hex."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        palette_layers = parsed["output"]["style"]["palette"]["layers"]
        assert len(palette_layers) == 2
        for layer in palette_layers:
            assert layer["base_color"].startswith("#")

    def test_layer_color_hsv_conversion(self, minimal_keybard):
        """HSV {hue:85, sat:255, val:255} converts to correct hex."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        r, g, b = colorsys.hsv_to_rgb(85 / 255, 1.0, 1.0)
        expected = f"#{int(round(r * 255)):02X}{int(round(g * 255)):02X}{int(round(b * 255)):02X}"
        assert parsed["output"]["style"]["palette"]["layers"][0]["base_color"] == expected

    def test_extracts_custom_keycodes(self, minimal_keybard):
        """Custom keycodes become keycodes.overrides entries."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        overrides = parsed["keycodes"]["overrides"]
        names = [o["keycode"] for o in overrides]
        assert "MY_KEY" in names

    def test_custom_keycode_newlines_replaced_with_space(self, minimal_keybard):
        """Newlines in shortName are replaced with spaces."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        overrides = {o["keycode"]: o["target"] for o in parsed["keycodes"]["overrides"]}
        assert overrides["MY_KEY"] == "My Key"

    def test_user_alias_for_custom_keycode(self, minimal_keybard):
        """USER00 alias points to custom keycode via @@ reference."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        overrides = {o["keycode"]: o["target"] for o in parsed["keycodes"]["overrides"]}
        assert overrides["USER00"] == "@@MY_KEY;"

    def test_empty_layers_drop_from_config_preserving_qmk_indices(self):
        """Empty layers are dropped, but the remaining layers keep their slot.

        The original kbi sample has 16 declared layers but layers 4, 6, and 7
        are empty (all KC_NO/KC_TRNS). Without this filtering the loader's
        ``zip(indices, non_empty)`` silently shifted every layer past slot 4
        — so a key with ``MO(14)`` ended up resolving to whatever happened
        to land in skim's slot 14 after repacking, not the user's "Sys"
        layer (kbi[14]). Layers must keep their original kbi index.
        """
        keybard = json.dumps(
            {
                "layers": 8,
                "keymap": [
                    ["KC_A"] * 60,  # 0 — active
                    ["KC_B"] * 60,  # 1 — active
                    ["KC_NO"] * 60,  # 2 — empty
                    ["KC_C"] * 60,  # 3 — active
                    ["KC_TRNS"] * 60,  # 4 — empty
                    ["KC_NO"] * 60,  # 5 — empty
                    ["KC_D"] * 60,  # 6 — active
                    ["KC_E"] * 60,  # 7 — active
                ],
                "layer_colors": [{"hue": h, "sat": 255, "val": 255} for h in range(0, 8 * 32, 32)],
                "cosmetic": {"layer": {}},
                "custom_keycodes": [],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(keybard)
        parsed = yaml.safe_load(result)
        layer_indices = [layer["index"] for layer in parsed["keyboard"]["layers"]]
        assert layer_indices == [0, 1, 3, 6, 7]
        # Palette mirrors the active layers in order — entry i corresponds
        # to ``parsed["keyboard"]["layers"][i]``, not to QMK index i.
        assert len(parsed["output"]["style"]["palette"]["layers"]) == 5

    def test_layers_without_cosmetic_names_get_defaults(self):
        """Layers missing from cosmetic.layer get 'Layer N' names."""
        keybard = json.dumps(
            {
                "layers": 2,
                "keymap": [["KC_A"] * 60, ["KC_B"] * 60],
                "layer_colors": [
                    {"hue": 0, "sat": 0, "val": 128},
                    {"hue": 0, "sat": 0, "val": 128},
                ],
                "cosmetic": {"layer": {}},
                "custom_keycodes": [],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(keybard)
        parsed = yaml.safe_load(result)
        layers = parsed["keyboard"]["layers"]
        assert layers[0]["index"] == 0
        assert layers[0]["name"] == "Layer 0"
        assert layers[1]["index"] == 1
        assert layers[1]["name"] == "Layer 1"

    def test_color_adjustment_lightness(self, minimal_keybard):
        """adjust_lightness parameter modifies extracted colors."""
        generator = ConfigGenerator()
        unadjusted = yaml.safe_load(generator.generate_from_keybard(minimal_keybard))
        adjusted = yaml.safe_load(
            generator.generate_from_keybard(minimal_keybard, adjust_lightness=0.31)
        )
        c1 = unadjusted["output"]["style"]["palette"]["layers"][0]["base_color"]
        c2 = adjusted["output"]["style"]["palette"]["layers"][0]["base_color"]
        assert c1 != c2

    def test_roundtrips_through_skim_config(self, minimal_keybard):
        """Generated config validates as a SkimConfig."""
        from skim.data.config import SkimConfig

        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        config = SkimConfig.model_validate(parsed)
        assert len(config.keyboard.layers) == 2

    def test_invalid_json_raises_value_error(self):
        """Non-JSON input raises ValueError."""
        generator = ConfigGenerator()
        with pytest.raises(ValueError, match="Invalid JSON"):
            generator.generate_from_keybard("not json {{{")

    def test_empty_custom_keycodes(self):
        """No custom keycodes produces empty overrides."""
        keybard = json.dumps(
            {
                "layers": 1,
                "keymap": [["KC_A"] * 60],
                "layer_colors": [{"hue": 0, "sat": 0, "val": 128}],
                "cosmetic": {"layer": {"0": "Base"}},
                "custom_keycodes": [],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(keybard)
        parsed = yaml.safe_load(result)
        assert parsed["keycodes"]["overrides"] == []


class TestMacroPreview:
    """Tests for macro_preview helper."""

    @pytest.fixture()
    def adapter(self):
        from skim.application.loaders.keycode_mappings_loader import (
            load_keycode_mappings,
        )
        from skim.data import SkimConfig
        from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter

        config = SkimConfig()
        mappings = load_keycode_mappings(config.keycodes)
        return KeycodeLabelAdapter(config.keyboard, mappings)

    def test_single_tap_action(self, adapter):
        from skim.application.config_generator import macro_preview
        from skim.domain.domain_types import (
            SvalboardMacro,
            SvalboardMacroAction,
            SvalboardMacroActionKind,
        )

        macro = SvalboardMacro[str](
            id="0",
            actions=(SvalboardMacroAction[str](kind=SvalboardMacroActionKind.TAP, keys=("KC_Q",)),),
        )
        assert macro_preview(macro, adapter) == "[↓↑ Q]"

    def test_multi_keycode_up_action_joins_with_comma(self, adapter):
        from skim.application.config_generator import macro_preview
        from skim.domain.domain_types import (
            SvalboardMacro,
            SvalboardMacroAction,
            SvalboardMacroActionKind,
        )

        macro = SvalboardMacro[str](
            id="0",
            actions=(
                SvalboardMacroAction[str](kind=SvalboardMacroActionKind.UP, keys=("KC_E", "KC_1")),
            ),
        )
        assert macro_preview(macro, adapter) == "[↑ E,1]"

    def test_text_action_uses_nf_marker(self, adapter):
        from skim.application.config_generator import macro_preview
        from skim.domain.domain_types import (
            SvalboardMacro,
            SvalboardMacroAction,
            SvalboardMacroActionKind,
        )

        macro = SvalboardMacro[str](
            id="0",
            actions=(SvalboardMacroAction[str](kind=SvalboardMacroActionKind.TEXT, text=";qj"),),
        )
        assert macro_preview(macro, adapter) == '[%%nf-md-text_recognition; ";qj"]'

    def test_delay_action_uses_nf_marker(self, adapter):
        from skim.application.config_generator import macro_preview
        from skim.domain.domain_types import (
            SvalboardMacro,
            SvalboardMacroAction,
            SvalboardMacroActionKind,
        )

        macro = SvalboardMacro[str](
            id="0",
            actions=(
                SvalboardMacroAction[str](kind=SvalboardMacroActionKind.DELAY, duration_ms=30),
            ),
        )
        assert macro_preview(macro, adapter) == "[%%nf-fa-hourglass_2; 30]"

    def test_mixed_sequence_pipe_separated(self, adapter):
        from skim.application.config_generator import macro_preview
        from skim.domain.domain_types import (
            SvalboardMacro,
            SvalboardMacroAction,
            SvalboardMacroActionKind,
        )

        macro = SvalboardMacro[str](
            id="0",
            actions=(
                SvalboardMacroAction[str](kind=SvalboardMacroActionKind.DOWN, keys=("KC_E",)),
                SvalboardMacroAction[str](kind=SvalboardMacroActionKind.DELAY, duration_ms=30),
                SvalboardMacroAction[str](kind=SvalboardMacroActionKind.UP, keys=("KC_E", "KC_1")),
            ),
        )
        assert macro_preview(macro, adapter) == "[↓ E | %%nf-fa-hourglass_2; 30 | ↑ E,1]"


class TestQmkColorParsing:
    """Tests for QMK color.h header parsing via generate_from_keybard."""

    @pytest.fixture()
    def minimal_keybard(self) -> str:
        return json.dumps(
            {
                "layers": 1,
                "keymap": [["KC_A"] * 60],
                "layer_colors": [{"hue": 0, "sat": 0, "val": 128}],
                "cosmetic": {"layer": {"0": "Base"}},
                "custom_keycodes": [],
            }
        )

    def test_hsv_define_parsed(self, minimal_keybard):
        """HSV_* defines are converted to palette overrides."""
        header = "#define HSV_MYBLUE 170, 255, 255"
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard, qmk_header_content=header)
        parsed = yaml.safe_load(result)
        overrides = parsed["output"]["style"]["palette"]["overrides"]
        assert "myblue" in overrides
        assert overrides["myblue"].startswith("#")

    def test_rgb_define_parsed(self, minimal_keybard):
        """RGB_* defines are converted to palette overrides."""
        header = "#define RGB_MYRED 255, 0, 0"
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard, qmk_header_content=header)
        parsed = yaml.safe_load(result)
        overrides = parsed["output"]["style"]["palette"]["overrides"]
        assert "myred" in overrides
        assert overrides["myred"] == "#FF0000"

    def test_non_define_lines_ignored(self, minimal_keybard):
        """Non-#define lines are silently skipped."""
        header = "// comment\n#include <stdint.h>\n#define HSV_FOO 0, 255, 128"
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard, qmk_header_content=header)
        parsed = yaml.safe_load(result)
        overrides = parsed["output"]["style"]["palette"]["overrides"]
        assert len(overrides) == 1
        assert "foo" in overrides

    def test_color_adjustment_applied_to_qmk_colors(self, minimal_keybard):
        """Color adjustments are applied to QMK-parsed colors."""
        header = "#define HSV_BRIGHT 0, 255, 255"
        generator = ConfigGenerator()
        unadjusted = yaml.safe_load(
            generator.generate_from_keybard(minimal_keybard, qmk_header_content=header)
        )
        adjusted = yaml.safe_load(
            generator.generate_from_keybard(
                minimal_keybard,
                qmk_header_content=header,
                adjust_lightness=0.2,
            )
        )
        assert (
            unadjusted["output"]["style"]["palette"]["overrides"]["bright"]
            != adjusted["output"]["style"]["palette"]["overrides"]["bright"]
        )

    def test_no_qmk_header_produces_empty_overrides(self, minimal_keybard):
        """Without qmk_header_content, palette overrides is empty."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        assert parsed["output"]["style"]["palette"]["overrides"] == {}


class TestFindNonStandardKeycodes:
    """Tests for ConfigGenerator._find_non_standard_keycodes()."""

    @pytest.fixture()
    def standard_keycodes(self) -> set[str]:
        """A minimal set of standard keycodes and macro functions for testing."""
        return {
            # keycodes
            "KC_A",
            "KC_B",
            "KC_NO",
            "KC_TRNS",
            "KC_SPACE",
            "KC_ENTER",
            "KC_LEFT_CTRL",
            "KC_LEFT_SHIFT",
            "KC_LEFT_ALT",
            "KC_LEFT_GUI",
            # macro_functions
            "MO",
            "LT",
            "TG",
            "OSL",
            "MT",
            "TO",
            "DF",
            "LSFT",
            "LCTL",
            "LALT",
            "LGUI",
        }

    def test_all_standard_returns_empty(self, standard_keycodes):
        """All-standard keycodes produce no overrides."""
        layers = [["KC_A", "KC_B", "KC_NO"]]
        result = ConfigGenerator._find_non_standard_keycodes(layers, standard_keycodes)
        assert result == []

    def test_bare_custom_keycode_found(self, standard_keycodes):
        """A bare non-standard keycode is detected."""
        layers = [["KC_A", "MY_CUSTOM", "KC_B"]]
        result = ConfigGenerator._find_non_standard_keycodes(layers, standard_keycodes)
        assert len(result) == 1
        assert result[0] == {"keycode": "MY_CUSTOM", "target": "MY_CUSTOM"}

    def test_function_calls_skipped(self, standard_keycodes):
        """Keycodes that are function calls (with parens) are skipped."""
        layers = [["LT(2, MY_KEY)", "MO(_BASE)", "LSFT(KC_A)"]]
        result = ConfigGenerator._find_non_standard_keycodes(layers, standard_keycodes)
        assert result == []

    def test_custom_function_call_skipped(self, standard_keycodes):
        """Even unknown function calls are skipped."""
        layers = [["MY_FUNC(KC_A)", "KC_B"]]
        result = ConfigGenerator._find_non_standard_keycodes(layers, standard_keycodes)
        assert result == []

    def test_deduplicates_across_layers(self, standard_keycodes):
        """Same non-standard keycode in multiple layers appears once."""
        layers = [["MY_KEY", "KC_A"], ["KC_B", "MY_KEY"]]
        result = ConfigGenerator._find_non_standard_keycodes(layers, standard_keycodes)
        assert len(result) == 1

    def test_empty_layers_returns_empty(self, standard_keycodes):
        """Empty layer list produces no overrides."""
        result = ConfigGenerator._find_non_standard_keycodes([], standard_keycodes)
        assert result == []

    def test_standard_macro_function_not_flagged(self, standard_keycodes):
        """Standard macro function names are not flagged as non-standard."""
        layers = [["LSFT(KC_A)", "LCTL(KC_B)"]]
        result = ConfigGenerator._find_non_standard_keycodes(layers, standard_keycodes)
        assert result == []


class TestGenerateFromKeymap:
    """Tests for ConfigGenerator.generate_from_keymap()."""

    def test_c2json_creates_correct_layer_count(self):
        """c2json with 3 layers creates 3 keyboard layers."""
        content = json.dumps(
            {
                "keyboard": "test",
                "keymap": "test",
                "layout": "LAYOUT",
                "layers": [
                    ["KC_A"] * 60,
                    ["KC_B"] * 60,
                    ["KC_NO"] * 60,
                ],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        # Layer 2 is all KC_NO, so it's skipped
        assert len(parsed["keyboard"]["layers"]) == 2
        assert parsed["keyboard"]["layers"][0]["index"] == 0
        assert parsed["keyboard"]["layers"][0]["name"] == "Layer 0"

    def test_c2json_creates_matching_palette_layers(self):
        """Palette layers count matches keyboard layers."""
        content = json.dumps(
            {
                "keyboard": "test",
                "keymap": "test",
                "layout": "LAYOUT",
                "layers": [["KC_A"] * 60, ["KC_B"] * 60],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        palette_layers = parsed["output"]["style"]["palette"]["layers"]
        assert len(palette_layers) == 2
        for layer in palette_layers:
            assert layer["base_color"].startswith("#")
            assert layer["color_index"] == 2
            assert layer["gradient"] is None

    def test_c2json_detects_non_standard_keycodes(self):
        """Non-standard keycodes in c2json are added as overrides."""
        content = json.dumps(
            {
                "keyboard": "test",
                "keymap": "test",
                "layout": "LAYOUT",
                "layers": [
                    ["KC_A", "MY_CUSTOM"] + ["KC_NO"] * 58,
                ],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        overrides = parsed["keycodes"]["overrides"]
        keycode_names = [o["keycode"] for o in overrides]
        assert "MY_CUSTOM" in keycode_names

    def test_c2json_no_overrides_when_all_standard(self):
        """All-standard keycodes produce empty overrides."""
        content = json.dumps(
            {
                "keyboard": "test",
                "keymap": "test",
                "layout": "LAYOUT",
                "layers": [["KC_A", "KC_B"] + ["KC_NO"] * 58],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        assert parsed["keycodes"]["overrides"] == []

    def test_vial_creates_correct_layer_count(self):
        """Vial with 2 layers creates 2 keyboard layers."""
        content = json.dumps(
            {
                "version": 1,
                "uid": 12345,
                "layout": [
                    [["KC_A"] * 6] * 10,
                    [["KC_B"] * 6] * 10,
                ],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        assert len(parsed["keyboard"]["layers"]) == 2

    def test_vial_detects_non_standard_keycodes(self):
        """Non-standard keycodes in Vial are added as overrides."""
        content = json.dumps(
            {
                "version": 1,
                "uid": 12345,
                "layout": [
                    [["KC_A", "MY_VIL_KEY"] + ["KC_NO"] * 4] + [["KC_NO"] * 6] * 9,
                ],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        overrides = parsed["keycodes"]["overrides"]
        keycode_names = [o["keycode"] for o in overrides]
        assert "MY_VIL_KEY" in keycode_names

    def test_vial_handles_unassigned_int_sentinel(self):
        """Vial encodes unassigned positions as int -1; do not crash."""
        content = json.dumps(
            {
                "version": 1,
                "uid": 12345,
                "layout": [
                    [["KC_A", "KC_B", "KC_C", "KC_D", "KC_E", -1]] + [["KC_NO"] * 6] * 9,
                ],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        # The -1 sentinel must not appear as a custom keycode override
        keycode_names = [o["keycode"] for o in parsed["keycodes"]["overrides"]]
        assert "-1" not in keycode_names
        assert -1 not in keycode_names

    def test_keybard_delegates_to_generate_from_keybard(self):
        """Keybard format delegates to generate_from_keybard."""
        content = json.dumps(
            {
                "layers": 1,
                "keymap": [["KC_A"] * 60],
                "layer_colors": [{"hue": 85, "sat": 255, "val": 255}],
                "cosmetic": {"layer": {"0": "Base"}},
                "custom_keycodes": [],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        # Should use Keybard path which extracts cosmetic names
        assert parsed["keyboard"]["layers"][0]["name"] == "Base"

    def test_roundtrips_through_skim_config(self):
        """Generated config validates as a SkimConfig."""
        from skim.data.config import SkimConfig

        content = json.dumps(
            {
                "keyboard": "test",
                "keymap": "test",
                "layout": "LAYOUT",
                "layers": [["KC_A"] * 60],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        config = SkimConfig.model_validate(parsed)
        assert len(config.keyboard.layers) == 1

    def test_invalid_json_raises_value_error(self):
        """Non-JSON input raises ValueError."""
        generator = ConfigGenerator()
        with pytest.raises(ValueError, match="Invalid JSON"):
            generator.generate_from_keymap("not json {{{")

    def test_unknown_format_raises_value_error(self):
        """Unrecognized JSON structure raises ValueError."""
        content = json.dumps({"something": "else"})
        generator = ConfigGenerator()
        with pytest.raises(ValueError, match="Unknown keymap format"):
            generator.generate_from_keymap(content)

    def test_empty_layers_skipped(self):
        """Layers with all KC_NO keys are not created."""
        content = json.dumps(
            {
                "keyboard": "test",
                "keymap": "test",
                "layout": "LAYOUT",
                "layers": [
                    ["KC_A"] * 60,
                    ["KC_NO"] * 60,
                    ["KC_B"] * 60,
                ],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        layers = parsed["keyboard"]["layers"]
        assert len(layers) == 2
        assert layers[0]["index"] == 0
        assert layers[1]["index"] == 2

    def test_empty_layers_with_trns_skipped(self):
        """Layers with mix of KC_NO and KC_TRNS are skipped."""
        content = json.dumps(
            {
                "keyboard": "test",
                "keymap": "test",
                "layout": "LAYOUT",
                "layers": [
                    ["KC_A"] * 60,
                    ["KC_NO"] * 30 + ["KC_TRNS"] * 30,
                    ["KC_B"] * 60,
                    ["KC_TRNS"] * 60,
                ],
            }
        )
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(content)
        parsed = yaml.safe_load(result)
        layers = parsed["keyboard"]["layers"]
        assert len(layers) == 2
        assert layers[0]["index"] == 0
        assert layers[1]["index"] == 2
        palette_layers = parsed["output"]["style"]["palette"]["layers"]
        assert len(palette_layers) == 2


class TestWithSampleKeybard:
    """Integration tests using the real keybard sample file."""

    @pytest.fixture()
    def sample_keybard(self) -> str:
        sample_path = (
            Path(__file__).parent.parent.parent.parent
            / "samples"
            / "keymaps"
            / "keybard-sample.kbi"
        )
        if not sample_path.exists():
            pytest.skip("Sample keybard file not found")
        return sample_path.read_text()

    def test_sample_produces_valid_config(self, sample_keybard):
        """Real sample file produces a valid SkimConfig.

        The sample defines 16 slots, but layers 4, 6, and 7 are empty
        (all KC_NO/KC_TRNS). The generator drops them so the resulting
        config carries the 13 active QMK indices — keeping each layer at
        its original slot so that ``MO(N)``/``TO(N)``/``DF(N)`` keycodes
        resolve to the rendered layer ``N`` rather than to whichever
        layer happened to land in slot ``N`` after sequential repacking.
        """
        from skim.data.config import SkimConfig

        generator = ConfigGenerator()
        result = generator.generate_from_keybard(sample_keybard)
        parsed = yaml.safe_load(result)
        config = SkimConfig.model_validate(parsed)
        layer_indices = [layer.index for layer in config.keyboard.layers]
        assert layer_indices == [0, 1, 2, 3, 5, 8, 9, 10, 11, 12, 13, 14, 15]

    def test_sample_extracts_known_layer_names(self, sample_keybard):
        """Known layer names from sample file are extracted."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(sample_keybard)
        parsed = yaml.safe_load(result)
        layer_names = [layer["name"] for layer in parsed["keyboard"]["layers"]]
        assert "Base" in layer_names
        assert "Sym" in layer_names
        assert "Nav" in layer_names

    def test_sample_extracts_custom_keycodes(self, sample_keybard):
        """Custom keycodes from sample are present in overrides."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(sample_keybard)
        parsed = yaml.safe_load(result)
        keycode_names = [o["keycode"] for o in parsed["keycodes"]["overrides"]]
        assert "SV_LEFT_DPI_INC" in keycode_names

    def test_sample_with_color_adjustments(self, sample_keybard):
        """Color adjustments apply without errors on real data."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(
            sample_keybard, adjust_lightness=0.31, adjust_saturation=0.50
        )
        parsed = yaml.safe_load(result)
        from skim.data.config import SkimConfig

        config = SkimConfig.model_validate(parsed)
        # Palette mirrors the active layers — empty slots (4, 6, 7) are
        # dropped from both ``keyboard.layers`` and ``palette.layers``.
        assert len(config.output.style.palette.layers) == 13


class TestWithSampleVial:
    """Integration tests using the real Vial sample file."""

    @pytest.fixture()
    def sample_vial(self) -> str:
        sample_path = (
            Path(__file__).parent.parent.parent.parent / "samples" / "keymaps" / "vial-sample.vil"
        )
        if not sample_path.exists():
            pytest.skip("Sample Vial file not found")
        return sample_path.read_text()

    def test_sample_produces_valid_config(self, sample_vial):
        """Real Vial sample file produces a valid SkimConfig."""
        from skim.data.config import SkimConfig

        generator = ConfigGenerator()
        result = generator.generate_from_keymap(sample_vial)
        parsed = yaml.safe_load(result)
        config = SkimConfig.model_validate(parsed)
        # Layers with all KC_NO/KC_TRNS keys are skipped
        assert len(config.keyboard.layers) == 11

    def test_sample_palette_matches_layer_count(self, sample_vial):
        """Palette layer count matches keyboard layer count."""
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(sample_vial)
        parsed = yaml.safe_load(result)
        assert len(parsed["output"]["style"]["palette"]["layers"]) == len(
            parsed["keyboard"]["layers"]
        )


class TestWithSampleC2json:
    """Integration tests using the real c2json sample file."""

    @pytest.fixture()
    def sample_c2json(self) -> str:
        sample_path = (
            Path(__file__).parent.parent.parent.parent
            / "samples"
            / "keymaps"
            / "c2json-sample.json"
        )
        if not sample_path.exists():
            pytest.skip("Sample c2json file not found")
        return sample_path.read_text()

    def test_sample_produces_valid_config(self, sample_c2json):
        """Real c2json sample file produces a valid SkimConfig."""
        from skim.data.config import SkimConfig

        generator = ConfigGenerator()
        result = generator.generate_from_keymap(sample_c2json)
        parsed = yaml.safe_load(result)
        config = SkimConfig.model_validate(parsed)
        assert len(config.keyboard.layers) == 11

    def test_sample_detects_custom_keycodes(self, sample_c2json):
        """Real c2json sample has non-standard keycodes detected."""
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(sample_c2json)
        parsed = yaml.safe_load(result)
        overrides = parsed["keycodes"]["overrides"]
        keycode_names = {o["keycode"] for o in overrides}
        # These are known non-standard keycodes in the c2json sample
        assert "CKC_SPC" in keycode_names
        assert "MKC_DKTP" in keycode_names

    def test_sample_palette_matches_layer_count(self, sample_c2json):
        """Palette layer count matches keyboard layer count."""
        generator = ConfigGenerator()
        result = generator.generate_from_keymap(sample_c2json)
        parsed = yaml.safe_load(result)
        assert len(parsed["output"]["style"]["palette"]["layers"]) == len(
            parsed["keyboard"]["layers"]
        )
