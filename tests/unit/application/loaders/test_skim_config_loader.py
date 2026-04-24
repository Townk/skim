# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.loaders.skim_config_loader module.

Tests cover configuration loading from YAML files and default config generation.
"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from skim.application.loaders.skim_config_loader import load_skim_config
from skim.data.config import SkimConfig


class TestLoadSkimConfigDefault:
    """Tests for loading default configuration."""

    def test_none_path_returns_default(self):
        """None path returns default configuration."""
        config = load_skim_config(None)
        assert isinstance(config, SkimConfig)

    def test_empty_path_returns_default(self):
        """Empty string path returns default configuration."""
        config = load_skim_config(Path(""))
        assert isinstance(config, SkimConfig)

    def test_nonexistent_file_returns_default(self, tmp_path):
        """Non-existent file returns default configuration."""
        path = tmp_path / "nonexistent.yaml"
        config = load_skim_config(path)
        assert isinstance(config, SkimConfig)

    def test_default_config_has_expected_values(self):
        """Default config has expected default values."""
        config = load_skim_config(None)
        assert config.output.layout.width == 800
        assert config.keyboard.features.double_south is False
        assert config.output.style.use_layer_colors_on_keys is True


class TestLoadSkimConfigFromFile:
    """Tests for loading configuration from YAML files."""

    def test_load_minimal_config(self, tmp_path):
        """Load a minimal configuration file."""
        config_data = {}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        config = load_skim_config(path)
        assert isinstance(config, SkimConfig)

    def test_load_with_output_settings(self, tmp_path):
        """Load configuration with output settings."""
        config_data = {"output": {"layout": {"width": 1200}}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        config = load_skim_config(path)
        assert config.output.layout.width == 1200

    def test_load_with_keyboard_settings(self, tmp_path):
        """Load configuration with keyboard settings."""
        config_data = {
            "keyboard": {
                "features": {"double_south": True},
                "layers": [{"index": 0, "name": "Base Layer"}],
            }
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        config = load_skim_config(path)
        assert config.keyboard.features.double_south is True
        assert len(config.keyboard.layers) == 1
        assert config.keyboard.layers[0].name == "Base Layer"

    def test_load_with_keycode_overrides(self, tmp_path):
        """Load configuration with keycode overrides."""
        config_data = {"keycodes": {"overrides": [{"keycode": "KC_SPC", "target": "Space"}]}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        config = load_skim_config(path)
        assert len(config.keycodes.overrides) == 1
        assert config.keycodes.overrides[0].keycode == "KC_SPC"
        assert config.keycodes.overrides[0].target == "Space"

    def test_load_with_style_settings(self, tmp_path):
        """Load configuration with style settings."""
        config_data = {
            "output": {
                "style": {
                    "use_layer_colors_on_keys": False,
                    "hold_symbol_position": "inward",
                    "palette": {"background_color": "#F0F0F0"},
                }
            }
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        config = load_skim_config(path)
        assert config.output.style.use_layer_colors_on_keys is False
        assert config.output.style.palette.background_color == "#F0F0F0"

    def test_load_with_layer_colors(self, tmp_path):
        """Load configuration with layer colors."""
        config_data = {
            "output": {
                "style": {
                    "palette": {
                        "layers": [
                            {"base_color": "#FF0000"},
                            {"base_color": "#00FF00", "color_index": 3},
                        ]
                    }
                }
            }
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        config = load_skim_config(path)
        assert len(config.output.style.palette.layers) == 2
        assert config.output.style.palette.layers[0].base_color == "#FF0000"
        assert config.output.style.palette.layers[1].color_index == 3

    def test_load_with_border_settings(self, tmp_path):
        """Load configuration with border settings."""
        config_data = {"output": {"style": {"border": {"width": 5, "radius": 15}}}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        config = load_skim_config(path)
        assert config.output.style.border.width == 5
        assert config.output.style.border.radius == 15

    def test_load_with_null_border(self, tmp_path):
        """Load configuration with border set to null."""
        config_data = {"output": {"style": {"border": None}}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        config = load_skim_config(path)
        assert config.output.style.border is None


class TestLoadSkimConfigErrors:
    """Tests for configuration loading error handling."""

    def test_invalid_yaml_raises(self, tmp_path):
        """Invalid YAML raises yaml.YAMLError."""
        path = tmp_path / "config.yaml"
        path.write_text("invalid: yaml: content: [")

        with pytest.raises(yaml.YAMLError):
            load_skim_config(path)

    def test_invalid_schema_raises(self, tmp_path):
        """Invalid schema raises pydantic.ValidationError."""
        config_data = {"output": {"layout": {"width": "not a number"}}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        with pytest.raises(ValidationError):
            load_skim_config(path)

    def test_extra_fields_raises_in_strict_mode(self, tmp_path):
        """Extra fields raise ValidationError in strict mode."""
        config_data = {"unknown_field": "value"}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        with pytest.raises(ValidationError):
            load_skim_config(path)

    def test_nested_extra_fields_raises(self, tmp_path):
        """Nested extra fields raise ValidationError."""
        config_data = {"output": {"unknown_nested": "value"}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        with pytest.raises(ValidationError):
            load_skim_config(path)

    def test_wrong_type_for_list_field(self, tmp_path):
        """Wrong type for list field raises ValidationError."""
        config_data = {"keyboard": {"layers": "not a list"}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        with pytest.raises(ValidationError):
            load_skim_config(path)


class TestLoadSkimConfigPathTypes:
    """Tests for different path type handling."""

    def test_path_object(self, tmp_path):
        """Works with Path object."""
        config_data = {"output": {"layout": {"width": 1000}}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config_data))

        config = load_skim_config(path)
        assert config.output.layout.width == 1000

    def test_directory_path_returns_default(self, tmp_path):
        """Directory path (not file) returns default."""
        # tmp_path is a directory
        config = load_skim_config(tmp_path)
        assert isinstance(config, SkimConfig)
        assert config.output.layout.width == 800  # Default value
