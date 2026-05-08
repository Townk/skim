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
    Loading configuration from a YAML file:

    ```python
    import yaml
    from skim.data.config import SkimConfig

    with open("skim-config.yaml") as f:
        data = yaml.safe_load(f)
    config = SkimConfig(**data)
    ```

    Creating configuration programmatically:

    ```python
    from skim.data.config import SkimConfig, LayerColor, Palette

    config = SkimConfig()
    new_layers = config.output.style.palette.layers + (LayerColor(base_color="#FF0000"),)
    new_palette = config.output.style.palette.model_copy(update={"layers": new_layers})
    new_style = config.output.style.model_copy(update={"palette": new_palette})
    new_output = config.output.model_copy(update={"style": new_style})
    config = config.model_copy(update={"output": new_output})
    ```

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
    its internal name. This is used to customize how layers are named in
    generated images.

    Attributes:
        id: Optional unique identifier for the layer. Used for internal
            reference when processing a keymap from `c2json` that uses C
            define-macros instead of layer numbers in with the layer switch
            functions. It may be None if not specified.
        name: Full descriptive name of the layer (e.g., "Base Layer",
            "Symbols", "Navigation"). Used as the "image title" on the
            generated images.
        variant: Optional secondary label shown below the layer name
            (e.g., "COLEMAK"). Used to display additional layer metadata
            in the overview image. Defaults to None if not specified.

    Example:
        ```pycon
        >>> layer = KeyboardLayer(index=0, name="Base Layer")
        >>> layer.name
        'Base Layer'
        >>> layer.variant is None
        True

        ```
    """

    model_config = ConfigDict(frozen=True)

    index: int
    id: str | None = None
    name: str
    variant: str | None = None


class KeyboardFeatures(BaseModel):
    """Configuration for optional keyboard hardware features.

    Controls which optional hardware features are enabled when generating
    keymap images. These settings affect which keys are rendered.

    Attributes:
        double_south: Whether to render the DS (double-south) keys on finger
            clusters. When False, these positions are hidden. Defaults to
            False as not all Svalboard configurations have these keys.

    Example:
        ```pycon
        >>> features = KeyboardFeatures(double_south=True)
        >>> features.double_south
        True

        ```

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
        ```pycon
        >>> keyboard = Keyboard(
        ...     features=KeyboardFeatures(double_south=True),
        ...     layers=(
        ...         KeyboardLayer(index=0, name="Base"),
        ...         KeyboardLayer(index=1, name="Symbols"),
        ...     ),
        ... )
        >>> len(keyboard.layers)
        2

        ```
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
            ```pycon
            >>> keyboard = Keyboard(
            ...     layers=[
            ...         KeyboardLayer(index=0, id="base", name="Base"),
            ...         KeyboardLayer(index=15, name="Symbols"),
            ...     ]
            ... )
            >>> keyboard.layer_index("base")
            0
            >>> keyboard.layer_index("1")  # Second layer has no id, uses QMK index
            15

            ```
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
            ```pycon
            >>> keyboard = Keyboard(
            ...     layers=[
            ...         KeyboardLayer(index=0, id="nav", name="Navigation"),
            ...         KeyboardLayer(index=15, name="Symbols"),
            ...     ]
            ... )
            >>> keyboard.layer_index("nav")
            0
            >>> keyboard.layer_index("1")
            15
            >>> keyboard.layer_index("unknown") is None
            True

            ```
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
            ```pycon
            >>> keyboard = Keyboard(
            ...     layers=[
            ...         KeyboardLayer(index=0, name="Base"),
            ...         KeyboardLayer(index=15, name="Mouse"),
            ...     ]
            ... )
            >>> keyboard.qmk_index_to_position(15)
            1
            >>> keyboard.qmk_index_to_position(5) is None
            True

            ```
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
            ```pycon
            >>> keyboard = Keyboard(
            ...     layers=[
            ...         KeyboardLayer(index=0, name="Base"),
            ...         KeyboardLayer(index=15, name="Mouse"),
            ...     ]
            ... )
            >>> keyboard.layer_qmk_index(1)
            15

            ```
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
        ```pycon
        >>> # Override KC_SPC to display as "Space"
        >>> override = Keycode(keycode="KC_SPC", target="Space")
        >>> override.keycode
        'KC_SPC'

        ```
    """

    model_config = ConfigDict(frozen=True)

    keycode: str
    target: str

    def __hash__(self) -> int:
        return hash((self.keycode, self.target))


class Macro(BaseModel):
    """A macro reference with an optional human-readable name and preview.

    Attributes:
        id: String id matching how the keycode references this macro
            (``"0"`` for ``MACRO_0``, ``"MY_MACRO"`` for ``MACRO_MY_MACRO``).
        name: Optional human-readable name surfaced by the renderer.
        preview: Single-line display summary, generated at bootstrap time
            or set to ``"Undefined"`` for manually-added entries. Read-only
            in the TUI.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str | None = None
    preview: str = ""

    def __hash__(self) -> int:
        return hash((self.id, self.name, self.preview))


class TapDance(BaseModel):
    """A tap-dance reference with an optional human-readable name and preview.

    Attributes:
        id: String id matching how the keycode references this tap dance
            (``"0"`` for ``TD(0)``, ``"MY_TD"`` for ``TD(MY_TD)``).
        name: Optional human-readable name surfaced by the renderer.
        preview: Single-line display summary, generated at bootstrap time
            or set to ``"Undefined"`` for manually-added entries. Read-only
            in the TUI.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str | None = None
    preview: str = ""

    def __hash__(self) -> int:
        return hash((self.id, self.name, self.preview))


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
        macros: Macro references with optional names and previews.
            Defaults to an empty tuple.
        tap_dances: Tap-dance references with optional names and previews.
            Defaults to an empty tuple.
        symbol_descriptions: User overrides for the bundled symbol
            description table, structured as ``{category: {keycode:
            description}}``. User keys in an existing bundled category take
            precedence; new categories are appended after the bundled ones.
            Defaults to an empty dict (no overrides).

            Example:

            ```yaml
            symbol_descriptions:
              Modifiers:
                KC_LEFT_CTRL: "Control (my label)"
              "My Section":
                MY_KEY: "Does the thing"
            ```

        function_descriptions: User overrides for the bundled function
            description table, same shape as ``symbol_descriptions``.
            Defaults to an empty dict (no overrides).

            Example:

            ```yaml
            function_descriptions:
              Layers:
                MO: "Custom MO description with @0;"
            ```

        symbol_legend_aliases: Shallow-merge overrides for the bundled
            ``symbol_legend_aliases`` map.  Each entry maps a keycode to
            the canonical keycode whose legend entry it should share.
            Defaults to an empty dict (no overrides).

            Example:

            ```yaml
            symbol_legend_aliases:
              KC_RIGHT_GUI: KC_LEFT_GUI
            ```

    Example:
        ```pycon
        >>> keycodes = Keycodes(
        ...     pre_process=(Keycode(keycode="LCTL_T(KC_A)", target="MT(MOD_LCTL,KC_A)"),),
        ...     overrides=(Keycode(keycode="KC_SPC", target="Space"),),
        ... )
        >>> len(keycodes.overrides)
        1

        ```
    """

    model_config = ConfigDict(frozen=True)

    pre_process: Annotated[tuple[Keycode, ...], BeforeValidator(_coerce_to_tuple)] = ()
    overrides: Annotated[tuple[Keycode, ...], BeforeValidator(_coerce_to_tuple)] = ()
    macros: Annotated[tuple[Macro, ...], BeforeValidator(_coerce_to_tuple)] = ()
    tap_dances: Annotated[tuple[TapDance, ...], BeforeValidator(_coerce_to_tuple)] = ()
    symbol_descriptions: dict[str, dict[str, str]] = Field(default_factory=dict)
    function_descriptions: dict[str, dict[str, str]] = Field(default_factory=dict)
    symbol_legend_aliases: dict[str, str] = Field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(
            (
                self.pre_process,
                self.overrides,
                self.macros,
                self.tap_dances,
                tuple(
                    (cat, tuple(sorted(items.items())))
                    for cat, items in sorted(self.symbol_descriptions.items())
                ),
                tuple(
                    (cat, tuple(sorted(items.items())))
                    for cat, items in sorted(self.function_descriptions.items())
                ),
                tuple(sorted(self.symbol_legend_aliases.items())),
            )
        )


def _parse_spacing(value: Any) -> float | None:
    """Normalize a Spacing field input to a float (or None).

    Accepted input forms:

    - ``None`` — keep the field's default (renderer falls back to its
      built-in proportion).
    - ``int`` / ``float`` — passed through as-is.
    - ``"N%"`` string — converted to ``N / 100.0`` (proportion form).
    - Plain numeric string (``"42"``, ``"0.05"``) — parsed as float.

    The renderer applies the **magnitude rule** to the resulting float:

    - ``x < 1.0`` → proportion of the field's documented base.
    - ``x >= 1.0`` → absolute SVG units (independent of doc width).

    Bools are rejected explicitly; without this they'd silently coerce
    to ``0.0`` / ``1.0`` because ``bool`` is a subclass of ``int``.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(f"Spacing value cannot be a bool, got {value!r}")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if s.endswith("%"):
            try:
                return float(s[:-1]) / 100.0
            except ValueError as exc:
                raise ValueError(f"Invalid percentage spacing: {value!r}") from exc
        try:
            return float(s)
        except ValueError as exc:
            raise ValueError(f"Invalid spacing value: {value!r}") from exc
    raise TypeError(f"Spacing must be a float, int, or string; got {type(value).__name__}")


SpacingValue = Annotated[float | None, BeforeValidator(_parse_spacing)]
"""A spacing field accepting None, float, int, or a ``'N%'`` string.

After validation the value is always ``float | None``; the renderer
interprets the float's magnitude (``< 1.0`` proportion, ``>= 1.0``
absolute units).
"""


def resolve_spacing(value: float | None, *, base: float, default_proportion: float) -> float:
    """Resolve a :data:`SpacingValue` to absolute SVG units.

    Implements the magnitude rule:

    - ``None`` → ``base * default_proportion`` (renderer's built-in).
    - ``value < 1.0`` → ``base * value`` (proportion of base).
    - ``value >= 1.0`` → ``value`` (absolute SVG units).

    The ``1.0`` boundary is conventional: proportions live in
    ``[0, 1)``, and any meaningful spacing in this codebase is at
    least 1 SVG unit (sub-pixel gaps are invisible anyway).

    Example:
        ```pycon
        >>> resolve_spacing(None, base=1600.0, default_proportion=0.025)
        40.0
        >>> resolve_spacing(0.05, base=1600.0, default_proportion=0.025)
        80.0
        >>> resolve_spacing(20, base=1600.0, default_proportion=0.025)
        20.0

        ```
    """
    if value is None:
        return base * default_proportion
    if value < 1.0:
        return max(0.0, base * value)
    return value


class Spacing(BaseModel):
    """Configurable spacing values for the document layout.

    Every gap, padding, and inset the renderer applies has a built-in
    proportional default. Override any of them here. Each field accepts:

    - **Float < 1.0** — proportion of the field's base.
    - **Float ≥ 1.0** — absolute SVG units (independent of doc width).
    - **String ``"N%"``** — shorthand for ``N / 100.0`` (proportion form).
    - **``None`` (default)** — the field's built-in default proportion.

    Each field documents its **base**. Most scale to the document width
    (``output.layout.width``); the two cluster geometry fields scale to
    the cluster's own width so they stay proportional regardless of how
    the keyboard is positioned in the canvas.

    Example:
        ```pycon
        >>> spacing = Spacing(margin=20, inset="3%", chip_padding=12)
        >>> spacing.margin
        20.0
        >>> spacing.inset
        0.03
        >>> spacing.chip_padding
        12.0

        ```
    """

    model_config = ConfigDict(frozen=True)

    # ------------------------------------------------------------------
    # Document chrome — base: ``output.layout.width``
    # ------------------------------------------------------------------

    margin: SpacingValue = Field(default=None)
    """Canvas edge → outer border line. Default: ``0`` (flush)."""

    inset: SpacingValue = Field(default=None)
    """Border line → content. Also the inter-element gap inside the
    document Column. Default: ``40/1600`` (2.5%) of doc width."""

    column_gap: SpacingValue = Field(default=None)
    """Horizontal gap between half-keyboards (and between side-by-side
    sections). Default: ``40/1600`` (2.5%) of doc width."""

    # ------------------------------------------------------------------
    # Section / table rhythm — base: ``output.layout.width``
    # ------------------------------------------------------------------

    section_spacing: SpacingValue = Field(default=None)
    """Section title stripe → section body. Default:
    ``24/1600`` (1.5%) of doc width."""

    section_title_rule_gap: SpacingValue = Field(default=None)
    """Section title bottom → rule line below it. Default:
    ``9/1600`` (~0.56%) of doc width."""

    table_header_spacing: SpacingValue = Field(default=None)
    """Table header → first row (also: chip → cells, named-macro
    header → pill row). Default: ``12/1600`` (0.75%) of doc width."""

    table_col_spacing: SpacingValue = Field(default=None)
    """Between adjacent table columns (pills, cells). Default:
    ``6/1600`` (0.375%) of doc width."""

    table_row_spacing: SpacingValue = Field(default=None)
    """Between adjacent table rows. Default: ``9/1600`` (~0.56%) of
    doc width."""

    # ------------------------------------------------------------------
    # Cluster geometry — base: the cluster's own width
    # ------------------------------------------------------------------

    finger_key_gap: SpacingValue = Field(default=None)
    """Center key → outer keys inside a finger cluster. Base: finger
    cluster width. Default: ``1.8%``."""

    thumb_key_gap: SpacingValue = Field(default=None)
    """Vertical gap above each outer thumb key (pad / nail / up /
    knuckle). Base: thumb cluster width. Default: ``3.8%``."""

    # ------------------------------------------------------------------
    # Layer indicators — base: ``output.layout.width``
    # ------------------------------------------------------------------

    layer_indicator_spacing: SpacingValue = Field(default=None)
    """Outer key → its layer indicator circle. Default chosen so finger
    and thumb indicators share the same gap regardless of cluster size."""

    # ------------------------------------------------------------------
    # Chip / pill / badge internals — base: ``output.layout.width``
    # ------------------------------------------------------------------

    chip_padding: SpacingValue = Field(default=None)
    """Symmetric horizontal inset inside any chip. Vertical inset is
    derived as ``chip_padding * 0.25``. Default:
    ``20/1600`` (1.25%) of doc width."""

    tap_dance_pill_padding: SpacingValue = Field(default=None)
    """Symmetric horizontal inset inside a tap-dance pill (cell).
    Vertical inset is derived as ``tap_dance_pill_padding * 0.25``.
    Default: ``20/1600`` (1.25%) of doc width."""

    macro_action_inset: SpacingValue = Field(default=None)
    """Uniform inset for all three positions inside a macro pill —
    pill edge → icon centre, icon centre → text start, text end →
    pill edge. Default: ``10/1600`` (0.625%) of doc width."""

    layer_badge_inset: SpacingValue = Field(default=None)
    """Leading horizontal inset inside a layer badge (badge edge →
    label text). Trailing inset is derived as
    ``layer_badge_inset * 2``. Default: ``15/1600`` (~0.94%) of doc
    width."""


class Layout(BaseModel):
    """Layout dimensions and spacing configuration.

    Controls the overall dimensions and spacing of generated keymap images.
    The height is calculated automatically based on the width to maintain
    the correct aspect ratio for the Svalboard layout.

    Attributes:
        width: Total width of the generated image in SVG units (typically
            pixels at default scale). Defaults to 1600.
        spacing: Spacing configuration for margins and padding. Defaults
            to a Spacing instance with default values.

    Example:
        ```pycon
        >>> layout = Layout(width=1200, spacing=Spacing(margin=20))
        >>> layout.width
        1200.0

        ```
    """

    model_config = ConfigDict(frozen=True)

    width: float = 1600
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
        ```pycon
        >>> border = Border(width=3, radius=15)
        >>> border.radius
        15.0

        ```
    """

    model_config = ConfigDict(frozen=True)

    width: float = 2
    radius: float = 10


class LayerConnector(BaseModel):
    """Styling for the dotted connector paths in the keymap overview.

    The overview links each layer indicator circle to its key on the
    miniature keymap with a dotted path. This block configures
    visibility, stroke, and dotted cadence. The two stroke / spacing
    fields follow the :data:`SpacingValue` magnitude rule (``< 1.0``
    proportion of doc width, ``>= 1.0`` absolute SVG units, ``"N%"``
    string shorthand).

    Attributes:
        show: Whether to draw connector paths in the overview at all.
            Defaults to ``True``.
        width: Stroke width of the connector path. Default:
            ``4.375 / 1600`` (~0.27%) of doc width — the legacy
            magic number tuned to read clearly on the canonical
            1600-unit overview.
        dot_spacing: Gap between adjacent dots along the path —
            controls the visible cadence of the dotted line. Default:
            ``12.25 / 1600`` (~0.77%) of doc width.

    Example:
        ```pycon
        >>> connector = LayerConnector(show=False, width=5, dot_spacing="1%")
        >>> connector.show
        False
        >>> connector.width
        5.0
        >>> connector.dot_spacing
        0.01

        ```
    """

    model_config = ConfigDict(frozen=True)

    show: bool = True
    width: SpacingValue = Field(default=None)
    dot_spacing: SpacingValue = Field(default=None)


class LayerIndicator(BaseModel):
    """Styling for the layer-indicator badges painted next to
    layer-switch keys in each cluster (and the matching badges in
    the overview's ``LAYERS`` column).

    Mirrors :class:`LayerConnector` — visibility flag plus a stroke
    width that follows the :data:`SpacingValue` magnitude rule
    (``< 1.0`` proportion of doc width, ``>= 1.0`` absolute SVG
    units, ``"N%"`` string shorthand).

    The gap between an outer key's edge and its indicator circle
    lives elsewhere, on
    ``output.layout.spacing.layer_indicator_spacing``, since it's a
    spacing value that applies between two elements rather than a
    property of the indicator itself.

    Attributes:
        show: Whether to draw layer-indicator badges. Defaults to
            ``True``.
        width: Stroke width of the indicator circle. Default:
            ``2.0 / 1600`` (~0.125%) of doc width.

    Example:
        ```pycon
        >>> indicator = LayerIndicator(show=True, width=3)
        >>> indicator.show
        True
        >>> indicator.width
        3.0

        ```
    """

    model_config = ConfigDict(frozen=True)

    show: bool = True
    width: SpacingValue = Field(default=None)


class Strokes(BaseModel):
    """Configurable stroke widths for the rendered chrome.

    Two stroke widths live here; both follow the :data:`SpacingValue`
    magnitude rule (``< 1.0`` proportion of doc width, ``>= 1.0``
    absolute SVG units, ``"N%"`` string shorthand).

    Three stroke values live elsewhere because they're tied to a
    visibility flag or other styling on the same conceptual element:

    * ``output.style.border.width`` — paired with ``Border.radius``.
    * ``output.style.layer_connector.width`` — paired with
      ``layer_connector.show`` and ``dot_spacing``.
    * ``output.style.layer_indicator.width`` — paired with
      ``layer_indicator.show``.

    Attributes:
        chip_outline: Stroke around macro and tap-dance chips.
            Default: ``1.2 / 1600`` (~0.075%) of doc width.
        header_rule: Stroke of every header rule — the section title
            stripe rule and the named-macro hairline below the chip.
            Default: ``1.2 / 1600`` (~0.075%) of doc width.

    Example:
        ```pycon
        >>> strokes = Strokes(chip_outline=2, header_rule="0.1%")
        >>> strokes.chip_outline
        2.0
        >>> strokes.header_rule
        0.001

        ```
    """

    model_config = ConfigDict(frozen=True)

    chip_outline: SpacingValue = Field(default=None)
    header_rule: SpacingValue = Field(default=None)


class LayerColor(BaseModel):
    """Color configuration for a keyboard layer.

    Defines the colour scheme used for keys on a specific layer. Each
    cluster position (centre, north, east, south, west, double-south)
    pulls its fill from a 6-stop gradient — adjacent keys land on
    adjacent stops, so a cluster reads with visual depth.

    Two ways to populate the gradient:

    * Provide ``base_color`` (and optionally ``color_index``) and
      leave ``gradient`` at ``None``.
      :func:`skim.application.keymap_generator.draw_keymap`
      auto-derives a 6-stop gradient via
      :func:`skim.application.render.styling.make_gradient`, anchoring
      ``base_color`` at ``color_index`` and stepping darker / lighter
      to fill the surrounding stops.
    * Set ``gradient`` explicitly to a 6-tuple of CSS colour strings.
      In that case ``draw_keymap`` keeps the user-supplied tuple
      verbatim. ``color_index`` still matters: it picks which stop
      the rest of the render path treats as the layer's "primary"
      colour (indicator circles, layer badges, the layer-trigger
      highlight on a source key).

    Attributes:
        base_color: The primary CSS colour for the layer
            (e.g. ``"#FF0000"``, ``"red"``, ``"rgb(255,0,0)"``). Used
            both as the gradient anchor when ``gradient`` is ``None``
            and as the layer's "primary" colour everywhere a single
            colour is needed (e.g. the auto-mouse-layer accent).
        color_index: Position (0–5) where ``base_color`` lands in the
            gradient. Defaults to 2 (the third stop). Used by
            :func:`make_gradient` when auto-deriving the gradient and
            by the renderer to pick the layer's "primary" stop when
            ``gradient`` is set explicitly.
        gradient: Optional 6-tuple of CSS colour strings — one per
            cluster position. When ``None`` the gradient is
            auto-derived from ``base_color`` and ``color_index`` at
            keymap-generation time, so the rendered output always
            sees a fully-populated gradient regardless of which form
            the user wrote.

    Example:
        ```pycon
        >>> # Auto-derived gradient — base_color anchors index 2.
        >>> layer = LayerColor(base_color="#FF0000")
        >>> layer.gradient is None
        True

        >>> # Explicit 6-stop gradient.
        >>> layer = LayerColor(
        ...     base_color="#FF0000",
        ...     gradient=("#FF0000", "#CC0000", "#990000", "#660000", "#330000", "#000000"),
        ... )
        >>> layer[1]
        '#CC0000'

        ```
    """

    model_config = ConfigDict(frozen=True)

    base_color: str
    color_index: int = 2
    gradient: (
        Annotated[tuple[str, str, str, str, str, str], BeforeValidator(_coerce_to_tuple)] | None
    ) = None

    def __getitem__(self, index: int) -> str:
        """Get the color for a specific cluster position.

        Args:
            index: Position index from 0-5 corresponding to cluster
                key positions.

        Returns:
            The CSS colour string for the gradient stop at ``index``.
            When ``gradient`` is ``None`` (the user-facing schema's
            "let Skim derive it" case), falls back to ``base_color``
            for every position so the lookup never fails. The
            keymap-generation pipeline replaces ``None`` gradients
            with auto-derived 6-stop tuples before rendering, so the
            fallback only kicks in for callers that bypass that
            pipeline (tests, introspection, the TUI's pre-fill path).

        Raises:
            IndexError: If index is outside the valid range (0-5).

        Example:
            ```pycon
            >>> layer = LayerColor(base_color="#FFF")
            >>> layer[0]
            '#FFF'

            ```
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
            ```pycon
            >>> str(LayerColor(base_color="#FFF"))
            '["#FFF"]'

            ```
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
            ```pycon
            >>> layer = LayerColor(
            ...     base_color="#FF0000",
            ...     gradient=("#FF0000", "#AA0000", "#880000", "#660000", "#440000", "#220000"),
            ... )
            >>> layer.dark_accent_color
            '#AA0000'

            ```
        """
        return self.base_color if not self.gradient else self.gradient[1]


class Palette(BaseModel):
    """Color palette configuration for the entire keyboard.

    Defines the color scheme used throughout the generated keymap images,
    including background colors, text colors, and per-layer key colors.

    Attributes:
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
        macro_color: Background color for macro badges and macro-table
            titles in the rendered keymap. Defaults to "#89511C".
        tap_dance_color: Background color for tap-dance badges and
            tap-dance-table titles in the rendered keymap. Defaults to
            "#41687F".
        layers: Tuple of LayerColor configurations, one per layer.
            Layer indices correspond to positions in this tuple.
            Defaults to an empty tuple.

    Example:
        ```pycon
        >>> palette = Palette(
        ...     background_color="#F0F0F0",
        ...     layers=(
        ...         LayerColor(base_color="#3366CC"),
        ...         LayerColor(base_color="#CC6633"),
        ...     ),
        ... )
        >>> palette.background_color
        '#F0F0F0'

        ```
    """

    model_config = ConfigDict(frozen=True)

    neutral_color: str = "#6F768B"
    text_color: str = "black"
    key_label_color: str = "white"
    background_color: str = "white"
    border_color: str = "black"
    macro_color: str = "#89511C"
    tap_dance_color: str = "#41687F"
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


SplitSidePositionStr = Annotated[SplitSidePosition, BeforeValidator(lambda v: SplitSidePosition(v))]
"""Annotated type for SplitSidePosition that accepts string inputs.

This type alias allows configuration files to specify hold symbol positions
as plain strings (e.g., "inward", "outward") which are automatically
converted to SplitSidePosition enum members during validation.

Example:
    In a YAML configuration file:

    ```yaml
    style:
      hold_symbol_position: outward
    ```

    When parsed, "outward" is converted to SplitSidePosition.OUTWARD.
"""


class SymbolLegendFlow(str, Enum):
    """Flow direction for the symbol legend's multi-column layout.

    Attributes:
        ROW_MAJOR: Entries fill left-to-right in the top row first, then
            drop to the next row.
        COLUMN_MAJOR: Entries fill top-to-bottom in the leftmost column
            first, then move to the next column. This is the default.
    """

    ROW_MAJOR = "row"
    COLUMN_MAJOR = "column"


SymbolLegendFlowStr = Annotated[SymbolLegendFlow, BeforeValidator(lambda v: SymbolLegendFlow(v))]


class MacrosLegend(BaseModel):
    """Configuration for the macros legend table.

    Controls visibility (whether the macros legend renders inside
    per-layer / overview images) and the body-scale multiplier
    applied when the macros are rendered as a standalone image.

    Attributes:
        show: Whether to embed the macros legend in per-layer and
            overview images. Defaults to ``True``.
        scale: Body-scale multiplier for the standalone macros image
            (the artifact ``skim generate -l macros`` produces). Body
            chips and pills scale by this factor; chrome (title,
            footer, outer padding) stays at the unscaled per-image
            size. Defaults to ``1.5``.

    Example:
        ```pycon
        >>> macros = MacrosLegend(show=True, scale=2.0)
        >>> macros.scale
        2.0

        ```
    """

    model_config = ConfigDict(frozen=True)

    show: bool = True
    scale: float = Field(default=1.5, gt=0)


class TapDancesLegend(BaseModel):
    """Configuration for the tap-dances legend table.

    Mirrors :class:`MacrosLegend` — visibility plus a body-scale
    multiplier for the standalone tap-dances image.

    Attributes:
        show: Whether to embed the tap-dances legend in per-layer and
            overview images. Defaults to ``True``.
        scale: Body-scale multiplier for the standalone tap-dances
            image. Defaults to ``1.5``.

    Example:
        ```pycon
        >>> td = TapDancesLegend(show=False)
        >>> td.show
        False
        >>> td.scale
        1.5

        ```
    """

    model_config = ConfigDict(frozen=True)

    show: bool = True
    scale: float = Field(default=1.5, gt=0)


class SymbolsLegend(BaseModel):
    """Configuration for the symbols legend table.

    Carries the same visibility / scale fields as the macros and
    tap-dances legends, plus two layout knobs unique to the symbol
    table (the multi-column layout's flow direction and column count).

    Attributes:
        show: Whether to embed the symbol legend in per-layer and
            overview images. Defaults to ``True``.
        scale: Body-scale multiplier for the standalone symbols image.
            Defaults to ``1.5``.
        flow: Flow direction for the multi-column layout.
            ``COLUMN_MAJOR`` (default) fills each column top-to-bottom
            before moving to the next. ``ROW_MAJOR`` fills each row
            left-to-right before dropping to the next row.
        columns: When set, force the standalone symbols image to lay
            out at exactly this many columns and shrink the canvas to
            fit the resulting natural width. ``None`` (default) lets
            the table pick the largest column count that fits the
            canvas budget — current per-layer / overview behaviour.

    Example:
        ```pycon
        >>> symbols = SymbolsLegend(columns=3, flow="row")
        >>> symbols.columns
        3
        >>> symbols.flow
        <SymbolLegendFlow.ROW_MAJOR: 'row'>

        ```
    """

    model_config = ConfigDict(frozen=True)

    show: bool = True
    scale: float = Field(default=1.5, gt=0)
    flow: SymbolLegendFlowStr = Field(default=SymbolLegendFlow.COLUMN_MAJOR)
    columns: int | None = Field(default=None, gt=0)


class LegendTables(BaseModel):
    """Container for the three legend tables Skim renders alongside
    the keymap: macros, tap-dances, and symbols.

    Each sub-block carries its own visibility flag and standalone-image
    body-scale multiplier (plus, for symbols, a flow direction and
    column count).

    Attributes:
        macros: Configuration for the macros legend.
        tap_dances: Configuration for the tap-dances legend.
        symbols: Configuration for the symbol legend.

    Example:
        ```pycon
        >>> legends = LegendTables(
        ...     macros=MacrosLegend(show=False),
        ...     symbols=SymbolsLegend(scale=2.0, columns=4),
        ... )
        >>> legends.macros.show
        False
        >>> legends.symbols.columns
        4

        ```
    """

    model_config = ConfigDict(frozen=True)

    macros: MacrosLegend = Field(default_factory=MacrosLegend)
    tap_dances: TapDancesLegend = Field(default_factory=TapDancesLegend)
    symbols: SymbolsLegend = Field(default_factory=SymbolsLegend)


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
        use_system_fonts: When True, the SVG references system fonts by
            name instead of embedding the bundled font subsets. Smaller
            file size; viewers without those fonts installed will see a
            fallback. Defaults to False.
        show_transparent_fallthrough: When True (default), transparent
            keycodes (KC_TRNS / _______) on layers above 0 render the
            same label as layer 0 in a faded "ghost" color. Set False to
            leave transparent keys blank.
        border: Document border configuration, or None to disable.
            Defaults to a :class:`Border` with the canonical 2-unit
            stroke and 10-unit corner radius.
        layer_connector: Configuration for the dotted connector paths
            in the keymap overview (visibility + stroke + dot cadence).
        layer_indicator: Configuration for the layer-indicator badges
            painted next to layer-switch keys (visibility + stroke).
        legend_tables: Container for the macros / tap-dances / symbols
            legend tables (visibility + scale per legend, plus the
            symbol-specific flow and column count).
        strokes: Stroke widths for chrome lines that don't have their
            own dedicated block (chip outlines, header rules).
        palette: Color palette configuration for the entire keyboard.

    Example:
        ```pycon
        >>> style = Style(
        ...     use_layer_colors_on_keys=True,
        ...     hold_symbol_position=SplitSidePosition.INWARD,
        ... )
        >>> style.hold_symbol_position
        <SplitSidePosition.INWARD: 'inward'>

        ```
    """

    model_config = ConfigDict(frozen=True)

    use_layer_colors_on_keys: bool = True
    hold_symbol_position: SplitSidePositionStr = Field(default=SplitSidePosition.OUTWARD)
    use_system_fonts: bool = False
    show_transparent_fallthrough: bool = True
    border: Border | None = Field(default_factory=Border)
    layer_connector: LayerConnector = Field(default_factory=LayerConnector)
    layer_indicator: LayerIndicator = Field(default_factory=LayerIndicator)
    legend_tables: LegendTables = Field(default_factory=LegendTables)
    strokes: Strokes = Field(default_factory=Strokes)
    palette: Palette = Field(default_factory=Palette)


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
        ```pycon
        >>> output = Output(
        ...     layout=Layout(width=1000),
        ...     style=Style(use_layer_colors_on_keys=False),
        ... )
        >>> output.layout.width
        1000.0

        ```
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
        Creating a basic configuration:

        ```python
        config = SkimConfig()
        new_layout = config.output.layout.model_copy(update={"width": 1200})
        new_output = config.output.model_copy(update={"layout": new_layout})
        config = config.model_copy(update={"output": new_output})
        ```

        Loading from a dictionary (e.g., parsed YAML):

        ```python
        data = {
            "keyboard": {
                "features": {"double_south": True},
                "layers": [{"index": 0, "id": "1", "name": "Base"}],
            },
            "output": {"layout": {"width": 1000}},
        }
        config = SkimConfig(**data)
        ```
    """

    model_config = ConfigDict(frozen=True)

    keyboard: Keyboard = Field(default_factory=Keyboard)
    keycodes: Keycodes = Field(default_factory=Keycodes)
    output: Output = Field(default_factory=Output)
