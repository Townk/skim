"""Parser for Vial .vil keymap format.

This module provides the :class:`VialParser` for parsing keymap files
exported from the Vial keyboard configurator. Vial files use a nested
structure with clusters of keys rather than flat layer arrays.

The Vial format structure::

    {
        "version": 1,
        "layout": [
            [  // Layer 0
                ["KC_Q", "KC_W", ...],  // Cluster 0
                ["KC_E", "KC_R", ...],  // Cluster 1
                ...
            ],
            [  // Layer 1
                ...
            ],
            ...
        ],
        ...
    }

Example:
    >>> parser = VialParser()
    >>> layers = parser.parse(vil_content)
    >>> len(layers[0])  # Keys per layer after flattening
    60
"""

import json

from skim.application.layer_transformer import LayerAdaptor


class VialParser:
    """Parses Vial keymap files (.vil) and transforms to Skim format.

    Vial is a popular GUI keyboard configurator that exports keymaps
    in a nested JSON structure organized by clusters. This parser
    flattens the cluster structure and reorders keys to match
    Skim's expected layout format.

    The transformation is handled by :class:`LayerAdaptor` after
    initial parsing.

    Example:
        >>> parser = VialParser()
        >>> with open("keymap.vil") as f:
        ...     content = f.read()
        >>> layers = parser.parse(content)
        >>> len(layers)  # Number of layers
        8
    """

    def parse(self, content: str) -> list[list[str]]:
        """Parse Vial content and extract keycode layers.

        Parses the nested Vial JSON structure, flattens the cluster
        organization, and transforms the key ordering to match
        Skim's internal format.

        Args:
            content: JSON string content of the .vil keymap file.

        Returns:
            List of layers, where each layer is a flat list of 60
            keycode strings in Skim's internal order.

        Raises:
            ValueError: If JSON is invalid, missing 'layout' key,
                or structure is incorrect.

        Example:
            >>> content = Path("my-keymap.vil").read_text()
            >>> layers = parser.parse(content)
            >>> layers[0][:6]  # First 6 keys of first layer
            ['KC_Q', 'KC_W', 'KC_E', 'KC_R', 'KC_T', 'KC_Y']
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        if "layout" not in data:
            raise ValueError("Missing 'layout' key in vial data")

        layout = data["layout"]
        if not isinstance(layout, list):
            raise ValueError("'layout' must be a list")

        return LayerAdaptor.from_vial(layout)
