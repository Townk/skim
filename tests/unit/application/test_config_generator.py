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
