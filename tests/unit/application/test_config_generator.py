"""Unit tests for ConfigGenerator."""

import yaml

from skim.application.config_generator import ConfigGenerator


class TestConfigGenerator:
    """Test configuration generation logic."""

    def test_generate_from_keybard(self):
        """Generate config from mocked Keybard content."""
        generator = ConfigGenerator()

        content = """
        {
            "layer_colors": [
                {"hue": 0, "sat": 255, "val": 255}
            ],
            "custom_keycodes": [
                {"name": "KC_CUSTOM", "shortName": "CST"}
            ],
            "cosmetic": {
                "layer": {
                    "0": "Red Layer"
                }
            }
        }
        """

        result = generator.generate(content)

        # Check essential parts of YAML
        assert "layers:" in result
        # Check color conversion (Hue 0 -> Red #FF0000)
        # Note: yaml dump quotes might vary, check content
        assert "#ff0000" in result.lower()
        assert "name: Red Layer" in result
        # Label heuristic: "Red Layer".upper()[:4] -> "RED "
        assert "label: RED" in result

        assert "keycodes:" in result
        assert "KC_CUSTOM: CST" in result

    def test_generate_with_qmk_colors(self):
        """Generate config with QMK colors."""
        generator = ConfigGenerator()
        kb_content = '{"layer_colors": []}'
        qmk_content = "#define HSV_RED 0, 255, 255"

        result = generator.generate(kb_content, qmk_content)

        assert "named_colors:" in result
        # RED -> #FF0000 (Red)
        assert "RED" in result
        assert "#FF0000" in result

        # Verify strict nesting structure
        data = yaml.safe_load(result)
        assert "named_colors" in data["appearance"]
        assert "named_colors" not in data["appearance"]["colors"]

    def test_generate_with_color_adjustment(self):
        """Generate with lightness/saturation adjustment."""
        generator = ConfigGenerator()
        # White in HSV (h=0, s=0, v=255) -> #FFFFFF
        kb_content = '{"layer_colors": [{"hue": 0, "sat": 0, "val": 255}]}'

        # Adjust lightness to 0.5 (Grey)
        result = generator.generate(kb_content, adjust_lightness=0.5)

        # #FFFFFF (rgb=1,1,1, h=0,l=1,s=0).
        # Target L=0.5. Result h=0,l=0.5,s=0 -> #808080 (approx)
        assert "#808080" in result

    def test_generate_sanitizes_short_names(self):
        """Ensure shortNames are sanitized (newlines/spaces collapsed)."""
        generator = ConfigGenerator()
        content = """
        {
            "custom_keycodes": [
                {"name": "KC_ENTER", "shortName": "En\\nter"},
                {"name": "KC_SPACE", "shortName": "Spa  ce"}
            ]
        }
        """

        result = generator.generate(content)

        assert "KC_ENTER: En ter" in result
        assert "KC_SPACE: Spa ce" in result
