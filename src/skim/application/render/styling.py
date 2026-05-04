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
        ```pycon
        >>> hex_str(1.0, 0.0, 0.0)
        '#FF0000'
        >>> hex_str(0.5, 0.5, 0.5)
        '#808080'

        ```
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
        ```pycon
        >>> str_to_rgb("#FF0000")
        (1.0, 0.0, 0.0)
        >>> str_to_rgb("00FF00")
        (0.0, 1.0, 0.0)

        ```
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


def lighten(color: str, amount: float) -> str:
    """Shift a color's HSL lightness by an additive amount.

    Args:
        color: Hexadecimal color string.
        amount: Value added to the lightness component in HSL space. Positive
            values lighten, negative values darken. The result is clamped to
            ``[0.0, 1.0]``.

    Returns:
        Adjusted color as a hexadecimal string.
    """
    hue, lum, sat = colorsys.rgb_to_hls(*str_to_rgb(color))
    lum = clip(lum + amount, 0.0, 1.0)
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


_GREEN_HUE_OFFSET = 85
"""Hue offset (on the 0-255 scale) that places ``layer_index=0`` at green.

``85 / 255`` is exactly ``1/3``, which is the green primary on the HSV
hue wheel. Using this offset matches the Svalboard convention of
starting the layer-color sequence at green for the base layer.
"""

_HUE_STEP_8 = 32
"""Hue step (on the 0-255 scale) between consecutive bit-reversed slots
within an octet of 8 hues.

``256 / 8 = 32`` — partitions the wheel into 8 hues at 45° apart, which
is wide enough that adjacent hues read as decisively different colors
(as opposed to 22.5° spacing where greens and yellow-greens blur).
"""

_INTERMEDIATE_HUE_OFFSET = 16
"""Half-octet offset (``32 / 2``) applied to layers 16–31 so their hues
land between the eight base hues used by layers 0–15."""

_BRIGHT_LIGHTNESS = 0.22
"""Lightness for the eight "bright" layers in each half (0–7 and 16–23)."""

_DIM_LIGHTNESS = 0.40
"""Lightness for the eight "dim" layers in each half (8–15 and 24–31).

Same hue as the corresponding bright layer; the lightness shift makes
them visually distinct without consuming another hue slot.
"""


def _bit_reverse_3(n: int) -> int:
    """Reverse the low 3 bits of ``n`` (assumes ``0 <= n < 8``).

    Used to walk the eight base hues so consecutive layers land on
    maximally-distant hues: layer 0 → 0, layer 1 → 4 (180° away), layer
    2 → 2 (90° back), layer 3 → 6 (180° from layer 2), then 1, 5, 3, 7
    fill the remaining slots at 45° each.

    Examples:
        ```pycon
        >>> _bit_reverse_3(0), _bit_reverse_3(1), _bit_reverse_3(2)
        (0, 4, 2)
        >>> _bit_reverse_3(3), _bit_reverse_3(4)
        (6, 1)

        ```
    """
    result = 0
    for i in range(3):
        if n & (1 << i):
            result |= 1 << (2 - i)
    return result


def default_layer_color(
    layer_index: int,
    target_lightness: float | None = None,
    target_saturation: float | None = 0.65,
) -> str:
    """Generate a default color for a layer.

    Combines two dimensions to deliver 32 visually distinct colors —
    well beyond what the human eye can separate in pure hue alone:

    - **Hue**: 8 bit-reversed hues at 45° apart (0, 180°, 90°, 270°, 45°,
      225°, 135°, 315° — relative to green). This wider spacing reads
      as decisively different colors instead of the 22.5° smear that
      makes greens, yellow-greens, and lime all blur together.
    - **Lightness**: alternates between a bright ``0.22`` and a dim
      ``0.40`` every 8 layers, so layer 8 (dim green) is unmistakable
      next to layer 0 (bright green) even though they share a hue.

    The mapping for ``layer_index`` (taken mod 32 first):

    | Range  | Hue band                            | Lightness |
    |--------|-------------------------------------|-----------|
    | 0–7    | 8 base hues (45° apart from green)  | bright    |
    | 8–15   | same 8 base hues                    | dim       |
    | 16–23  | 8 intermediate hues (offset 22.5°)  | bright    |
    | 24–31  | same 8 intermediate hues            | dim       |

    Layers 0–15 cover sixteen visually-distinct colors (eight hues × two
    lightnesses); layers 16–31 fill in the intermediate hues for keymaps
    that exceed the first half of the budget. Indices past 31 wrap.

    The ``target_lightness`` argument, when not ``None``, overrides the
    bright/dim split — pass it explicitly when you want the whole
    palette at a single fixed lightness (e.g., when generating a
    monochrome variant). Leave it as ``None`` to keep the bright/dim
    alternation.

    Args:
        layer_index: Zero-based layer index.
        target_lightness: Desired lightness value (0.0-1.0). When
            ``None`` (default), the bright/dim alternation chooses
            lightness automatically.
        target_saturation: Maximum saturation value (0.0-1.0). Default:
            0.65

    Returns:
        Adjusted hex color string with '#' prefix.

    Examples:
        ```pycon
        >>> default_layer_color(0)  # bright green base
        '#145D14'
        >>> default_layer_color(1)  # 180° from green, bright
        '#5D145C'
        >>> default_layer_color(8)  # same hue as layer 0, dim
        '#24A824'
        >>> default_layer_color(32) == default_layer_color(0)  # wraps
        True

        ```
    """
    n = layer_index % 32
    octet = n // 8  # 0, 1, 2, or 3
    within_octet = n % 8
    hue_slot = _bit_reverse_3(within_octet)  # 0..7 in shuffled order
    is_intermediate = octet >= 2  # layers 16-31
    is_dim = (octet % 2) == 1  # 8-15 or 24-31

    intermediate_offset = _INTERMEDIATE_HUE_OFFSET if is_intermediate else 0
    hue_byte = (hue_slot * _HUE_STEP_8 + intermediate_offset + _GREEN_HUE_OFFSET) % 256
    hue = hue_byte / 255.0

    lightness = target_lightness
    if lightness is None:
        lightness = _DIM_LIGHTNESS if is_dim else _BRIGHT_LIGHTNESS

    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    base_color = hex_str(r, g, b)
    return adjust_color(base_color, lightness, target_saturation)


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
        ```pycon
        >>> adjust_color("#FF0000", 0.31, 0.50)
        '#7F0000'  # Darker, less saturated red

        ```
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


def nudge_color_hsl(
    hex_color: str,
    *,
    saturation_delta: float = 0.0,
    lightness_delta: float = 0.0,
) -> str:
    """Nudge a hex color's saturation and/or lightness by additive deltas.

    Both ``saturation_delta`` and ``lightness_delta`` are added to the
    current channel value and clamped into ``[0.0, 1.0]``. The hue is
    preserved. Use ``adjust_color`` instead when you want to *set* a
    target value rather than nudge by a delta.

    Args:
        hex_color: Input color in hexadecimal format.
        saturation_delta: Amount added to the current saturation. Use a
            negative value to decrease.
        lightness_delta: Amount added to the current lightness. Use a
            negative value to decrease.

    Returns:
        Adjusted color as a ``#RRGGBB`` hexadecimal string.

    Examples:
        ```pycon
        >>> nudge_color_hsl("#7F7F7F", lightness_delta=0.05)
        '#8C8C8C'

        ```
    """
    red, green, blue = str_to_rgb(hex_color)
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    new_saturation = max(0.0, min(1.0, saturation + saturation_delta))
    new_lightness = max(0.0, min(1.0, lightness + lightness_delta))
    r_new, g_new, b_new = colorsys.hls_to_rgb(hue, new_lightness, new_saturation)
    return hex_str(r_new, g_new, b_new)


def derive_accent_line(fill_color: str) -> str:
    """Derive a lighter "line" accent tone from a darker accent fill.

    The design uses two tones per accent — a dark fill (used for chip
    bodies and key corner triangles) and a lighter line tone (used for
    chip outlines, section title text, and underlines). The fill lives
    in config; this helper computes the line tone in HSL space by
    raising lightness ~25 percentage points and reducing saturation
    ~10 percentage points.

    Args:
        fill_color: The dark accent fill, e.g. ``"#89511C"`` or
            ``"#41687F"``.

    Returns:
        A hex colour string for the lighter line tone.
    """
    r, g, b = str_to_rgb(fill_color)
    hue, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
    new_lightness = clip(lightness + 0.25, 0.0, 1.0)
    new_saturation = clip(saturation - 0.10, 0.0, 1.0)
    nr, ng, nb = colorsys.hls_to_rgb(hue, new_lightness, new_saturation)
    return hex_str(nr, ng, nb)


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
        ```pycon
        >>> grad = make_gradient("#347156", base_index=2)
        >>> len(grad)
        6
        >>> gradient[2]  # Base color at index 2
        '#347156'

        ```
    """
    red, green, blue = str_to_rgb(base_color)
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)

    num_colors = 6
    lightness_values = []

    for i in range(num_colors):
        if i < base_index:
            progress = i / base_index if base_index > 0 else 0
            target_l = lightness * (0.5 + 0.5 * progress)
        elif i == base_index:
            target_l = lightness
        else:
            remaining = num_colors - 1 - base_index
            progress = (i - base_index) / remaining if remaining > 0 else 0
            max_lightness = min(0.85, lightness * 1.9)
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
