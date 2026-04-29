# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Rendering context objects for keyboard visualization.

This module provides context classes that encapsulate rendering parameters
shared across components, reducing parameter passing and centralizing
configuration for keyboard cluster rendering.
"""

import colorsys
from collections.abc import Callable
from dataclasses import dataclass, field

from typing_extensions import Self

from skim.data import LayerColor, Palette, SplitSidePosition
from skim.domain import KeyboardSide, SvalboardTargetKey

from .styling import lighten, str_to_rgb

GHOST_LABEL_LIGHTNESS_DELTA = 0.12
"""Magnitude of the HSL lightness shift applied to a transparent key's fill
color to produce its faded "ghost" label color. The shift lightens fills
that sit at or below the layer's base color and darkens fills above it."""


@dataclass(frozen=True)
class RenderContext:
    """Context object containing render parameters shared across components.

    This dataclass encapsulates the common parameters needed for rendering
    keyboard clusters, reducing parameter passing between methods.
    """

    palette: Palette
    layer_index: int
    has_double_south: bool
    use_layer_colors_on_keys: bool
    hold_symbol_position: SplitSidePosition
    use_system_fonts: bool = False
    show_layer_indicators: bool = False
    qmk_index_to_position: Callable[[int], int | None] = field(
        default=lambda idx: idx, repr=False, compare=False, hash=False
    )
    layer_colors: LayerColor = field(init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "layer_colors", self.palette.layers[self.layer_index])

    def key_fill_color(
        self, key: SvalboardTargetKey, default: str, use_accent: bool = False
    ) -> str:
        """Get the fill color for a key, using layer colors if enabled.

        Args:
            key: The target key with optional layer_switch info.
            default: The default color if layer colors are not used.
            use_accent: When true, returns the accent color instead of the base
                one.

        Returns:
            The fill color to use for the key.
        """
        if not self.use_layer_colors_on_keys:
            return default

        if key.layer_switch is None:
            return default

        position = self.qmk_index_to_position(key.layer_switch)
        if position is not None and 0 <= position < len(self.palette.layers):
            lc = self.palette.layers[position]
            return lc[lc.color_index - (1 if use_accent else 0)]

        return default

    def key_label_color(self, key: SvalboardTargetKey, fill_color: str) -> str:
        """Get the text color for a key's label.

        For transparent keys with a non-empty (substituted) label, returns a
        faded "ghost" color derived from the key's fill color. For all other
        keys, returns the palette's standard key label color.

        Args:
            key: The target key whose label is being rendered.
            fill_color: The key's resolved fill color, used as the source for
                the ghost color when the key is transparent.

        Returns:
            The CSS color string to use for the label text.
        """
        if key.is_transparent and key.label:
            fill_lightness = colorsys.rgb_to_hls(*str_to_rgb(fill_color))[1]
            base_lightness = colorsys.rgb_to_hls(*str_to_rgb(self.layer_colors.base_color))[1]
            delta = (
                GHOST_LABEL_LIGHTNESS_DELTA
                if fill_lightness <= base_lightness
                else -GHOST_LABEL_LIGHTNESS_DELTA
            )
            return lighten(fill_color, delta)
        return self.palette.key_label_color


@dataclass(frozen=True)
class ClusterRenderContext(RenderContext):
    """Extended render context with keyboard side information.

    Attributes:
        side: The keyboard side (LEFT or RIGHT) for this cluster.
    """

    side: KeyboardSide = KeyboardSide.LEFT

    @classmethod
    def from_render_context(cls, render_context: RenderContext, side: KeyboardSide) -> Self:
        """Create a ClusterRenderContext from a base RenderContext.

        Args:
            render_context: The base render context to copy parameters from.
            side: The keyboard side for this cluster.

        Returns:
            A new ClusterRenderContext instance with all parameters from the
            base context plus the specified side.
        """
        return cls(
            palette=render_context.palette,
            layer_index=render_context.layer_index,
            has_double_south=render_context.has_double_south,
            use_layer_colors_on_keys=render_context.use_layer_colors_on_keys,
            hold_symbol_position=render_context.hold_symbol_position,
            use_system_fonts=render_context.use_system_fonts,
            show_layer_indicators=render_context.show_layer_indicators,
            qmk_index_to_position=render_context.qmk_index_to_position,
            side=side,
        )


@dataclass(frozen=True, slots=True)
class FingerClusterKeyColors:
    """Color pair for finger cluster keys.

    Attributes:
        primary: The primary fill color for the key.
        accent: The accent color for the key's accent bar.
    """

    primary: str
    accent: str
