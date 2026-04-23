# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Configuration models for Svalboard Keymap Image Maker tool.

This module defines the Pydantic configuration models used to customize
the appearance and behavior of generated keymap images. The configuration
is hierarchical, with the root :class:`SkimConfig` containing nested models
for keyboard settings, keycode mappings, and output styling.

Configuration can be loaded from YAML files or constructed programmatically.
All models use Pydantic's BaseModel for validation and serialization.

Example:
    Loading configuration from a YAML file::

        import yaml
        from skim.data.config import SkimConfig

        with open("skim-config.yaml") as f:
            data = yaml.safe_load(f)
        config = SkimConfig(**data)

    Creating configuration programmatically::

        from skim.data.config import SkimConfig, LayerColor, Palette

        config = SkimConfig()
        new_layers = config.output.style.palette.layers + (LayerColor(base_color="#FF0000"),)
        new_palette = config.output.style.palette.model_copy(update={"layers": new_layers})
        new_style = config.output.style.model_copy(update={"palette": new_palette})
        new_output = config.output.model_copy(update={"style": new_style})
        config = config.model_copy(update={"output": new_output})

Attributes:
    SplitSidePositionStr: Annotated type alias for SplitSidePosition that
        accepts string values and converts them to enum members.
"""

from collections.abc import Sequence
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PrivateAttr


def _coerce_to_tuple(v: Any) -> Any:
    if isinstance(v, tuple):
        return v
    if isinstance(v, Sequence) and not isinstance(v, str):
        return tuple(v)
    return v


class KeyboardLayer(BaseModel):
    """Configuration for a single keyboard layer.

    Defines the metadata associated with a layer in the keymap, including
    its display label and internal name. This is used to customize how
    layers are labeled in generated images.

    Attributes:
        id: Optional unique identifier for the layer. Used for internal
            reference when processing a keymap from `c2json` that uses C
            define-macros instead of layer numbers in with the layer switch
            functions. It may be None if not specified.
        label: Short display label shown in the generated image (e.g., "1",
            "Sym", "Nav"). Should be brief for visual clarity.
        name: Full descriptive name of the layer (e.g., "Base Layer",
            "Symbols", "Navigation"). Used as the "image title" on the
            generated images.
        variant: Optional secondary label shown below the layer name
            (e.g., "COLEMAK"). Used to display additional layer metadata
            in the overview image. Defaults to None if not specified.

    Example:
        >>> layer = KeyboardLayer(label="1", name="Base Layer")
        >>> layer.label
        '1'
        >>> layer.name
        'Base Layer'
        >>> layer.variant is None
        True
    """

    model_config = ConfigDict(frozen=True)

    index: int
    id: str | None = None
    label: str
    name: str
    variant: str | None = None


class KeyboardFeatures(BaseModel):
    """Configuration for optional keyboard hardware features.

    Controls which optional hardware features are enabled when generating
    keymap images. These settings affect which keys are rendered.

    Attributes:
        double_south: Whether to render the MH (double-south) keys on finger
            clusters. When False, these positions are hidden. Defaults to
            False as not all Svalboard configurations have these keys.

    Example:
        >>> features = KeyboardFeatures(double_south=True)
        >>> features.double_south
        True

    Note:
        Currently the Svalboard keyboard only have a single feature modifier
        that can impact a keymap image, but this configuration object is here
        to future-proof this tool on eventual changes.
    """

    model_config = ConfigDict(frozen=True)

    double_south: bool = False


class Keyboard(BaseModel):
    """Keyboard-specific configuration settings.

    Contains settings that describe the physical keyboard configuration
    and layer definitions. This is used to customize the rendering based
    on the specific keyboard setup.

    Attributes:
        features: Hardware feature flags controlling the keymap rendering.
            Defaults to a KeyboardFeatures instance with all features disabled.
        layers: Tuple of layer configurations defining the metadata for
            each layer in the keymap. The order corresponds to layer
            indices (0, 1, 2, etc.).

    Example:
        >>> keyboard = Keyboard(
        ...     features=KeyboardFeatures(double_south=True),
        ...     layers=(
        ...         KeyboardLayer(label="1", name="Base"),
        ...         KeyboardLayer(label="2", name="Symbols"),
        ...     ),
        ... )
        >>> len(keyboard.layers)
        2
    """

    model_config = ConfigDict(frozen=True)

    features: KeyboardFeatures = Field(default_factory=KeyboardFeatures)
    layers: Annotated[tuple[KeyboardLayer, ...], BeforeValidator(_coerce_to_tuple)] = ()
    _layer_id_map: dict[str, int] = PrivateAttr(default_factory=dict)
    _qmk_index_map: dict[int, int] = PrivateAttr(default_factory=dict)

    def model_post_init(self, context: object) -> None:
        """Initialize the layer ID lookup map after model construction.

        Builds an internal mapping from layer identifiers to their QMK
        firmware indices for efficient layer lookup. If a layer has an
        explicit ``id``, that ID is used as the key. Otherwise, the string
        representation of the layer's position index is used.

        This method is called automatically by Pydantic after the model is
        constructed.

        Args:
            context: Pydantic validation context (unused but required by
                the Pydantic post-init signature).

        Example:
            >>> keyboard = Keyboard(
            ...     layers=[
            ...         KeyboardLayer(index=0, id="base", label="1", name="Base"),
            ...         KeyboardLayer(index=15, label="2", name="Symbols"),
            ...     ]
            ... )
            >>> keyboard.layer_index("base")
            0
            >>> keyboard.layer_index("1")  # Second layer has no id, uses QMK index
            15
        """
        for idx, layer in enumerate(self.layers):
            if layer.id is not None:
                self._layer_id_map[layer.id] = layer.index
            else:
                self._layer_id_map[str(idx)] = layer.index
            self._qmk_index_map[layer.index] = idx

    def layer_index(self, key: str | None) -> int | None:
        """Look up a layer's QMK firmware index by its identifier.

        Returns the QMK firmware index of the layer matching the given key.
        The key can be either a layer's explicit ``id``, the string
        representation of its position index (for layers without an id),
        or an integer index which is converted to string for lookup.

        Args:
            key: The layer identifier to look up. This can be a layer's
                ``id`` attribute, a string index like ``"0"``, ``"1"``,
                or an integer index like ``0``, ``1``. If ``None``, returns
                ``None``.

        Returns:
            The QMK firmware index of the matching layer, or ``None`` if no
            layer matches the given key or if key is ``None``.

        Example:
            >>> keyboard = Keyboard(
            ...     layers=[
            ...         KeyboardLayer(index=0, id="nav", label="N", name="Navigation"),
            ...         KeyboardLayer(index=15, label="S", name="Symbols"),
            ...     ]
            ... )
            >>> keyboard.layer_index("nav")
            0
            >>> keyboard.layer_index("1")
            15
            >>> keyboard.layer_index("unknown") is None
            True
        """
        if key is None:
            return None
        return self._layer_id_map.get(key)

    def qmk_index_to_position(self, qmk_idx: int) -> int | None:
        """Look up a layer's position by its QMK firmware index.

        Returns the zero-based position of the layer in the layers tuple
        that has the given QMK firmware index. This is useful when layer
        indices in the firmware are non-sequential (e.g., 0, 1, 2, 15).

        Args:
            qmk_idx: The QMK firmware layer index to look up.

        Returns:
            The position of the matching layer in the layers tuple, or
            ``None`` if no layer has the given QMK index.

        Example:
            >>> keyboard = Keyboard(
            ...     layers=[
            ...         KeyboardLayer(index=0, label="1", name="Base"),
            ...         KeyboardLayer(index=15, label="M", name="Mouse"),
            ...     ]
            ... )
            >>> keyboard.qmk_index_to_position(15)
            1
            >>> keyboard.qmk_index_to_position(5) is None
            True
        """
        return self._qmk_index_map.get(qmk_idx)

    def layer_qmk_index(self, position: int) -> int:
        """Get the QMK firmware index for a layer at a given position.

        Returns the QMK firmware layer index for the layer at the given
        position in the layers tuple.

        Args:
            position: The zero-based position of the layer in the layers tuple.

        Returns:
            The QMK firmware layer index.

        Example:
            >>> keyboard = Keyboard(
            ...     layers=[
            ...         KeyboardLayer(index=0, label="1", name="Base"),
            ...         KeyboardLayer(index=15, label="M", name="Mouse"),
            ...     ]
            ... )
            >>> keyboard.layer_qmk_index(1)
            15
        """
        return self.layers[position].index


class Keycode(BaseModel):
    """A keycode-to-label mapping override.

    Defines a custom mapping from a QMK keycode string to a display label.
    This is used to customize how specific keycodes are rendered, either
    by preprocessing them before the standard mapping or by overriding
    the default label entirely.

    Attributes:
        keycode: The QMK keycode string to match (e.g., "KC_A", "KC_ESC").
            Must match exactly, including case.
        target: The replacement label or transformed keycode. For
            pre-processing, this is typically another keycode. For
            overrides, this is the display label.

    Example:
        >>> # Override KC_SPC to display as "Space"
        >>> override = Keycode(keycode="KC_SPC", target="Space")
        >>> override.keycode
        'KC_SPC'
    """

    model_config = ConfigDict(frozen=True)

    keycode: str
    target: str

    def __hash__(self) -> int:
        return hash((self.keycode, self.target))


class Keycodes(BaseModel):
    """Configuration for keycode transformation and display.

    Contains tuples of keycode mappings that customize how QMK keycodes
    are transformed and displayed. The pre-processing transformation happens
    without any processing by the tool. This mapping should not use the alias
    and other replacements features from key resolution. Then, the standard
    label mapping happens with the overrides defined in this configuration
    having higher priority than the default transformations.

    Attributes:
        pre_process: Keycode transformations applied before standard
            mapping. Useful for normalizing keycodes or representing custom
            keycodes that act like othes QMK keycodes including functions.
            Defaults to an empty tuple.
        overrides: Keycode-to-label mappings that override the standard
            mapping results. Applied after all other transformations.
            Defaults to an empty tuple.

    Example:
        >>> keycodes = Keycodes(
        ...     pre_process=(Keycode(keycode="LCTL_T(KC_A)", target="MT(MOD_LCTL,KC_A)"),),
        ...     overrides=(Keycode(keycode="KC_SPC", target="Space"),),
        ... )
        >>> len(keycodes.overrides)
        1
    """

    model_config = ConfigDict(frozen=True)

    pre_process: Annotated[tuple[Keycode, ...], BeforeValidator(_coerce_to_tuple)] = ()
    overrides: Annotated[tuple[Keycode, ...], BeforeValidator(_coerce_to_tuple)] = ()

    def __hash__(self) -> int:
        return hash((self.pre_process, self.overrides))


class Spacing(BaseModel):
    """Spacing configuration for layout margins and inset (padding and
    in-between elements spacing).

    Controls the whitespace around and within the generated keymap images.
    Spacing is specified in SVG units (typically pixels at default scale).

    Attributes:
        margin: Outer margin around the entire keyboard layout. Space
            between the keyboard and the image edge. Defaults to 0.
        inset: Inner padding within the keyboard border. Space between
            the border and the key clusters. Defaults to 20.

    Example:
        >>> spacing = Spacing(margin=10, inset=25)
        >>> spacing.margin
        10
    """

    model_config = ConfigDict(frozen=True)

    margin: float = 0
    inset: float = 20


class Layout(BaseModel):
    """Layout dimensions and spacing configuration.

    Controls the overall dimensions and spacing of generated keymap images.
    The height is calculated automatically based on the width to maintain
    the correct aspect ratio for the Svalboard layout.

    Attributes:
        width: Total width of the generated image in SVG units (typically
            pixels at default scale). Defaults to 800.
        spacing: Spacing configuration for margins and padding. Defaults
            to a Spacing instance with default values.

    Example:
        >>> layout = Layout(width=1200, spacing=Spacing(margin=20))
        >>> layout.width
        1200
    """

    model_config = ConfigDict(frozen=True)

    width: float = 800
    spacing: Spacing = Field(default_factory=Spacing)


class Border(BaseModel):
    """Border styling configuration.

    Controls the appearance of borders drawn around the keyboard layout
    and optionally around individual key groups.

    Attributes:
        width: Line width of the border in SVG units. Defaults to 2.
        radius: Corner radius for rounded borders in SVG units. Set to 0
            for square corners. Defaults to 10.

    Example:
        >>> border = Border(width=3, radius=15)
        >>> border.radius
        15.0
    """

    model_config = ConfigDict(frozen=True)

    width: float = 2
    radius: float = 10


class LayerColor(BaseModel):
    """Color configuration for a keyboard layer.

    Defines the color scheme used for keys on a specific layer. Supports
    both single-color and gradient modes. In gradient mode, different
    keys within a cluster can have different shades for visual depth.

    The gradient tuple contains 6 colors corresponding to the 6 positions
    in a cluster (e.g., center, north, east, south, west, double-south
    for finger clusters).

    Attributes:
        base_color: The primary color for this layer as a CSS color string
            (e.g., "#FF0000", "red", "rgb(255,0,0)"). Used when gradient
            is None or as a fallback.
        color_index: Index into the gradient for the primary key color.
            Only used when gradient is set. Defaults to 2.
        gradient: Optional tuple of 6 CSS color strings for position-based
            coloring within clusters. When None, the tool will generate the
            gradient tuple based on the base_color and the index position it
            should be in.

    Example:
        >>> # Single color mode
        >>> layer = LayerColor(base_color="#FF0000")
        >>> layer[0]
        '#FF0000'

        >>> # Gradient mode
        >>> layer = LayerColor(
        ...     base_color="#FF0000",
        ...     gradient=("#FF0000", "#CC0000", "#990000", "#660000", "#330000", "#000000"),
        ... )
        >>> layer[1]
        '#CC0000'
    """

    model_config = ConfigDict(frozen=True)

    base_color: str
    color_index: int = 2
    gradient: tuple[str, str, str, str, str, str] | None = None

    def __getitem__(self, index: int) -> str:
        """Get the color for a specific cluster position.

        Args:
            index: Position index from 0-5 corresponding to cluster
                key positions.

        Returns:
            The CSS color string for the specified position. Returns
            base_color if gradient is not set.

        Raises:
            IndexError: If index is outside the valid range (0-5).

        Example:
            >>> layer = LayerColor(base_color="#FFF")
            >>> layer[0]
            '#FFF'
        """
        if not 0 <= index < 6:
            raise IndexError(f"Gradient index {index} out of range (0-5)")
        if not self.gradient:
            return self.base_color
        return self.gradient[index]

    def __str__(self) -> str:
        """Return a string representation of the color configuration.

        Returns:
            A JSON-like array string of the colors. For single-color
            mode, returns a single-element array. For gradient mode,
            returns all 6 colors.

        Example:
            >>> str(LayerColor(base_color="#FFF"))
            '["#FFF"]'
        """
        str_colors = (
            (f'"{self.base_color}"',) if not self.gradient else (f'"{x}"' for x in self.gradient)
        )
        return f"[{', '.join(str_colors)}]"

    @property
    def dark_accent_color(self) -> str:
        """Get the darker accent color for this layer.

        Returns the second color in the gradient (index 1) if a gradient
        is defined, otherwise returns the base_color. This is typically
        used for key borders, shadows, or accent elements.

        Returns:
            A CSS color string for the accent color.

        Example:
            >>> layer = LayerColor(
            ...     base_color="#FF0000",
            ...     gradient=("#FF0000", "#AA0000", "#880000", "#660000", "#440000", "#220000"),
            ... )
            >>> layer.dark_accent_color
            '#AA0000'
        """
        return self.base_color if not self.gradient else self.gradient[1]


class Palette(BaseModel):
    """Color palette configuration for the entire keyboard.

    Defines the color scheme used throughout the generated keymap images,
    including background colors, text colors, and per-layer key colors.

    Attributes:
        overrides: Dictionary mapping color names to colors values.
            Used to change the color defined by W3C on the 147 supported named
            colors on SVG files. Defaults to an empty dictionary so the
            standard definitions should be used.
        neutral_color: Color for keys that don't have layer-specific
            coloring (e.g., some thumb cluster keys). Defaults to "#6F768B"
            (gray).
        text_color: Default text color for non key labels. Defaults to "black".
        key_label_color: Text color for key labels. Defaults to "white"
            for contrast against typically dark key backgrounds.
        background_color: Background color for the entire image.
            Defaults to "white".
        border_color: Color for keyboard and cluster borders.
            Defaults to "black".
        layers: Tuple of LayerColor configurations, one per layer.
            Layer indices correspond to positions in this tuple.
            Defaults to an empty tuple.

    Example:
        >>> palette = Palette(
        ...     background_color="#F0F0F0",
        ...     layers=(
        ...         LayerColor(base_color="#3366CC"),
        ...         LayerColor(base_color="#CC6633"),
        ...     ),
        ... )
        >>> palette.background_color
        '#F0F0F0'
    """

    model_config = ConfigDict(frozen=True)

    overrides: dict[str, str] = Field(default_factory=dict)
    neutral_color: str = "#6F768B"
    text_color: str = "black"
    key_label_color: str = "white"
    background_color: str = "white"
    border_color: str = "black"
    layers: Annotated[tuple[LayerColor, ...], BeforeValidator(_coerce_to_tuple)] = ()


class SplitSidePosition(str, Enum):
    """Position options for hold-tap key symbol placement.

    Controls where the "hold" portion of a hold-tap key is displayed
    relative to the "tap" portion. This affects keys like LT(1, KC_A)
    where tapping produces "A" but holding activates layer 1.

    Attributes:
        QMK_DEFINED: Use the position defined in QMK firmware settings.
            This respects the argument order of the macro-functions defined by
            QMK, which is always the hold part as the first argument, and the
            tap part as the second.
        INWARD: Place the hold symbol toward the center of the keyboard cluster
            (right on left side, left on right side).
        OUTWARD: Place the hold symbol toward the outside of the keyboard
            cluster (left on left side, right on right side). This is the
            default.
    """

    QMK_DEFINED = "qmk"
    INWARD = "inward"
    OUTWARD = "outward"


SplitSidePositionStr = Annotated[SplitSidePosition, BeforeValidator(SplitSidePosition)]
"""Annotated type for SplitSidePosition that accepts string inputs.

This type alias allows configuration files to specify hold symbol positions
as plain strings (e.g., "inward", "outward") which are automatically
converted to SplitSidePosition enum members during validation.

Example:
    In a YAML configuration file::

        style:
          hold_symbol_position: outward

    When parsed, "outward" is converted to SplitSidePosition.OUTWARD.
"""


class Style(BaseModel):
    """Visual styling configuration for keymap images.

    Controls the overall visual appearance of generated images, including
    colors, borders, and key labeling options.

    Attributes:
        use_layer_colors_on_keys: Whether to color keys backgrounds based on
            the layer it activates. When True, keys use colors from the
            palette's layer list. When False, all keys use their standard
            colors. Defaults to True.
        hold_symbol_position: Where to place the "hold" portion of
            hold-tap keys relative to the "tap" portion. See
            :class:`SplitSidePosition` for options. Defaults to OUTWARD.
        border: Border styling configuration, or None to disable borders.
            Defaults to a Border instance with default values.
        palette: Color palette configuration for the entire keyboard.
            Defaults to a Palette instance with default values.

    Example:
        >>> style = Style(
        ...     use_layer_colors_on_keys=True,
        ...     hold_symbol_position=SplitSidePosition.INWARD,
        ... )
        >>> style.hold_symbol_position
        <SplitSidePosition.INWARD: 'inward'>
    """

    model_config = ConfigDict(frozen=True)

    use_layer_colors_on_keys: bool = True
    hold_symbol_position: SplitSidePositionStr = Field(default=SplitSidePosition.OUTWARD)
    border: Border | None = Field(default_factory=Border)
    palette: Palette = Field(default_factory=Palette)
    use_system_fonts: bool = False
    show_layer_indicators: bool = True
    show_layer_connectors: bool = True


class Output(BaseModel):
    """Output configuration for generated images.

    Groups together layout dimensions and visual styling settings
    that control the final appearance of generated keymap images.

    Attributes:
        layout: Layout dimensions and spacing configuration.
            Defaults to a Layout instance with default values.
        style: Visual styling configuration. Defaults to a Style
            instance with default values.
        keymap_title: Optional title for the overview keymap image.
            When set, overrides the auto-generated title. Defaults to None.
        copyright: Optional copyright notice displayed in the overview
            image. Defaults to None.

    Example:
        >>> output = Output(
        ...     layout=Layout(width=1000),
        ...     style=Style(use_layer_colors_on_keys=False),
        ... )
        >>> output.layout.width
        1000
    """

    model_config = ConfigDict(frozen=True)

    layout: Layout = Field(default_factory=Layout)
    style: Style = Field(default_factory=Style)
    keymap_title: str | None = None
    copyright: str | None = None


class SkimConfig(BaseModel):
    """Root configuration model for skim keymap image generation.

    This is the top-level configuration class that contains all settings
    for generating Svalboard keymap images. It can be loaded from YAML
    files or constructed programmatically.

    The configuration is organized into three main sections:
    - **keyboard**: Hardware and layer settings
    - **keycodes**: Keycode transformation and display rules
    - **output**: Layout dimensions and visual styling

    Attributes:
        keyboard: Keyboard-specific configuration including hardware
            features and layer definitions. Defaults to a Keyboard
            instance with default values.
        keycodes: Keycode transformation rules including pre-processing
            and overrides. Defaults to a Keycodes instance with empty
            rule tuples.
        output: Output configuration including layout dimensions and
            visual styling. Defaults to an Output instance with default
            values.

    Example:
        Creating a basic configuration::

            config = SkimConfig()
            new_layout = config.output.layout.model_copy(update={"width": 1200})
            new_output = config.output.model_copy(update={"layout": new_layout})
            config = config.model_copy(update={"output": new_output})

        Loading from a dictionary (e.g., parsed YAML)::

            data = {
                "keyboard": {
                    "features": {"double_south": True},
                    "layers": [{"label": "1", "name": "Base"}],
                },
                "output": {"layout": {"width": 1000}},
            }
            config = SkimConfig(**data)
    """

    model_config = ConfigDict(frozen=True)

    keyboard: Keyboard = Field(default_factory=Keyboard)
    keycodes: Keycodes = Field(default_factory=Keycodes)
    output: Output = Field(default_factory=Output)
