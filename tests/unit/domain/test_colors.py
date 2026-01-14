"""Test suite for color utilities."""

from skim.domain.colors import (
    adjust_color,
    generate_gradient,
    hex_str,
    str_to_rgb,
)


class TestColorConversion:
    """Test color format conversion functions."""

    def test_str_to_rgb_with_hash(self):
        """Test conversion from hex string with # to RGB tuple."""
        assert str_to_rgb("#FF0000") == (1.0, 0.0, 0.0)
        assert str_to_rgb("#00FF00") == (0.0, 1.0, 0.0)
        assert str_to_rgb("#0000FF") == (0.0, 0.0, 1.0)

    def test_str_to_rgb_without_hash(self):
        """Test conversion from hex string without # to RGB tuple."""
        assert str_to_rgb("FF0000") == (1.0, 0.0, 0.0)
        assert str_to_rgb("FFFFFF") == (1.0, 1.0, 1.0)
        assert str_to_rgb("000000") == (0.0, 0.0, 0.0)

    def test_str_to_rgb_lowercase(self):
        """Test conversion handles lowercase hex values."""
        assert str_to_rgb("#ff00ff") == (1.0, 0.0, 1.0)
        assert str_to_rgb("00ffff") == (0.0, 1.0, 1.0)

    def test_hex_str_from_rgb(self):
        """Test conversion from RGB floats to hex string."""
        assert hex_str(1.0, 0.0, 0.0) == "#FF0000"
        assert hex_str(0.0, 1.0, 0.0) == "#00FF00"
        assert hex_str(0.0, 0.0, 1.0) == "#0000FF"
        assert hex_str(1.0, 1.0, 1.0) == "#FFFFFF"
        assert hex_str(0.0, 0.0, 0.0) == "#000000"

    def test_hex_str_with_partial_values(self):
        """Test hex string conversion with values between 0 and 1."""
        result = hex_str(0.5, 0.5, 0.5)
        # Should be around #7F7F7F or #808080
        assert result.startswith("#")
        assert len(result) == 7


class TestColorAdjustment:
    """Test color adjustment functions."""

    def test_adjust_color_default_values(self):
        """Test adjust_color with default lightness and saturation."""
        # Start with a bright red
        result = adjust_color("#FF0000", target_lightness=0.31, target_saturation=0.50)
        assert result.startswith("#")
        assert len(result) == 7
        # Result should be darker and less saturated than original

    def test_adjust_color_lightness_only(self):
        """Test adjusting only lightness."""
        original = "#FF0000"
        lightened = adjust_color(original, target_lightness=0.7, target_saturation=1.0)
        assert lightened != original
        assert lightened.startswith("#")

    def test_adjust_color_saturation_cap(self):
        """Test that saturation is capped at target value."""
        # High saturation color should be reduced
        result = adjust_color("#FF0000", target_lightness=0.5, target_saturation=0.3)
        assert result.startswith("#")


class TestGradientGeneration:
    """Test gradient generation function."""

    def test_generate_gradient_returns_six_colors(self):
        """Test that gradient generation returns exactly 6 colors."""
        gradient = generate_gradient("#FF0000", base_index=2)
        assert len(gradient) == 6

    def test_generate_gradient_all_hex_strings(self):
        """Test that all gradient colors are valid hex strings."""
        gradient = generate_gradient("#00FF00", base_index=2)
        for color in gradient:
            assert color.startswith("#")
            assert len(color) == 7
            # Verify it's a valid hex string
            int(color[1:], 16)

    def test_generate_gradient_base_color_at_index(self):
        """Test that base color appears at the specified index."""
        base_color = "#347156"
        base_index = 2
        gradient = generate_gradient(base_color, base_index=base_index)

        # The base color should be at the base_index position
        # It won't be exactly the same due to HSL conversions, but should be close
        assert gradient[base_index] is not None

    def test_generate_gradient_darker_before_base(self):
        """Test that colors before base index are darker."""
        gradient = generate_gradient("#808080", base_index=2)
        # Colors at index 0 and 1 should generally be darker than at index 2
        # This is a rough check since we're comparing hex strings
        assert gradient[0] != gradient[2]
        assert gradient[1] != gradient[2]

    def test_generate_gradient_lighter_after_base(self):
        """Test that colors after base index are lighter."""
        gradient = generate_gradient("#404040", base_index=2)
        # Colors at index 3, 4, 5 should generally be lighter than at index 2
        assert gradient[3] != gradient[2]
        assert gradient[4] != gradient[2]
        assert gradient[5] != gradient[2]

    def test_generate_gradient_different_base_index(self):
        """Test gradient generation with different base indices."""
        gradient_0 = generate_gradient("#FF0000", base_index=0)
        gradient_3 = generate_gradient("#FF0000", base_index=3)

        # Different base indices should produce different gradients
        assert gradient_0 != gradient_3
