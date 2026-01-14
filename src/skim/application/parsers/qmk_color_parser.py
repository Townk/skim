"""Parser for QMK color.h header files.

This module provides the :class:`QmkColorParser` for extracting color
definitions from QMK firmware color.h header files. These files contain
``#define`` statements for named colors in both RGB and HSV formats.

Supported formats::

    # define RGB_CORAL 0xFF, 0x7F, 0x50
    # define HSV_TEAL 128, 255, 255

Example:
    >>> parser = QmkColorParser()
    >>> colors = parser.parse(color_h_content)
    >>> colors
    {'CORAL': '#FF7F50', 'TEAL': '#00FFFF'}
"""

import colorsys
import re

from skim.domain.colors import hex_str


class QmkColorParser:
    """Parses QMK color definitions from C header files.

    Extracts ``RGB_*`` and ``HSV_*`` color definitions from QMK color.h files,
    converting them to hexadecimal color strings. When both RGB and HSV
    definitions exist for the same color name, HSV takes precedence.

    QMK uses 0-255 range for all HSV components (not 0-360 for hue).

    Example:
        >>> parser = QmkColorParser()
        >>> content = '''
        ... #define RGB_RED 0xFF, 0x00, 0x00
        ... #define HSV_BLUE 170, 255, 255
        ... '''
        >>> parser.parse(content)
        {'RED': '#FF0000', 'BLUE': '#0000FF'}
    """

    def parse(self, content: str) -> dict[str, str]:
        """Parse C header content and return color name to hex mapping.

        Extracts both ``RGB_*`` and ``HSV_*`` color definitions from the content.
        For each color name (without the ``RGB_``/``HSV_`` prefix), returns the
        hexadecimal color value. If both RGB and HSV are defined for
        the same name, HSV definition takes precedence.

        Args:
            content: C header file content containing #define statements.

        Returns:
            Dictionary mapping color names (without prefix) to hex strings.
            Example: {"RED": "#FF0000", "BLUE": "#0000FF"}

        Example:
            >>> content = '''
            ... #define RGB_CORAL 0xFF, 0x7F, 0x50
            ... #define HSV_CORAL 11, 176, 255
            ... #define RGB_TEAL 0x00, 0x80, 0x80
            ... '''
            >>> parser.parse(content)
            {'CORAL': '#FF7A4D', 'TEAL': '#008080'}
            # Note: CORAL uses HSV definition (precedence)
        """
        colors = {}

        rgb_pattern = r"#define\s+RGB_(\w+)\s+(0x[0-9A-Fa-f]+|\d+),\s*(0x[0-9A-Fa-f]+|\d+),\s*(0x[0-9A-Fa-f]+|\d+)"
        for match in re.finditer(rgb_pattern, content):
            name = match.group(1)
            r = int(match.group(2), 0)
            g = int(match.group(3), 0)
            b = int(match.group(4), 0)
            colors[name] = hex_str(r / 255.0, g / 255.0, b / 255.0)

        hsv_pattern = r"#define\s+HSV_(\w+)\s+(\d+),\s*(\d+),\s*(\d+)"
        for match in re.finditer(hsv_pattern, content):
            name = match.group(1)
            h = int(match.group(2))
            s = int(match.group(3))
            v = int(match.group(4))

            r_val, g_val, b_val = colorsys.hsv_to_rgb(h / 255.0, s / 255.0, v / 255.0)
            colors[name] = hex_str(r_val, g_val, b_val)

        return colors
