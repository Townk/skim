# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Color utilities for converting and manipulating colors.

This module provides functions for color format conversion (hex to RGB,
RGB to hex), color adjustment (lightness and saturation), and gradient
generation for keymap layer colors.
"""

import colorsys
import re
from functools import lru_cache
from typing import cast

import webcolors

from skim.domain import clip


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


@lru_cache(maxsize=1024)
def str_to_rgb(color_str: str) -> tuple[float, float, float]:
    """Convert a hex color string to RGB tuple with values 0.0-1.0.

    This function is cached for performance since the same colors
    are often used repeatedly across a keymap.

    Args:
        color_str: Hexadecimal color string with or without '#' prefix.
                   Examples: '#FF0000', 'FF0000', '#00ff00'

    Returns:
        Tuple of (red, green, blue) with values in range 0.0-1.0.

    Examples:
        >>> str_to_rgb("#FF0000")
        (1.0, 0.0, 0.0)
        >>> str_to_rgb("00FF00")
        (0.0, 1.0, 0.0)
    """
    color_str = color_str.strip().lower()

    try:
        # 1. Handle Hex: "#00ff00"
        if color_str.startswith("#"):
            rgb = webcolors.hex_to_rgb(color_str)

        # 2. Handle Functional: "rgb(50%, 0, 0)" or "rgb(255, 255, 255)"
        elif color_str.startswith("rgb"):
            # This regex finds numbers followed optionally by a %
            matches = re.findall(r"([-+]?\d*\.\d+|\d+)(%)?", color_str)

            rgb_floats = []
            for value, unit in matches[:3]:  # We only care about R, G, and B
                num = float(value)
                if unit == "%":
                    # Convert 0-100% to 0-255
                    rgb_floats.append((num / 100.0) * 255.0)
                else:
                    rgb_floats.append(num)
            rgb = tuple(rgb_floats)

        # 3. Handle Named colors: "lime"
        else:
            rgb = webcolors.name_to_rgb(color_str)

    except (ValueError, AttributeError):
        # 4. Fallback to Legacy (The 'everything else' bucket)
        rgb = webcolors.html5_parse_legacy_color(color_str)

    # Final normalization to 0.0 - 1.0
    # We use min/max to ensure values stay in bounds if the user input "110%"
    return cast(tuple[float, float, float], tuple(max(0.0, min(1.0, c / 255.0)) for c in rgb))


def rgb_to_hex(red: float, green: float, blue: float) -> str:
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def adjust_luminance(color: str, adjustment_multiplier: float) -> str:
    """Adjust the luminance (brightness) of a color.

    Args:
        color: Hexadecimal color string.
        adjustment_multiplier: Multiplier for luminance (e.g., 0.7 for darker).

    Returns:
        Adjusted color as hexadecimal string.
    """
    hue, lum, sat = colorsys.rgb_to_hls(*str_to_rgb(color))
    lum = clip(lum * adjustment_multiplier, 0.0, 1.0)
    return rgb_to_hex(*colorsys.hls_to_rgb(hue, lum, sat))


def adjust_saturation(color: str, adjustment_multiplier: float) -> str:
    """Adjust the saturation of a color.

    Args:
        color: Hexadecimal color string.
        adjustment_multiplier: Multiplier for saturation (e.g., 0.5 for less saturated).

    Returns:
        Adjusted color as hexadecimal string.
    """
    hue, lum, sat = colorsys.rgb_to_hls(*str_to_rgb(color))
    sat = clip(sat * adjustment_multiplier, 0.0, 1.0)
    return rgb_to_hex(*colorsys.hls_to_rgb(hue, lum, sat))


def adjust_hls(
    color: str, luminance_multiplier: float = 1.0, saturation_multiplier: float = 1.0
) -> str:
    """Adjust both luminance and saturation of a color.

    Args:
        color: Hexadecimal color string.
        luminance_multiplier: Multiplier for luminance. Default: 1.0 (no change).
        saturation_multiplier: Multiplier for saturation. Default: 1.0 (no change).

    Returns:
        Adjusted color as hexadecimal string.
    """
    hue, lum, sat = colorsys.rgb_to_hls(*str_to_rgb(color))
    lum = clip(lum * luminance_multiplier, 0.0, 1.0)
    sat = clip(sat * saturation_multiplier, 0.0, 1.0)
    return rgb_to_hex(*colorsys.hls_to_rgb(hue, lum, sat))


def default_layer_color(
    layer_index: int,
    target_lightness: float | None = 0.31,
    target_saturation: float | None = 0.50,
) -> str:
    """Generate a default color for a layer using QMK's hue distribution.

    QMK distributes layer hues evenly across the color wheel using the
    formula ``hue = layer_index * (256 / 16)`` on a 0-255 scale (16 layers
    maximum). The saturation and value are both set to maximum (255).

    The resulting color is then adjusted using the same lightness and
    saturation parameters used by the config generator.

    Args:
        layer_index: Zero-based layer index.
        target_lightness: Desired lightness value (0.0-1.0). Default: 0.31
        target_saturation: Maximum saturation value (0.0-1.0). Default: 0.50

    Returns:
        Adjusted hex color string with '#' prefix.

    Examples:
        >>> default_layer_color(0)  # hue=0 (red)
        '#772828'
        >>> default_layer_color(4)  # hue=64 (green-ish)
        '#4F7728'
    """
    hue = (layer_index * 16) / 255.0  # QMK: layer * (256/16) on 0-255 scale
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    base_color = hex_str(r, g, b)
    return adjust_color(base_color, target_lightness, target_saturation)


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


def make_gradient(base_color: str, base_index: int = 2) -> tuple[str, str, str, str, str, str]:
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
        >>> grad = make_gradient("#347156", base_index=2)
        >>> len(grad)
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

    return tuple(gradient)
