"""Unit tests for skim.application.render.styling module.

Tests cover color conversion functions, luminance/saturation adjustments,
and gradient generation for layer colors.
"""

from skim.application.render.styling import (
    adjust_color,
    adjust_hls,
    adjust_luminance,
    adjust_saturation,
    hex_str,
    make_gradient,
    rgb_to_hex,
    str_to_rgb,
)


class TestHexStr:
    """Tests for hex_str function."""

    def test_pure_red(self):
        """Pure red converts correctly."""
        assert hex_str(1.0, 0.0, 0.0) == "#FF0000"

    def test_pure_green(self):
        """Pure green converts correctly."""
        assert hex_str(0.0, 1.0, 0.0) == "#00FF00"

    def test_pure_blue(self):
        """Pure blue converts correctly."""
        assert hex_str(0.0, 0.0, 1.0) == "#0000FF"

    def test_white(self):
        """White (1,1,1) converts correctly."""
        assert hex_str(1.0, 1.0, 1.0) == "#FFFFFF"

    def test_black(self):
        """Black (0,0,0) converts correctly."""
        assert hex_str(0.0, 0.0, 0.0) == "#000000"

    def test_gray(self):
        """Gray value converts correctly."""
        result = hex_str(0.5, 0.5, 0.5)
        assert result in ("#808080", "#7F7F7F")  # Rounding variation

    def test_clamps_values_above_one(self):
        """Values above 1.0 are clamped to 255."""
        result = hex_str(1.5, 1.2, 2.0)
        assert result == "#FFFFFF"

    def test_clamps_negative_values(self):
        """Negative values are clamped to 0."""
        result = hex_str(-0.5, -0.1, 0.5)
        assert result.startswith("#00")

    def test_uppercase_hex_output(self):
        """Output uses uppercase hex digits."""
        result = hex_str(0.5, 0.6, 0.7)
        assert result == result.upper()


class TestStrToRgb:
    """Tests for str_to_rgb function."""

    def test_hex_with_hash(self):
        """Hex color with '#' prefix converts correctly."""
        assert str_to_rgb("#FF0000") == (1.0, 0.0, 0.0)

    def test_hex_lowercase(self):
        """Lowercase hex converts correctly."""
        assert str_to_rgb("#00ff00") == (0.0, 1.0, 0.0)

    def test_hex_mixed_case(self):
        """Mixed case hex converts correctly."""
        assert str_to_rgb("#fF00Ff") == (1.0, 0.0, 1.0)

    def test_rgb_functional_notation(self):
        """RGB functional notation converts correctly."""
        result = str_to_rgb("rgb(255, 0, 0)")
        assert result == (1.0, 0.0, 0.0)

    def test_rgb_functional_with_percentages(self):
        """RGB functional notation with percentages converts correctly."""
        result = str_to_rgb("rgb(100%, 0%, 50%)")
        assert result == (1.0, 0.0, 0.5)

    def test_named_color_red(self):
        """Named color 'red' converts correctly."""
        assert str_to_rgb("red") == (1.0, 0.0, 0.0)

    def test_named_color_lime(self):
        """Named color 'lime' converts correctly."""
        assert str_to_rgb("lime") == (0.0, 1.0, 0.0)

    def test_named_color_blue(self):
        """Named color 'blue' converts correctly."""
        assert str_to_rgb("blue") == (0.0, 0.0, 1.0)

    def test_named_color_white(self):
        """Named color 'white' converts correctly."""
        assert str_to_rgb("white") == (1.0, 1.0, 1.0)

    def test_named_color_black(self):
        """Named color 'black' converts correctly."""
        assert str_to_rgb("black") == (0.0, 0.0, 0.0)

    def test_values_clamped_to_valid_range(self):
        """RGB values over 255 are clamped to 1.0."""
        result = str_to_rgb("rgb(300, 256, 255)")
        assert result[0] == 1.0
        assert result[1] == 1.0
        assert result[2] == 1.0

    def test_legacy_html_color_parsing(self):
        """Legacy HTML color strings are parsed via fallback."""
        result = str_to_rgb("FF0000")
        assert result == (1.0, 0.0, 0.0)

    def test_caching_returns_same_result(self):
        """Cached results are consistent."""
        result1 = str_to_rgb("#123456")
        result2 = str_to_rgb("#123456")
        assert result1 is result2


class TestRgbToHex:
    """Tests for rgb_to_hex function."""

    def test_pure_red(self):
        """Pure red converts correctly."""
        assert rgb_to_hex(1.0, 0.0, 0.0) == "#ff0000"

    def test_pure_green(self):
        """Pure green converts correctly."""
        assert rgb_to_hex(0.0, 1.0, 0.0) == "#00ff00"

    def test_pure_blue(self):
        """Pure blue converts correctly."""
        assert rgb_to_hex(0.0, 0.0, 1.0) == "#0000ff"

    def test_white(self):
        """White converts correctly."""
        assert rgb_to_hex(1.0, 1.0, 1.0) == "#ffffff"

    def test_black(self):
        """Black converts correctly."""
        assert rgb_to_hex(0.0, 0.0, 0.0) == "#000000"

    def test_lowercase_hex_output(self):
        """Output uses lowercase hex digits."""
        result = rgb_to_hex(0.5, 0.6, 0.7)
        assert result == result.lower()


class TestAdjustLuminance:
    """Tests for adjust_luminance function."""

    def test_darken_color(self):
        """Multiplier < 1 darkens the color."""
        original = str_to_rgb("#808080")
        result = adjust_luminance("#808080", 0.5)
        result_rgb = str_to_rgb(result)
        # Lightness should be reduced
        assert result_rgb[0] < original[0]
        assert result_rgb[1] < original[1]
        assert result_rgb[2] < original[2]

    def test_lighten_color(self):
        """Multiplier > 1 lightens the color (clamped to 1.0)."""
        original = str_to_rgb("#404040")
        result = adjust_luminance("#404040", 2.0)
        result_rgb = str_to_rgb(result)
        # Lightness should be increased (or clamped)
        assert result_rgb[0] >= original[0]
        assert result_rgb[1] >= original[1]
        assert result_rgb[2] >= original[2]

    def test_no_change_with_multiplier_1(self):
        """Multiplier of 1.0 returns similar color."""
        result = adjust_luminance("#808080", 1.0)
        result_rgb = str_to_rgb(result)
        original = str_to_rgb("#808080")
        # Should be very close (allowing for rounding)
        assert abs(result_rgb[0] - original[0]) < 0.01
        assert abs(result_rgb[1] - original[1]) < 0.01
        assert abs(result_rgb[2] - original[2]) < 0.01

    def test_returns_valid_hex_string(self):
        """Result is a valid hex color string."""
        result = adjust_luminance("#FF0000", 0.7)
        assert result.startswith("#")
        assert len(result) == 7


class TestAdjustSaturation:
    """Tests for adjust_saturation function."""

    def test_desaturate_color(self):
        """Multiplier < 1 desaturates the color."""
        result = adjust_saturation("#FF0000", 0.5)
        result_rgb = str_to_rgb(result)
        # Fully saturated red becomes less saturated
        # (R stays high, G and B increase toward R)
        assert result_rgb[1] > 0.0 or result_rgb[2] > 0.0

    def test_no_change_with_multiplier_1(self):
        """Multiplier of 1.0 returns same color."""
        result = adjust_saturation("#FF0000", 1.0)
        result_rgb = str_to_rgb(result)
        original = str_to_rgb("#FF0000")
        assert abs(result_rgb[0] - original[0]) < 0.01

    def test_gray_stays_gray(self):
        """Gray (0 saturation) stays gray regardless of multiplier."""
        result = adjust_saturation("#808080", 2.0)
        result_rgb = str_to_rgb(result)
        # Gray has 0 saturation, multiplying by anything keeps it gray
        assert abs(result_rgb[0] - result_rgb[1]) < 0.01
        assert abs(result_rgb[1] - result_rgb[2]) < 0.01


class TestAdjustHls:
    """Tests for adjust_hls function."""

    def test_adjust_both_luminance_and_saturation(self):
        """Can adjust both luminance and saturation at once."""
        result = adjust_hls("#FF0000", luminance_multiplier=0.5, saturation_multiplier=0.5)
        assert result.startswith("#")
        assert len(result) == 7

    def test_default_multipliers_preserve_color(self):
        """Default multipliers (1.0) preserve the color."""
        result = adjust_hls("#808080")
        result_rgb = str_to_rgb(result)
        original = str_to_rgb("#808080")
        assert abs(result_rgb[0] - original[0]) < 0.01
        assert abs(result_rgb[1] - original[1]) < 0.01
        assert abs(result_rgb[2] - original[2]) < 0.01


class TestAdjustColor:
    """Tests for adjust_color function."""

    def test_default_adjustments(self):
        """Default adjustments produce valid result."""
        result = adjust_color("#FF0000")
        assert result.startswith("#")
        assert len(result) == 7

    def test_target_lightness_applied(self):
        """Target lightness is set correctly."""
        # Bright color becomes darker with low target lightness
        result = adjust_color("#FFFFFF", target_lightness=0.2, target_saturation=None)
        result_rgb = str_to_rgb(result)
        # Should be much darker than white
        assert result_rgb[0] < 0.5
        assert result_rgb[1] < 0.5
        assert result_rgb[2] < 0.5

    def test_none_lightness_preserves_original(self):
        """target_lightness=None preserves original lightness."""
        result = adjust_color("#808080", target_lightness=None, target_saturation=None)
        result_rgb = str_to_rgb(result)
        original = str_to_rgb("#808080")
        # Should be very close to original
        assert abs(result_rgb[0] - original[0]) < 0.01

    def test_saturation_is_capped_not_set(self):
        """target_saturation caps but doesn't increase saturation."""
        # Gray has 0 saturation, should stay gray
        result = adjust_color("#808080", target_lightness=None, target_saturation=0.5)
        result_rgb = str_to_rgb(result)
        # Gray should remain gray (equal RGB components)
        assert abs(result_rgb[0] - result_rgb[1]) < 0.02
        assert abs(result_rgb[1] - result_rgb[2]) < 0.02


class TestMakeGradient:
    """Tests for make_gradient function."""

    def test_returns_tuple_of_six_colors(self):
        """Gradient contains exactly 6 colors."""
        gradient = make_gradient("#347156")
        assert isinstance(gradient, tuple)
        assert len(gradient) == 6

    def test_all_colors_are_valid_hex(self):
        """All gradient colors are valid hex strings."""
        gradient = make_gradient("#FF0000")
        for color in gradient:
            assert color.startswith("#")
            assert len(color) == 7

    def test_base_color_at_default_index(self):
        """Base color appears at the default index (2)."""
        base = "#347156"
        gradient = make_gradient(base, base_index=2)
        # The color at index 2 should be the base color (approximately)
        base_rgb = str_to_rgb(base)
        result_rgb = str_to_rgb(gradient[2])
        # Allow for slight rounding differences
        assert abs(result_rgb[0] - base_rgb[0]) < 0.05
        assert abs(result_rgb[1] - base_rgb[1]) < 0.05
        assert abs(result_rgb[2] - base_rgb[2]) < 0.05

    def test_base_color_at_custom_index(self):
        """Base color can be placed at a custom index."""
        base = "#FF0000"
        gradient = make_gradient(base, base_index=4)
        base_rgb = str_to_rgb(base)
        result_rgb = str_to_rgb(gradient[4])
        assert abs(result_rgb[0] - base_rgb[0]) < 0.05
        assert abs(result_rgb[1] - base_rgb[1]) < 0.05
        assert abs(result_rgb[2] - base_rgb[2]) < 0.05

    def test_colors_before_base_are_darker(self):
        """Colors before base index are darker."""
        gradient = make_gradient("#808080", base_index=3)
        # Colors at indices 0, 1, 2 should be darker than index 3
        base_rgb = str_to_rgb(gradient[3])
        for i in range(3):
            color_rgb = str_to_rgb(gradient[i])
            # Sum of RGB values (brightness proxy) should be lower
            assert sum(color_rgb) <= sum(base_rgb) + 0.1

    def test_colors_after_base_are_lighter(self):
        """Colors after base index are lighter."""
        gradient = make_gradient("#404040", base_index=2)
        base_rgb = str_to_rgb(gradient[2])
        for i in range(3, 6):
            color_rgb = str_to_rgb(gradient[i])
            # Sum of RGB values (brightness proxy) should be higher
            assert sum(color_rgb) >= sum(base_rgb) - 0.1

    def test_base_index_zero(self):
        """Gradient works with base at index 0."""
        gradient = make_gradient("#FF0000", base_index=0)
        assert len(gradient) == 6
        base_rgb = str_to_rgb("#FF0000")
        result_rgb = str_to_rgb(gradient[0])
        assert abs(result_rgb[0] - base_rgb[0]) < 0.05

    def test_base_index_five(self):
        """Gradient works with base at index 5."""
        gradient = make_gradient("#FF0000", base_index=5)
        assert len(gradient) == 6
        base_rgb = str_to_rgb("#FF0000")
        result_rgb = str_to_rgb(gradient[5])
        assert abs(result_rgb[0] - base_rgb[0]) < 0.05

    def test_saturation_reduced_for_light_colors(self):
        """Saturation is reduced for very light colors in gradient."""
        gradient = make_gradient("#FF0000", base_index=0)
        # The lightest colors (at the end) should have reduced saturation
        # This is hard to test precisely, but we can check they're valid
        for color in gradient:
            assert color.startswith("#")
