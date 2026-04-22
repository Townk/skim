# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.config_generator module."""

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
        assert parsed["output"]["layout"]["width"] == 800
        assert parsed["output"]["style"]["palette"]["neutral_color"] == "#6F768B"
        assert parsed["keyboard"]["features"]["double_south"] is False

    def test_roundtrips_through_skim_config(self):
        """Output can be loaded back as a valid SkimConfig."""
        from skim.data.config import SkimConfig

        generator = ConfigGenerator()
        result = generator.generate_default()
        parsed = yaml.safe_load(result)
        config = SkimConfig.model_validate(parsed)
        assert config.output.layout.width == 800


import colorsys
import json

import pytest


class TestGenerateFromKeybard:
    """Tests for ConfigGenerator.generate_from_keybard()."""

    @pytest.fixture()
    def minimal_keybard(self) -> str:
        """Minimal .kbi JSON with 2 layers, 1 custom keycode."""
        return json.dumps({
            "layers": 2,
            "keymap": [["KC_A"] * 60, ["KC_B"] * 60],
            "layer_colors": [
                {"hue": 85, "sat": 255, "val": 255},
                {"hue": 0, "sat": 255, "val": 255},
            ],
            "cosmetic": {
                "layer": {"0": "Base", "1": "Symbols"}
            },
            "custom_keycodes": [
                {"name": "MY_KEY", "shortName": "My\nKey", "title": "A custom key"}
            ],
        })

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
        assert layers[0]["label"] == "BASE"
        assert layers[1]["index"] == 1
        assert layers[1]["name"] == "Symbols"
        assert layers[1]["label"] == "SYMB"

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
        expected = f"#{int(round(r*255)):02X}{int(round(g*255)):02X}{int(round(b*255)):02X}"
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

    def test_layers_without_cosmetic_names_get_defaults(self):
        """Layers missing from cosmetic.layer get 'Layer N' names."""
        keybard = json.dumps({
            "layers": 2,
            "keymap": [["KC_A"] * 60, ["KC_B"] * 60],
            "layer_colors": [
                {"hue": 0, "sat": 0, "val": 128},
                {"hue": 0, "sat": 0, "val": 128},
            ],
            "cosmetic": {"layer": {}},
            "custom_keycodes": [],
        })
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(keybard)
        parsed = yaml.safe_load(result)
        layers = parsed["keyboard"]["layers"]
        assert layers[0]["index"] == 0
        assert layers[0]["name"] == "Layer 0"
        assert layers[0]["label"] == "L0"
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
        keybard = json.dumps({
            "layers": 1,
            "keymap": [["KC_A"] * 60],
            "layer_colors": [{"hue": 0, "sat": 0, "val": 128}],
            "cosmetic": {"layer": {"0": "Base"}},
            "custom_keycodes": [],
        })
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(keybard)
        parsed = yaml.safe_load(result)
        assert parsed["keycodes"]["overrides"] == []


class TestQmkColorParsing:
    """Tests for QMK color.h header parsing via generate_from_keybard."""

    @pytest.fixture()
    def minimal_keybard(self) -> str:
        return json.dumps({
            "layers": 1,
            "keymap": [["KC_A"] * 60],
            "layer_colors": [{"hue": 0, "sat": 0, "val": 128}],
            "cosmetic": {"layer": {"0": "Base"}},
            "custom_keycodes": [],
        })

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
        assert unadjusted["output"]["style"]["palette"]["overrides"]["bright"] != \
               adjusted["output"]["style"]["palette"]["overrides"]["bright"]

    def test_no_qmk_header_produces_empty_overrides(self, minimal_keybard):
        """Without qmk_header_content, palette overrides is empty."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(minimal_keybard)
        parsed = yaml.safe_load(result)
        assert parsed["output"]["style"]["palette"]["overrides"] == {}


from pathlib import Path


class TestWithSampleKeybard:
    """Integration tests using the real keybard sample file."""

    @pytest.fixture()
    def sample_keybard(self) -> str:
        sample_path = Path(__file__).parent.parent.parent.parent / "samples" / "keymaps" / "keybard-sample.kbi"
        if not sample_path.exists():
            pytest.skip("Sample keybard file not found")
        return sample_path.read_text()

    def test_sample_produces_valid_config(self, sample_keybard):
        """Real sample file produces a valid SkimConfig."""
        from skim.data.config import SkimConfig

        generator = ConfigGenerator()
        result = generator.generate_from_keybard(sample_keybard)
        parsed = yaml.safe_load(result)
        config = SkimConfig.model_validate(parsed)
        assert len(config.keyboard.layers) == 16

    def test_sample_extracts_known_layer_names(self, sample_keybard):
        """Known layer names from sample file are extracted."""
        generator = ConfigGenerator()
        result = generator.generate_from_keybard(sample_keybard)
        parsed = yaml.safe_load(result)
        layer_names = [l["name"] for l in parsed["keyboard"]["layers"]]
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
        assert len(config.output.style.palette.layers) == 16
