# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Rendering context objects for keyboard visualization.

This module provides context classes that encapsulate rendering parameters
shared across components, reducing parameter passing and centralizing
configuration for keyboard cluster rendering.
"""

from dataclasses import dataclass, field

from typing_extensions import Self

from skim.data import LayerColor, Palette, SplitSidePosition
from skim.domain import KeyboardSide, SvalboardTargetKey


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

        if 0 <= key.layer_switch < len(self.palette.layers):
            lc = self.palette.layers[key.layer_switch]
            return lc[lc.color_index - (1 if use_accent else 0)]

        return default


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
