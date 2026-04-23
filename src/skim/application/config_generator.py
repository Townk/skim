# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Configuration generator for creating skim config YAML files.

Provides :class:`ConfigGenerator` which can produce default configuration
templates or extract metadata from Keybard (.kbi) files to generate
pre-populated configuration files.

Example:
    Generate default config::

        generator = ConfigGenerator()
        print(generator.generate_default())

    Generate from Keybard file::

        generator = ConfigGenerator()
        yaml_config = generator.generate_from_keybard(
            Path("layout.kbi").read_text(),
            adjust_lightness=0.31,
        )
        Path("skim-config.yaml").write_text(yaml_config)
"""

import colorsys
import json
import re
from collections.abc import Callable
from typing import Any

import yaml

from skim.application.render.styling import adjust_color, hex_str
from skim.data.config import SkimConfig


class ConfigGenerator:
    """Generates skim configuration YAML from defaults or source files."""

    def generate_default(self) -> str:
        """Generate YAML from SkimConfig defaults.

        Returns:
            YAML string containing the default skim configuration.
        """
        config = SkimConfig()
        data = config.model_dump(mode="json")
        return yaml.dump(data, sort_keys=False, default_flow_style=False)

    def generate_from_keybard(
        self,
        keybard_content: str,
        qmk_header_content: str | None = None,
        adjust_lightness: float | None = None,
        adjust_saturation: float | None = None,
    ) -> str:
        """Generate config YAML by extracting metadata from a Keybard file.

        Parses the .kbi JSON to extract layer colors, layer names, and
        custom keycode definitions. Optionally applies color adjustments
        and merges QMK named colors from a color.h header.

        Args:
            keybard_content: JSON string from a .kbi file.
            qmk_header_content: Optional C header content with color defines.
            adjust_lightness: Target lightness (0.0-1.0) for extracted colors.
            adjust_saturation: Max saturation (0.0-1.0) for extracted colors.

        Returns:
            YAML string containing the generated skim configuration.

        Raises:
            ValueError: If keybard_content is not valid JSON.
        """
        try:
            data = json.loads(keybard_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in Keybard file: {e}") from e

        num_layers = data.get("layers", 0)
        layer_colors_raw = data.get("layer_colors", [])
        layer_names = data.get("cosmetic", {}).get("layer", {})
        custom_keycodes = data.get("custom_keycodes", [])

        def apply_adjustment(hex_c: str) -> str:
            if adjust_lightness is not None or adjust_saturation is not None:
                return adjust_color(hex_c, adjust_lightness, adjust_saturation)
            return hex_c

        keyboard_layers = self._build_layers(num_layers, layer_names)
        palette_layers = self._build_palette_layers(num_layers, layer_colors_raw, apply_adjustment)
        keycode_overrides = self._build_keycode_overrides(custom_keycodes)

        palette_overrides: dict[str, str] = {}
        if qmk_header_content:
            palette_overrides = self._parse_qmk_colors(qmk_header_content, apply_adjustment)

        config_dict: dict[str, Any] = SkimConfig().model_dump(mode="json")
        config_dict["keyboard"]["layers"] = keyboard_layers
        config_dict["keycodes"]["overrides"] = keycode_overrides
        config_dict["output"]["style"]["palette"]["layers"] = palette_layers
        config_dict["output"]["style"]["palette"]["overrides"] = palette_overrides

        return yaml.dump(config_dict, sort_keys=False, default_flow_style=False)

    def _build_layers(
        self, num_layers: int, layer_names: dict[str, str]
    ) -> list[dict[str, str | None]]:
        """Build keyboard.layers list from layer count and cosmetic names."""
        layers = []
        for idx in range(num_layers):
            name = layer_names.get(str(idx), f"Layer {idx}")
            label = name.upper()[:4].strip() if name != f"Layer {idx}" else f"L{idx}"
            layers.append({"index": idx, "label": label, "name": name, "id": None, "variant": None})
        return layers

    def _build_palette_layers(
        self,
        num_layers: int,
        layer_colors_raw: list[dict[str, int]],
        apply_adjustment: Callable[[str], str],
    ) -> list[dict[str, Any]]:
        """Convert HSV layer colors to hex palette entries."""
        palette_layers = []
        for idx in range(num_layers):
            if idx < len(layer_colors_raw):
                color_data = layer_colors_raw[idx]
                h = color_data.get("hue", 0) / 255.0
                s = color_data.get("sat", 255) / 255.0
                v = color_data.get("val", 255) / 255.0
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                base_color = hex_str(r, g, b)
                base_color = apply_adjustment(base_color)
            else:
                base_color = "#6F768B"

            palette_layers.append({"base_color": base_color, "color_index": 2, "gradient": None})
        return palette_layers

    def _build_keycode_overrides(
        self, custom_keycodes: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """Build keycodes.overrides from custom keycode definitions."""
        overrides = []
        for idx, item in enumerate(custom_keycodes):
            name = item.get("name", "")
            short_name = item.get("shortName", "")
            if not name or not short_name:
                continue

            short_name = re.sub(r"\s+", " ", short_name).strip()
            overrides.append({"keycode": name, "target": short_name})
            overrides.append({"keycode": f"USER{idx:02d}", "target": f"@@{name};"})

        return overrides

    @staticmethod
    def _find_non_standard_keycodes(
        layers: list[list[str]], standard_keycodes: set[str]
    ) -> list[dict[str, str]]:
        """Find keycodes in layers that are not in the standard QMK set.

        Extracts all identifier tokens from each keycode string (including
        arguments inside macro function calls) and returns overrides for
        any token not in the standard set.

        Args:
            layers: List of layers, each a list of keycode strings.
            standard_keycodes: Set of known QMK keycode names, macro
                function names, and modifier constants.

        Returns:
            List of override dicts with keycode mapped to itself.
        """
        seen: set[str] = set()
        overrides: list[dict[str, str]] = []
        for layer in layers:
            for keycode in layer:
                tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", keycode)
                for token in tokens:
                    if token not in standard_keycodes and token not in seen:
                        seen.add(token)
                        overrides.append({"keycode": token, "target": token})
        return overrides

    @staticmethod
    def _load_standard_keycodes() -> set[str]:
        """Load the set of all known QMK keycode identifiers.

        Combines keycodes, pre_processing keys, macro_functions keys,
        and modifier_union keys from keycode-mappings.yaml.

        Returns:
            Set of all known QMK keycode/function/modifier names.
        """
        from skim.assets import ASSETS

        mapping = yaml.safe_load(ASSETS.keycode_mappings.read_text())
        standard: set[str] = set()
        for section in ("keycodes", "pre_processing", "macro_functions", "modifier_union"):
            if section in mapping:
                standard.update(mapping[section].keys())
        return standard

    def _build_default_palette_layers(self, num_layers: int) -> list[dict[str, Any]]:
        """Build palette layers with default colors for each layer index."""
        from skim.application.render.styling import default_layer_color

        return [
            {"base_color": default_layer_color(idx), "color_index": 2, "gradient": None}
            for idx in range(num_layers)
        ]

    @staticmethod
    def _flatten_keymap_layers(
        raw_layers: list, keymap_type: object
    ) -> list[list[str]]:
        """Flatten raw keymap layers into a list of string lists.

        For Vial, each layer is a list of clusters (list of lists).
        For c2json, each layer is already a flat list of strings.

        Args:
            raw_layers: Raw layer data from the keymap file.
            keymap_type: The detected KeymapType enum value.

        Returns:
            List of layers, each a flat list of keycode strings.
        """
        from skim.domain import KeymapType

        flat: list[list[str]] = []
        for layer in raw_layers:
            if keymap_type == KeymapType.VIAL:
                keys: list[str] = []
                for cluster in layer:
                    if isinstance(cluster, list):
                        keys.extend(cluster)
                    else:
                        keys.append(str(cluster))
                flat.append(keys)
            else:
                flat.append(layer)
        return flat

    def generate_from_keymap(self, content: str) -> str:
        """Generate config YAML from a Vial or c2json keymap file.

        Detects the keymap format, counts layers to create default layer
        entries with auto-generated colors, and scans for non-standard
        keycodes to populate overrides.

        For Keybard files, delegates to generate_from_keybard() which
        extracts richer metadata (layer names, colors, custom keycodes).

        Args:
            content: JSON string from a keymap file (.vil or .json).

        Returns:
            YAML string containing the generated skim configuration.

        Raises:
            ValueError: If content is not valid JSON or format is unknown.
        """
        from skim.application.loaders.keymap_loader import (
            _detect_keymap_from_json,
        )
        from skim.domain import KeymapType

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in keymap file: {e}") from e

        keymap_type = _detect_keymap_from_json(data)

        if keymap_type == KeymapType.KEYBARD:
            return self.generate_from_keybard(content)

        # Count layers based on format
        if keymap_type == KeymapType.VIAL:
            raw_layers = data.get("layout", [])
        else:  # C2JSON
            raw_layers = data.get("layers", [])

        num_layers = len(raw_layers)

        # Build default layers and palette
        keyboard_layers = self._build_layers(num_layers, {})
        palette_layers = self._build_default_palette_layers(num_layers)

        # Scan for non-standard keycodes
        flat_layers = self._flatten_keymap_layers(raw_layers, keymap_type)
        standard = self._load_standard_keycodes()
        keycode_overrides = self._find_non_standard_keycodes(flat_layers, standard)

        config_dict: dict[str, Any] = SkimConfig().model_dump(mode="json")
        config_dict["keyboard"]["layers"] = keyboard_layers
        config_dict["keycodes"]["overrides"] = keycode_overrides
        config_dict["output"]["style"]["palette"]["layers"] = palette_layers

        return yaml.dump(config_dict, sort_keys=False, default_flow_style=False)

    def _parse_qmk_colors(
        self, header_content: str, apply_adjustment: Callable[[str], str]
    ) -> dict[str, str]:
        """Parse QMK color.h defines into name->hex mapping.

        Supports:
            #define HSV_MYCOLOR h, s, v
            #define RGB_MYCOLOR r, g, b
        """
        colors: dict[str, str] = {}
        for line in header_content.splitlines():
            line = line.strip()
            if not line.startswith("#define"):
                continue

            hsv_match = re.match(r"#define\s+HSV_(\w+)\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", line)
            if hsv_match:
                name = hsv_match.group(1).lower()
                h = int(hsv_match.group(2)) / 255.0
                s = int(hsv_match.group(3)) / 255.0
                v = int(hsv_match.group(4)) / 255.0
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                colors[name] = apply_adjustment(hex_str(r, g, b))
                continue

            rgb_match = re.match(r"#define\s+RGB_(\w+)\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", line)
            if rgb_match:
                name = rgb_match.group(1).lower()
                r = int(rgb_match.group(2)) / 255.0
                g = int(rgb_match.group(3)) / 255.0
                b = int(rgb_match.group(4)) / 255.0
                colors[name] = apply_adjustment(hex_str(r, g, b))

        return colors
