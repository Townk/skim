"""Color utilities for converting and manipulating colors.

This module provides functions for color format conversion (hex to RGB,
RGB to hex), color adjustment (lightness and saturation), and gradient
generation for keymap layer colors.
"""

import colorsys


def str_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert a hex color string to RGB tuple with values 0.0-1.0.

    Args:
        hex_color: Hexadecimal color string with or without '#' prefix.
                   Examples: '#FF0000', 'FF0000', '#00ff00'

    Returns:
        Tuple of (red, green, blue) with values in range 0.0-1.0.

    Examples:
        >>> str_to_rgb("#FF0000")
        (1.0, 0.0, 0.0)
        >>> str_to_rgb("00FF00")
        (0.0, 1.0, 0.0)
    """
    hex_color = hex_color.lstrip("#")

    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    return (r, g, b)


def hex_str(red: float, green: float, blue: float) -> str:
    """Convert RGB floats to hexadecimal color string.

    Args:
        red: Red component in range 0.0-1.0.
        green: Green component in range 0.0-1.0.
        blue: Blue component in range 0.0-1.0.

    Returns:
        Hexadecimal color string with '#' prefix in uppercase.
        Format: '#RRGGBB'

    Examples:
        >>> hex_str(1.0, 0.0, 0.0)
        '#FF0000'
        >>> hex_str(0.5, 0.5, 0.5)
        '#808080'
    """
    r = int(round(red * 255))
    g = int(round(green * 255))
    b = int(round(blue * 255))

    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    return f"#{r:02X}{g:02X}{b:02X}"


def adjust_color(
    hex_color: str,
    target_lightness: float | None = 0.31,
    target_saturation: float | None = 0.50,
) -> str:
    """Adjust the lightness and saturation of a color.

    Converts the color to HLS space, adjusts saturation (capped at target)
    and lightness (set to target), then converts back to RGB hex format.
    If a target is None, the original value is preserved.

    Args:
        hex_color: Input color in hexadecimal format.
        target_lightness: Desired lightness value (0.0-1.0).
                          Default: 0.31
        target_saturation: Maximum saturation value (0.0-1.0).
                          Original saturation is capped at this value.
                          Default: 0.50

    Returns:
        Adjusted color as hexadecimal string with '#' prefix.

    Examples:
        >>> adjust_color("#FF0000", 0.31, 0.50)
        '#7F0000'  # Darker, less saturated red
    """
    red, green, blue = str_to_rgb(hex_color)
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)

    s_adjusted = saturation
    if target_saturation is not None:
        s_adjusted = min(saturation, target_saturation)

    l_adjusted = lightness
    if target_lightness is not None:
        l_adjusted = target_lightness

    r_new, g_new, b_new = colorsys.hls_to_rgb(hue, l_adjusted, s_adjusted)
    return hex_str(r_new, g_new, b_new)


def generate_gradient(base_color: str, base_index: int = 2) -> list[str]:
    """Generate a 6-color gradient with base color at specified index.

    Creates a gradient that interpolates from dark to light colors,
    with the base color appearing at the specified index position.

    Args:
        base_color: The base color in hexadecimal format.
        base_index: Position (0-5) where base color should appear.
                   Colors before this index will be darker,
                   colors after will be lighter. Default: 2

    Returns:
        List of 6 hexadecimal color strings forming a gradient.

    Examples:
        >>> gradient = generate_gradient("#347156", base_index=2)
        >>> len(gradient)
        6
        >>> gradient[2]  # Base color at index 2
        '#347156'
    """
    red, green, blue = str_to_rgb(base_color)
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)

    num_colors = 6
    lightness_values = []

    for i in range(num_colors):
        if i < base_index:
            progress = i / base_index if base_index > 0 else 0
            target_l = lightness * (0.15 + 0.85 * progress)
        elif i == base_index:
            target_l = lightness
        else:
            remaining = num_colors - 1 - base_index
            progress = (i - base_index) / remaining if remaining > 0 else 0
            max_lightness = min(0.95, lightness * 2.3)
            target_l = lightness + (max_lightness - lightness) * progress

        lightness_values.append(min(1.0, target_l))

    gradient = []
    for target_l in lightness_values:
        adjusted_s = saturation
        if target_l > 0.7:
            saturation_factor = 1.0 - (target_l - 0.7) * 0.5
            adjusted_s = saturation * saturation_factor

        r_new, g_new, b_new = colorsys.hls_to_rgb(hue, target_l, adjusted_s)
        gradient.append(hex_str(r_new, g_new, b_new))

    return gradient
