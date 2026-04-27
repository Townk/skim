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
        from skim.application.loaders.keymap_loader import is_empty_layer
        from skim.domain import KeymapType
        from skim.domain.adapters import KeymapJsonAdapter

        try:
            data = json.loads(keybard_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in Keybard file: {e}") from e

        layer_colors_raw = data.get("layer_colors", [])
        layer_names = data.get("cosmetic", {}).get("layer", {})
        custom_keycodes = data.get("custom_keycodes", [])

        # Drop empty layers (all KC_NO/KC_TRNS) the same way the vial/c2json
        # path does in ``generate_from_keymap``. Without this, every empty
        # slot still gets a config entry and load_keymap's zip(indices,
        # non_empty) silently shifts every layer past the first empty one
        # — so e.g. ``MO(14)`` resolves to the wrong rendered layer because
        # skim's index 14 was paired with a layer that came from kbi[N>14].
        keymap_raw = data.get("keymap", [])
        normalized = KeymapJsonAdapter.transform(keymap_raw, KeymapType.KEYBARD)
        active_indices = [i for i, layer in enumerate(normalized) if not is_empty_layer(layer)]

        def apply_adjustment(hex_c: str) -> str:
            if adjust_lightness is not None or adjust_saturation is not None:
                return adjust_color(hex_c, adjust_lightness, adjust_saturation)
            return hex_c

        keyboard_layers = self._build_layers_for_indices(active_indices, layer_names)
        palette_layers = self._build_palette_layers_for_indices(
            active_indices, layer_colors_raw, apply_adjustment
        )
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

    def _build_layers_for_indices(
        self, active_indices: list[int], layer_names: dict[str, str]
    ) -> list[dict[str, str | None]]:
        """Build keyboard.layers list for a sparse set of source-layer indices.

        Each index keeps its original kbi position so QMK layer-switch
        keycodes (``MO(N)``, ``TO(N)``, …) resolve to the right rendered
        layer downstream — empty layers don't shift later ones into wrong
        slots.
        """
        layers = []
        for idx in active_indices:
            name = layer_names.get(str(idx), f"Layer {idx}")
            layers.append({"index": idx, "name": name, "id": None, "variant": None})
        return layers

    def _build_palette_layers_for_indices(
        self,
        active_indices: list[int],
        layer_colors_raw: list[dict[str, int]],
        apply_adjustment: Callable[[str], str],
    ) -> list[dict[str, Any]]:
        """Convert HSV layer colors to hex palette entries for a sparse set.

        ``palette.layers[pos]`` is indexed by *config position* (not QMK
        index), so this list mirrors ``active_indices`` in order: the
        layer at ``active_indices[i]`` gets the color sampled from
        ``layer_colors_raw[active_indices[i]]`` (or a neutral fallback if
        the kbi file omits that slot).
        """
        palette_layers = []
        for idx in active_indices:
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

        Checks each raw keycode string against the known keycodes and
        macro function names. Function calls (containing parentheses)
        are skipped since the renderer handles them via macro expansion.

        Args:
            layers: List of layers, each a list of keycode strings.
            standard_keycodes: Set of known QMK keycode names and macro
                function names from keycode-mappings.yaml.

        Returns:
            List of override dicts with keycode mapped to itself.
        """
        seen: set[str] = set()
        overrides: list[dict[str, str]] = []
        for layer in layers:
            for keycode in layer:
                if keycode in standard_keycodes or keycode in seen:
                    continue
                if "(" in keycode and ")" in keycode:
                    continue
                seen.add(keycode)
                overrides.append({"keycode": keycode, "target": keycode})
        return overrides

    @staticmethod
    def _load_standard_keycodes() -> set[str]:
        """Load the set of known QMK keycodes and macro function names.

        Combines keycodes and macro_functions keys from
        keycode-mappings.yaml.

        Returns:
            Set of known QMK keycode and macro function names.
        """
        from skim.assets import ASSETS

        mapping = yaml.safe_load(ASSETS.keycode_mappings.read_text())
        standard: set[str] = set()
        for section in ("keycodes", "macro_functions"):
            if section in mapping:
                standard.update(mapping[section].keys())
        return standard

    def _build_default_palette_layers(self, num_layers: int) -> list[dict[str, Any]]:
        """Build palette layers with default colors for each layer index."""
        return self._build_default_palette_layers_for_indices(list(range(num_layers)))

    def _build_default_palette_layers_for_indices(self, indices: list[int]) -> list[dict[str, Any]]:
        """Build palette layers with default colors for specific layer indices."""
        from skim.application.render.styling import default_layer_color

        return [
            {"base_color": default_layer_color(idx), "color_index": 2, "gradient": None}
            for idx in indices
        ]

    @staticmethod
    def _flatten_keymap_layers(raw_layers: list, keymap_type: object) -> list[list[str]]:
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
            is_empty_layer,
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

        # Flatten and filter out empty layers (all KC_NO/KC_TRNS)
        flat_layers = self._flatten_keymap_layers(raw_layers, keymap_type)
        active_indices = [i for i, layer in enumerate(flat_layers) if not is_empty_layer(layer)]

        # Build layers and palette only for non-empty indices
        keyboard_layers = [
            {"index": idx, "name": f"Layer {idx}", "id": None, "variant": None}
            for idx in active_indices
        ]
        palette_layers = self._build_default_palette_layers_for_indices(active_indices)

        # Scan for non-standard keycodes (only active layers)
        active_flat = [flat_layers[i] for i in active_indices]
        standard = self._load_standard_keycodes()
        keycode_overrides = self._find_non_standard_keycodes(active_flat, standard)

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
