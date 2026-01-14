"""Keymap data models for keyboard layout visualization.

This module defines the core domain models that represent keyboard layers
and keymap data structures used throughout the skim application.

The data models follow a hierarchical structure:
    - :class:`KeymapData` contains multiple :class:`Layer` instances
    - Each :class:`Layer` represents a single keyboard layer with labels,
      colors, and layer toggle information

Example:
    Creating a simple layer::

        layer = Layer(
            name="Base",
            labels=[["Q", "W", "E", "R", "T", "Y"] for _ in range(10)],
            colors=[
                "#FF0000",
                "#FF3333",
                "#FF6666",
                "#FF9999",
                "#FFCCCC",
                "#FFFFFF",
                "#808080",
            ],
            primary_color=2,
            secondary_color=6,
            layer_toggles=[[None] * 6 for _ in range(10)],
        )

    Creating keymap data from layers::

        keymap = KeymapData(layers=[layer])
        layer_count = keymap.layer_count()  # Returns 1
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Layer:
    """Represents a single keyboard layer with visual and functional data.

    A Layer contains all information needed to render a keyboard layer image,
    including key labels, color scheme, and layer toggle mappings.

    The Svalboard layout uses 10 clusters (8 finger + 2 thumb), each with 6 keys,
    totaling 60 keys per layer.

    Attributes:
        name: Display name for this layer (e.g., "Base", "Navigation", "Symbols").
        labels: 2D list of key labels organized as 10 rows x 6 columns.
            Each row represents a key cluster on the keyboard.
        colors: List of exactly 7 hex color strings forming the layer's gradient.
            Colors 0-5 are the gradient, color 6 is the neutral/secondary color.
        primary_color: Index (0-5) into colors list for primary key highlighting.
        secondary_color: Index (0-6) into colors list for secondary elements.
        layer_toggles: 2D list matching labels dimensions, containing target
            layer indices for layer-switching keys, or None for regular keys.

    Raises:
        ValueError: If colors list doesn't have exactly 7 elements.
        ValueError: If labels or layer_toggles don't have exactly 10 rows.
        ValueError: If any row in labels or layer_toggles doesn't have 6 keys.

    Example:
        >>> layer = Layer(
        ...     name="Symbols",
        ...     labels=[["!", "@", "#", "$", "%", "^"] for _ in range(10)],
        ...     colors=["#3471FF"] * 6 + ["#808080"],
        ...     primary_color=2,
        ...     secondary_color=6,
        ...     layer_toggles=[[None, None, None, None, None, 0] for _ in range(10)],
        ... )
        >>> layer.to_dict()["name"]
        'Symbols'
    """

    name: str
    labels: list[list[str]]
    colors: list[str]
    primary_color: int
    secondary_color: int
    layer_toggles: list[list[int | None]]

    def __post_init__(self) -> None:
        """Validate layer data structure after initialization.

        Raises:
            ValueError: If any structural constraints are violated.
        """
        if len(self.colors) != 7:
            raise ValueError("Layer must have exactly 7 colors")

        if len(self.labels) != 10:
            raise ValueError(
                "Layer labels must have 10 rows (8 finger clusters + 2 thumb clusters)"
            )

        if len(self.layer_toggles) != 10:
            raise ValueError("Layer toggles must have 10 rows")

        for row in self.labels:
            if len(row) != 6:
                raise ValueError("Each label row must have 6 keys")

        for row in self.layer_toggles:
            if len(row) != 6:
                raise ValueError("Each toggle row must have 6 keys")

    def to_dict(self) -> dict[str, Any]:
        """Convert layer to dictionary format for JSON serialization.

        The output dictionary uses camelCase keys to match the Typst
        template's expected input format.

        Returns:
            Dictionary with keys: name, labels, colors, primaryColor,
            secondaryColor, layerToggles.

        Example:
            >>> layer.to_dict()
            {'name': 'Base', 'labels': [...], 'colors': [...],
             'primaryColor': 2, 'secondaryColor': 6, 'layerToggles': [...]}
        """
        return {
            "name": self.name,
            "labels": self.labels,
            "colors": self.colors,
            "primaryColor": self.primary_color,
            "secondaryColor": self.secondary_color,
            "layerToggles": self.layer_toggles,
        }


@dataclass
class KeymapData:
    """Container for all keyboard layers in a keymap.

    KeymapData serves as the top-level data structure holding all layers
    that make up a complete keyboard layout configuration.

    Attributes:
        layers: List of Layer objects representing each keyboard layer.

    Example:
        >>> base = Layer(name="Base", ...)
        >>> nav = Layer(name="Nav", ...)
        >>> keymap = KeymapData(layers=[base, nav])
        >>> keymap.layer_count()
        2
        >>> keymap.get_layer(0).name
        'Base'
    """

    layers: list[Layer]

    def to_dict(self) -> dict[str, Any]:
        """Convert keymap to dictionary format for JSON serialization.

        Returns:
            Dictionary with 'layers' key containing list of layer dictionaries.

        Example:
            >>> keymap.to_dict()
            {'layers': [{'name': 'Base', ...}, {'name': 'Nav', ...}]}
        """
        return {"layers": [layer.to_dict() for layer in self.layers]}

    def get_layer(self, index: int) -> Layer | None:
        """Retrieve a layer by its index.

        Args:
            index: Zero-based index of the layer to retrieve.

        Returns:
            The Layer at the specified index, or None if index is out of bounds.

        Example:
            >>> keymap = KeymapData(layers=[base_layer, nav_layer])
            >>> keymap.get_layer(0).name
            'Base'
            >>> keymap.get_layer(99) is None
            True
        """
        if 0 <= index < len(self.layers):
            return self.layers[index]
        return None

    def layer_count(self) -> int:
        """Return the total number of layers in this keymap.

        Returns:
            Integer count of layers.

        Example:
            >>> keymap = KeymapData(layers=[layer1, layer2, layer3])
            >>> keymap.layer_count()
            3
        """
        return len(self.layers)
