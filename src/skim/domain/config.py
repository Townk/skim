"""Configuration models for Skim keyboard layout image generator.

This module provides dataclass-based configuration models for customizing
the appearance and behavior of generated keymap images. Configuration can
be loaded from YAML files or constructed programmatically.

The configuration hierarchy is:
    - :class:`SkimConfig` (root) contains:
        - :class:`LayerConfigList` of :class:`LayerConfig` instances
        - :class:`AppearanceConfig` with :class:`BorderConfig` and :class:`ColorConfig`
        - Optional keycode overrides and layer mappings

Example:
    Loading configuration from a YAML file::

        from pathlib import Path
        import yaml

        with open("config.yaml") as f:
            data = yaml.safe_load(f)
        config = SkimConfig.from_dict(data)

    Using default configuration with overrides::

        user_config = SkimConfig.from_dict({"layers": [...]})
        full_config = user_config.merge_with_defaults()
"""

from __future__ import annotations

from collections import UserList
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BorderConfig:
    """Configuration for key border appearance.

    Attributes:
        color: Hex color string for key borders (e.g., "#000000").
        radius: Corner radius in pixels for rounded key corners.

    Example:
        >>> border = BorderConfig(color="#333333", radius=15)
    """

    color: str = "#000000"
    radius: int = 20


@dataclass
class ColorConfig:
    """Configuration for the color scheme used in keymap images.

    Defines the base colors used throughout the generated images,
    including text, background, and optional named color palette.

    Attributes:
        text: Hex color for key label text.
        background: Hex color for the image background.
        neutral: Hex color for neutral/inactive elements and layer-toggle keys.
        named_colors: Optional dictionary mapping color names to hex values.
            Used to reference colors by name in layer configurations.

    Example:
        >>> colors = ColorConfig(
        ...     text="#000000",
        ...     background="#FFFFFF",
        ...     neutral="#70768B",
        ...     named_colors={"primary": "#3471FF", "accent": "#FF5733"},
        ... )
    """

    text: str = "#000000"
    background: str = "#FFFFFF"
    neutral: str = "#70768B"
    named_colors: dict[str, str] | None = None


@dataclass
class AppearanceConfig:
    """Combined appearance configuration for keymap images.

    Groups border and color configurations into a single structure
    that can be serialized and passed to the Typst rendering engine.

    Attributes:
        border: Border styling configuration.
        colors: Color scheme configuration.

    Example:
        >>> appearance = AppearanceConfig(
        ...     border=BorderConfig(radius=10),
        ...     colors=ColorConfig(background="#F5F5F5"),
        ... )
        >>> appearance.to_dict()
        {'border': {'color': '#000000', 'radius': 10},
         'colors': {'text': '#000000', 'background': '#F5F5F5', ...}}
    """

    border: BorderConfig = field(default_factory=BorderConfig)
    colors: ColorConfig = field(default_factory=ColorConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert appearance config to dictionary for JSON serialization.

        Returns:
            Dictionary with 'border' and 'colors' keys containing
            the respective configuration values.
        """
        return {"border": asdict(self.border), "colors": asdict(self.colors)}


@dataclass
class LayerConfig:
    """Configuration for a single keyboard layer.

    Defines the visual properties and identification for a layer,
    including its base color, display name, and optional identifiers.

    Attributes:
        base_color: Hex color string or named color for this layer's theme.
            A gradient will be generated from this base color.
        id: Optional unique identifier for referencing this layer in keycodes
            (e.g., "_NAV", "_SYM"). Used for layer toggle resolution.
        name: Display name shown in the generated image (e.g., "Navigation").
        label: Short label (typically 2-4 chars) for compact display.
        index: Zero-based position in the layer list. Set automatically
            when added to a :class:`LayerConfigList`.

    Example:
        >>> layer = LayerConfig(
        ...     base_color="#3471FF",
        ...     id="_NAV",
        ...     name="Navigation",
        ...     label="NAV",
        ... )
        >>> layer.is_valid()
        False  # index not yet assigned
    """

    base_color: str
    id: str | None = None
    name: str | None = None
    label: str | None = None
    index: int = -1

    def is_valid(self) -> bool:
        """Check if this layer configuration has been properly initialized.

        A layer is valid if it has been assigned a non-negative index,
        which happens when it's added to a :class:`LayerConfigList`.

        Returns:
            True if layer has a valid index (>= 0), False otherwise.
        """
        return self.index >= 0


NoneConfigLayer = LayerConfig(index=-1, base_color="#000000", id="", name="", label="")
"""Sentinel value representing a missing or unresolved layer configuration.

Used as a return value when layer lookup fails, avoiding None checks.
The ``is_valid()`` method will return False for this sentinel.
"""


class LayerConfigList(UserList[LayerConfig]):
    """A list of layer configurations with indexed access by ID or position.

    Extends UserList to provide flexible layer lookup by either numeric index
    or string identifier. Automatically assigns indices to layers when added.

    The list supports three access patterns:
        - Numeric index: ``layers[0]`` returns first layer
        - String ID: ``layers["_NAV"]`` returns layer with id="_NAV"
        - String numeric: ``layers["2"]`` returns layer at index 2

    Example:
        >>> layers = LayerConfigList(
        ...     [
        ...         LayerConfig(base_color="#FF0000", id="_BASE", name="Base"),
        ...         LayerConfig(base_color="#00FF00", id="_NAV", name="Nav"),
        ...     ]
        ... )
        >>> layers[0].name
        'Base'
        >>> layers["_NAV"].name
        'Nav'
        >>> layers["nonexistent"].is_valid()
        False  # Returns NoneConfigLayer sentinel
    """

    def __init__(self, initlist: list[LayerConfig] | None = None) -> None:
        """Initialize the layer list with optional initial layers.

        Args:
            initlist: Optional list of LayerConfig objects to initialize with.
                Each layer will have its index automatically assigned.
        """
        self._index_map: dict[str, int] = {}
        super().__init__(initlist)
        if initlist:
            for i, item in enumerate(self.data):
                item.index = i
                if item.id:
                    self._index_map[item.id] = i

    def __getitem__(self, i: str | int) -> LayerConfig:  # type: ignore[override]
        """Retrieve a layer by index or ID.

        Args:
            i: Either an integer index or string identifier.
                String identifiers are matched against layer IDs first,
                then attempted as numeric strings.

        Returns:
            The matching LayerConfig, or NoneConfigLayer sentinel if not found.

        Example:
            >>> layers[0]  # By index
            LayerConfig(...)
            >>> layers["_SYM"]  # By ID
            LayerConfig(...)
        """
        if isinstance(i, str):
            idx = self._index_map.get(i)
            if idx is not None and 0 <= idx < len(self.data):
                return super().__getitem__(idx)
            try:
                int_idx = int(i)
                if 0 <= int_idx < len(self.data):
                    return super().__getitem__(int_idx)
            except ValueError:
                pass
            return NoneConfigLayer
        return super().__getitem__(i)

    def append(self, item: LayerConfig) -> None:
        """Add a layer to the list, automatically assigning its index.

        Args:
            item: LayerConfig to append. Its index will be set to the
                current list length, and its ID (if present) will be
                registered for lookup.
        """
        item.index = len(self.data)
        if item.id:
            self._index_map[item.id] = item.index
        super().append(item)


@dataclass
class SkimConfig:
    """Root configuration for the Skim keymap image generator.

    Contains all settings needed to generate keymap images, including
    layer definitions, appearance settings, and keycode customizations.

    Attributes:
        layers: List of layer configurations defining colors and names.
        appearance: Visual styling for borders and colors.
        keycodes: Optional dict mapping QMK keycodes to custom display labels.
        layer_keycode: Optional dict for custom layer-switching key behavior.
        reversed_alias: Optional dict mapping keycode functions to aliases
            (e.g., "LSFT(KC_1)" -> "KC_EXLM").

    Example:
        Loading and merging with defaults::

            user_config = SkimConfig.from_dict(
                {
                    "layers": [
                        {"base_color": "#FF0000", "name": "Base"},
                        {"base_color": "#00FF00", "name": "Nav"},
                    ],
                }
            )
            config = user_config.merge_with_defaults()
    """

    layers: LayerConfigList
    appearance: AppearanceConfig | None = None
    keycodes: dict[str, str] | None = None
    layer_keycode: dict[str, Any] | None = None
    reversed_alias: dict[str, str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkimConfig:
        """Create a SkimConfig from a dictionary (typically from YAML).

        Parses nested configuration structures and constructs the
        appropriate dataclass hierarchy.

        Args:
            data: Dictionary with configuration data. Expected keys:
                - layers: List of layer config dicts
                - appearance: Optional appearance settings dict
                - keycodes: Optional keycode override dict
                - layer_keycode: Optional layer keycode mappings
                - reversed_alias: Optional alias mappings

        Returns:
            Populated SkimConfig instance.

        Example:
            >>> data = yaml.safe_load(open("config.yaml"))
            >>> config = SkimConfig.from_dict(data)
        """
        layers = LayerConfigList()
        for layer_data in data.get("layers", []):
            layers.append(LayerConfig(**layer_data))

        appearance = None
        if "appearance" in data:
            app_data = data["appearance"]
            border = BorderConfig(**app_data.get("border", {}))
            colors_data = app_data.get("colors", {}).copy()
            if "named_colors" in app_data:
                colors_data["named_colors"] = app_data["named_colors"]
            colors = ColorConfig(**colors_data)
            appearance = AppearanceConfig(border=border, colors=colors)

        return cls(
            layers=layers,
            appearance=appearance,
            keycodes=data.get("keycodes"),
            layer_keycode=data.get("layer_keycode"),
            reversed_alias=data.get("reversed_alias"),
        )

    @classmethod
    def load_default(cls) -> SkimConfig:
        """Load the bundled default configuration.

        Returns:
            SkimConfig with default settings from the bundled
            default-config.yaml asset file.

        Raises:
            FileNotFoundError: If the default config file is missing.
        """
        default_config_path = (
            Path(__file__).parent.parent / "assets" / "data" / "default-config.yaml"
        )
        with open(default_config_path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    def merge_with_defaults(self) -> SkimConfig:
        """Merge this configuration with default values.

        Creates a new SkimConfig where any unset (None) values are
        filled in from the default configuration. User-provided values
        take precedence over defaults.

        Returns:
            New SkimConfig with defaults applied to missing values.

        Example:
            >>> partial = SkimConfig.from_dict({"layers": [...]})
            >>> full = partial.merge_with_defaults()
            >>> full.appearance is not None
            True
        """
        default = SkimConfig.load_default()

        return SkimConfig(
            layers=self.layers if self.layers else default.layers,
            appearance=self.appearance if self.appearance else default.appearance,
            keycodes=self.keycodes if self.keycodes else default.keycodes,
            layer_keycode=self.layer_keycode
            if self.layer_keycode
            else default.layer_keycode,
            reversed_alias=self.reversed_alias
            if self.reversed_alias
            else default.reversed_alias,
        )
