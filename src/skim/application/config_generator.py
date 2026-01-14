"""Configuration Generator for creating Skim config from source files.

This module provides the :class:`ConfigGenerator` which extracts metadata
from Keybard keymap files and QMK color headers to generate Skim YAML
configuration files. This automates the initial configuration setup
for users migrating from these tools.

The generator extracts:
    - Layer colors (converted from HSV to hex)
    - Layer names from cosmetic settings
    - Custom keycode short names for display labels
    - Named color definitions from QMK headers

Example:
    Generating configuration from a Keybard file::

        generator = ConfigGenerator()
        yaml_config = generator.generate(
            keybard_content=keybard_json_str,
            qmk_header_content=qmk_color_h_content,
            adjust_lightness=0.31,
        )
        Path("skim-config.yaml").write_text(yaml_config)
"""

import colorsys
import re

import yaml

from skim.application.parsers.keybard_parser import KeybardParser
from skim.application.parsers.qmk_color_parser import QmkColorParser
from skim.domain.colors import adjust_color, hex_str


class ConfigGenerator:
    """Generates Skim configuration YAML from source keymap files.

    This class extracts relevant metadata from Keybard (.kbi) files and
    optional QMK color headers to produce a ready-to-use Skim configuration.
    The generated config includes layer definitions, color schemes, and
    keycode display overrides.

    Example:
        >>> generator = ConfigGenerator()
        >>> yaml_output = generator.generate(keybard_content)
        >>> print(yaml_output)
        layers:
          - base_color: '#347156'
            label: BASE
            name: Base
            id: '0'
        ...
    """

    def generate(
        self,
        keybard_content: str,
        qmk_header_content: str | None = None,
        adjust_lightness: float | None = None,
        adjust_saturation: float | None = None,
    ) -> str:
        """Generate YAML configuration from Keybard content.

        Parses the Keybard JSON file to extract layer colors, names, and
        custom keycode definitions. Optionally integrates QMK color
        definitions from a color.h header file.

        Args:
            keybard_content: JSON string content of the Keybard .kbi file.
            qmk_header_content: Optional C header content from QMK color.h
                file containing RGB_* and HSV_* color definitions.
            adjust_lightness: Optional target lightness (0.0-1.0) to apply
                to all extracted colors. Useful for ensuring readable
                contrast in generated images.
            adjust_saturation: Optional maximum saturation (0.0-1.0) to cap
                all extracted colors. Original saturation is reduced to
                this value if it exceeds the target.

        Returns:
            YAML-formatted string containing the generated Skim configuration.
            Ready to be written to a .yaml file.

        Raises:
            ValueError: If keybard_content contains invalid JSON.

        Example:
            >>> generator = ConfigGenerator()
            >>> config = generator.generate(
            ...     keybard_content=Path("layout.kbi").read_text(),
            ...     qmk_header_content=Path("color.h").read_text(),
            ...     adjust_lightness=0.31,
            ... )
            >>> Path("skim-config.yaml").write_text(config)
        """
        parser = KeybardParser()
        metadata = parser.extract_metadata(keybard_content)

        def apply_adjustment(hex_c: str) -> str:
            if adjust_lightness is not None or adjust_saturation is not None:
                return adjust_color(hex_c, adjust_lightness, adjust_saturation)
            return hex_c

        qmk_colors = {}
        if qmk_header_content:
            qmk_parser = QmkColorParser()
            qmk_colors = qmk_parser.parse(qmk_header_content)
            for k, v in qmk_colors.items():
                qmk_colors[k] = apply_adjustment(v)

        layers_config = []
        layer_colors = metadata.get("layer_colors", [])
        layer_names = metadata.get("layer_names", {})

        for idx, color_data in enumerate(layer_colors):
            h = color_data.get("hue", 0) / 255.0
            s = color_data.get("sat", 255) / 255.0
            v = color_data.get("val", 255) / 255.0

            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            base_color = hex_str(r, g, b)
            base_color = apply_adjustment(base_color)

            idx_str = str(idx)
            name = layer_names.get(idx_str, f"Layer {idx}")

            layer_entry = {
                "base_color": base_color,
                "label": name.upper()[:4].strip(),
                "name": name,
                "id": str(idx),
            }
            layers_config.append(layer_entry)

        overrides = {}
        for item in metadata.get("custom_keycodes", []):
            if "name" in item and "shortName" in item:
                short_name = item["shortName"]
                short_name = re.sub(r"\s+", " ", short_name).strip()
                overrides[item["name"]] = short_name

        config_dict = {
            "layers": layers_config,
            "appearance": {
                "colors": {
                    "text": "#000000",
                    "background": "#FFFFFF",
                    "neutral": "#70768B",
                }
            },
        }

        if qmk_colors:
            config_dict["appearance"]["colors"]["named_colors"] = qmk_colors

        if overrides:
            config_dict["keycodes"] = overrides

        return yaml.dump(config_dict, sort_keys=False)
