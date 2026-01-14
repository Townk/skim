"""Parser for Keybard .kbi keymap format.

This module provides the :class:`KeybardParser` for parsing keymap files
from the Keybard keyboard configurator. Keybard is a configuration tool
for the Svalboard keyboard that stores keymaps with rich metadata.

The Keybard format structure::

    {
        "keymap": [
            ["KC_Q", "KC_W", ...],  // Layer 0 (60 keys)
            ["KC_1", "KC_2", ...],  // Layer 1
            ...
        ],
        "layer_colors": [
            {"hue": 85, "sat": 153, "val": 255},
            ...
        ],
        "custom_keycodes": [
            {"name": "MY_KEY", "shortName": "MK"},
            ...
        ],
        "cosmetic": {
            "layer": {"0": "Base", "1": "Nav", ...}
        },
        ...
    }

Example:
    >>> parser = KeybardParser()
    >>> layers = parser.parse(kbi_content)
    >>> metadata = parser.extract_metadata(kbi_content)
    >>> metadata["layer_names"]
    {'0': 'Base', '1': 'Navigation', ...}
"""

import json
from typing import Any

from skim.application.layer_transformer import LayerAdaptor


class KeybardParser:
    """Parses Keybard keymap files (.kbi) and extracts metadata.

    Keybard is the primary configuration tool for Svalboard keyboards.
    This parser extracts both the keycode layers and rich metadata
    including layer colors, names, and custom keycode definitions.

    The parser provides two main methods:
        - :meth:`parse`: Extracts keycode layers (for image generation)
        - :meth:`extract_metadata`: Extracts colors, names, and custom keys
          (for configuration generation)

    Example:
        >>> parser = KeybardParser()
        >>> layers = parser.parse(content)
        >>> metadata = parser.extract_metadata(content)
        >>> metadata["layer_colors"][0]["hue"]
        85
    """

    def parse(self, content: str) -> list[list[str]]:
        """Parse Keybard content and extract keycode layers.

        Parses the Keybard JSON structure and transforms the key
        ordering to match Skim's internal format using :class:`LayerAdaptor`.

        Args:
            content: JSON string content of the .kbi keymap file.

        Returns:
            List of layers, where each layer is a flat list of 60
            keycode strings in Skim's internal order.

        Raises:
            ValueError: If JSON is invalid, missing 'keymap' key,
                or structure is incorrect.

        Example:
            >>> content = Path("my-layout.kbi").read_text()
            >>> layers = parser.parse(content)
            >>> len(layers)
            8
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        if "keymap" not in data:
            raise ValueError("Missing 'keymap' key in keybard data")

        keymap = data["keymap"]
        if not isinstance(keymap, list):
            raise ValueError("'keymap' must be a list")

        return LayerAdaptor.from_keybard(keymap)

    def extract_metadata(self, content: str) -> dict[str, Any]:
        """Extract metadata (colors, names, custom keycodes) from Keybard content.

        Parses the Keybard JSON to extract configuration metadata that
        can be used to generate Skim configuration files.

        Extracted metadata includes:
            - ``layer_colors``: List of HSV color dicts for each layer
            - ``custom_keycodes``: List of custom keycode definitions
            - ``layer_names``: Dict mapping layer indices to display names

        Args:
            content: JSON string content of the .kbi keymap file.

        Returns:
            Dictionary containing:
                - ``layer_colors``: List[Dict] with keys: hue, sat, val (0-255)
                - ``custom_keycodes``: List[Dict] with keys: name, shortName
                - ``layer_names``: Dict[str, str] mapping "0", "1", etc. to names

        Raises:
            ValueError: If content contains invalid JSON.

        Example:
            >>> metadata = parser.extract_metadata(content)
            >>> metadata["layer_colors"]
            [{'hue': 85, 'sat': 153, 'val': 255}, ...]
            >>> metadata["layer_names"]
            {'0': 'Base', '1': 'Navigation'}
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        return {
            "layer_colors": data.get("layer_colors", []),
            "custom_keycodes": data.get("custom_keycodes", []),
            "layer_names": data.get("cosmetic", {}).get("layer", {}),
        }
