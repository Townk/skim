"""Keycode mapping loader for QMK keycode to label translations.

This module provides the :class:`KeycodeMappingLoader` for loading and merging
QMK keycode mappings from YAML files. These mappings define how raw QMK keycodes
are translated to human-readable labels for display in keymap images.

The mapping files contain several dictionaries:
    - ``keycodes``: Direct keycode to label mappings (e.g., "KC_A" -> "A")
    - ``reversed_alias``: Function patterns to alias keycodes (e.g., "LSFT(KC_1)" -> "KC_EXLM")
    - ``modifiers``: Modifier function prefixes (e.g., "S" -> "Shift")
    - ``layer_symbols``: Layer function symbols (e.g., "MO" -> "⬓")

Example:
    Loading and using keycode mappings::

        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        # Access individual mapping dictionaries
        keycodes = mappings["keycodes"]
        modifiers = mappings["modifiers"]

    Merging custom mappings with bundled defaults::

        loader = KeycodeMappingLoader()
        base = loader.load_bundled()
        custom = loader.load_from_file(Path("my-keycodes.yaml"))
        merged = loader.merge_mappings(base, custom)
"""

from pathlib import Path
from typing import Any

import yaml


class KeycodeMappingLoader:
    """Loads and manages QMK keycode to display label mappings.

    Provides methods to load keycode mappings from YAML files, including
    the bundled default mappings and user-provided custom mappings.
    Supports merging multiple mapping sources with custom overrides
    taking precedence over defaults.

    Example:
        >>> loader = KeycodeMappingLoader()
        >>> mappings = loader.load_bundled()
        >>> mappings["keycodes"]["KC_A"]
        'A'
        >>> mappings["modifiers"]["S"]
        '%%nf-md-apple_keyboard_shift;'
    """

    def load_bundled(self) -> dict[str, Any]:
        """Load the bundled default keycode mappings.

        Returns:
            Dictionary containing 'keycodes', 'reversed_alias', 'modifiers',
            and 'layer_symbols' mapping dictionaries.

        Raises:
            FileNotFoundError: If the bundled mapping file is missing.

        Example:
            >>> loader = KeycodeMappingLoader()
            >>> mappings = loader.load_bundled()
            >>> "KC_SPACE" in mappings["keycodes"]
            True
        """
        bundled_path = (
            Path(__file__).parent.parent / "assets" / "data" / "keycode-mappings.yaml"
        )
        return self.load_from_file(bundled_path)

    def load_from_file(self, path: Path) -> dict[str, Any]:
        """Load keycode mappings from a YAML file.

        Args:
            path: Path to the YAML file containing keycode mappings.

        Returns:
            Dictionary containing the parsed mapping data.

        Raises:
            FileNotFoundError: If the specified file doesn't exist.
            yaml.YAMLError: If the file contains invalid YAML.

        Example:
            >>> loader = KeycodeMappingLoader()
            >>> custom = loader.load_from_file(Path("custom-keycodes.yaml"))
        """
        with open(path) as f:
            return yaml.safe_load(f)

    def merge_mappings(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge two mapping dictionaries with override taking precedence.

        Combines base and override mappings, where values in the override
        dictionary replace corresponding values in the base. This allows
        users to customize specific keycodes while retaining defaults
        for everything else.

        Args:
            base: Base mapping dictionary (typically bundled defaults).
            override: Override mapping dictionary (user customizations).

        Returns:
            New dictionary with merged mappings from both sources.

        Example:
            >>> loader = KeycodeMappingLoader()
            >>> base = loader.load_bundled()
            >>> custom = {"keycodes": {"KC_A": "Custom A"}, "modifiers": {}}
            >>> merged = loader.merge_mappings(base, custom)
            >>> merged["keycodes"]["KC_A"]
            'Custom A'
        """
        result = {
            "keycodes": {**base.get("keycodes", {}), **override.get("keycodes", {})},
            "reversed_alias": {
                **base.get("reversed_alias", {}),
                **override.get("reversed_alias", {}),
            },
            "modifiers": {**base.get("modifiers", {}), **override.get("modifiers", {})},
            "layer_symbols": {
                **base.get("layer_symbols", {}),
                **override.get("layer_symbols", {}),
            },
        }
        return result
