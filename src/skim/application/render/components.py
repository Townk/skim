"""Keyboard cluster rendering components.

This module provides SVG rendering components for keyboard clusters (finger
and thumb), handling layout, key rendering, and hold symbol positioning.
"""

import re
from abc import ABCMeta, abstractmethod
from typing import Generic, Literal

import drawsvg as draw
from drawsvg import DrawingElement
from typing_extensions import override

from skim.data import ClusterT, FingerCluster, SplitSidePosition, ThumbCluster
from skim.domain import (
    NBSP_CHAR,
    SEPARATOR_CHAR,
    KeyboardSide,
    KeyDirection,
    SvalboardTargetKey,
)

from .context import (
    ClusterRenderContext,
    FingerClusterKeyColors,
    RenderContext,
)
from .geometry import AspectRatio
from .keys import (
    CenterKey,
    DirectionalKey,
    DoubleDownKey,
    DoubleSouthKey,
    DownKey,
    KnuckleKey,
    NailKey,
    PadKey,
    UpKey,
)
from .layout import (
    Boundary,
    BoundingBox,
    FingerClusterKeyProportions,
    FingerClusterLayout,
    Position,
    Size,
    ThumbClusterKeyProportions,
    ThumbClusterLayout,
)


class KeyCluster(draw.Group, Generic[ClusterT], metaclass=ABCMeta):
    """Base class for keyboard cluster rendering components.

    Attributes:
        _keymap_cluster: The keymap data for this cluster.
        _side: The keyboard side (LEFT or RIGHT).
        _render_context: The rendering context with shared parameters.
        _boundary: The layout boundary for this cluster.
        _height: The calculated height of the cluster.
        _center: The center position of the cluster.
    """

    _keymap_cluster: ClusterT
    _side: KeyboardSide
    _render_context: RenderContext
    _boundary: Boundary
    _height: float
    _center: Position

    def __init__(
        self,
        keymap_cluster: ClusterT,
        side: KeyboardSide,
        layout: Boundary,
        aspect_ratio: AspectRatio,
        render_context: RenderContext,
        **kwargs,
    ):
        """Initialize a keyboard cluster component.

        Args:
            keymap_cluster: The keymap data for this cluster.
            side: The keyboard side (LEFT or RIGHT).
            layout: The layout boundary for this cluster.
            aspect_ratio: The aspect ratio to maintain for the cluster.
            render_context: The rendering context with shared parameters.
            **kwargs: Additional arguments passed to the parent Group.
        """
        self._height = aspect_ratio.height_from_width(layout.width)
        self._keymap_cluster = keymap_cluster
        self._side = side
        self._boundary = layout
        self._render_context = render_context
        self._center = Position(x=layout.width / 2.0, y=self._height / 2.0)
        super().__init__(**self.override_args(side, layout, kwargs))

    @property
    def x(self) -> float:
        """Get the x coordinate of the cluster."""
        return self._boundary.pos.x

    @property
    def y(self) -> float:
        """Get the y coordinate of the cluster."""
        return self._boundary.pos.y

    @property
    def width(self) -> float:
        """Get the width of the cluster."""
        return self._boundary.width

    @property
    def height(self) -> float:
        """Get the height of the cluster."""
        return self._height

    def override_args(self, side: KeyboardSide, layout: Boundary, kwargs: dict) -> dict:
        """Override SVG group arguments for subclass-specific positioning.

        Args:
            side: The keyboard side.
            layout: The layout boundary.
            kwargs: The arguments to override.

        Returns:
            The modified arguments dictionary.
        """
        _ = side
        _ = layout
        return kwargs

    @abstractmethod
    def build(self) -> DrawingElement:
        """Build the SVG element for this cluster.

        Returns:
            A DrawingElement representing the cluster.
        """
        pass


def _adjust_hold_symbol_label(
    hold_pos: Literal[SplitSidePosition.INWARD, SplitSidePosition.OUTWARD],
    side: KeyboardSide,
    label: str,
) -> str:
    """Adjust hold/tap symbol positions in a label based on configuration.

    Recursively processes labels with hold/tap separators to reorder symbols
    based on the hold_pos setting and keyboard side.

    Args:
        hold_pos: The desired hold symbol position (INWARD or OUTWARD).
        side: The keyboard side (LEFT or RIGHT).
        label: The label string with hold/tap separator.

    Returns:
        The adjusted label string.
    """
    parts = re.split(f"({SEPARATOR_CHAR}|{NBSP_CHAR})", label, maxsplit=1)
    if len(parts) == 3:
        hold, sep, tap = parts
        tap = _adjust_hold_symbol_label(hold_pos, side, tap)
        if hold_pos == SplitSidePosition.OUTWARD:
            label = f"{hold}{sep}{tap}" if side == KeyboardSide.LEFT else f"{tap}{sep}{hold}"
        else:
            label = f"{tap}{sep}{hold}" if side == KeyboardSide.LEFT else f"{hold}{sep}{tap}"
    return label


class ThumbClusterComponent(KeyCluster[ThumbCluster[SvalboardTargetKey]]):
    """Renders a thumb cluster with all its keys.

    Attributes:
        ASPECT_RATIO: The aspect ratio for thumb clusters (1.5:1).
        CLUSTER_WIDTH_PROPORTIONS: The proportional widths for each key.
        _layout: The computed layout for this cluster.
    """

    _ASPECT_RATIO = AspectRatio("1.5:1")
    _CLUSTER_WIDTH_PROPORTIONS = ThumbClusterKeyProportions(
        keys_width_proportion=ThumbCluster(
            down_key=0.25,
            pad_key=0.38,
            up_key=0.372,
            nail_key=0.4,
            knuckle_key=0.385,
            double_down_key=0.13,
        ),
        inset_width_proportion=0.038,
    )

    _layout: ThumbClusterLayout

    def __init__(
        self,
        keymap_cluster: ThumbCluster[SvalboardTargetKey],
        side: KeyboardSide,
        layout: Boundary,
        render_context: RenderContext,
        **kwargs,
    ):
        """Initialize a thumb cluster component.

        Args:
            keymap_cluster: The thumb cluster keymap data.
            side: The keyboard side (LEFT or RIGHT).
            layout: The layout boundary for this cluster.
            render_context: The rendering context with shared parameters.
            **kwargs: Additional arguments passed to the parent.
        """
        super().__init__(
            keymap_cluster,
            side,
            layout,
            ThumbClusterComponent._ASPECT_RATIO,
            render_context,
            **kwargs,
        )

    @override
    def override_args(self, side: KeyboardSide, layout: Boundary, kwargs: dict) -> dict:
        """Override SVG group arguments for thumb cluster positioning.

        Args:
            side: The keyboard side.
            layout: The layout boundary.
            kwargs: The arguments to override.

        Returns:
            The modified arguments dictionary with transform applied.
        """
        self._layout = ThumbClusterLayout(
            side,
            BoundingBox(pos=self._boundary.pos, size=Size(width=self.width, height=self.height)),
            ThumbClusterComponent._CLUSTER_WIDTH_PROPORTIONS,
        )
        pad_left = self._layout.metrics.pad_key.pos.x
        nail_left = layout.pos.x - self._layout.metrics.nail_key.pos.x
        transform = kwargs.pop("transform", "")

        # layout.pos.x
        # + (-layout.width if side == KeyboardSide.LEFT else layout.width)
        # *ThumbCluster.X_TRANSLATION_MULTI

        x_translation = layout.pos.x - pad_left if side == KeyboardSide.LEFT else nail_left
        full_transform = f"translate({x_translation},{layout.pos.y})"
        if transform:
            full_transform = f"{full_transform} {transform}"
        kwargs["transform"] = full_transform
        return kwargs

    @override
    def build(self) -> DrawingElement:
        """Build the SVG element for this thumb cluster.

        Returns:
            This component with all key elements appended.
        """
        keys = self._adjust_hold_symbol_positions(self._keymap_cluster)
        metrics = self._layout.metrics
        ctx = ClusterRenderContext.from_render_context(self._render_context, self._side)
        self.append(DownKey(ctx, keys.down_key, metrics.down_key))
        self.append(DoubleDownKey(ctx, keys.double_down_key, metrics.double_down_key))
        self.append(PadKey(ctx, keys.pad_key, metrics.pad_key))
        self.append(NailKey(ctx, keys.nail_key, metrics.nail_key))
        self.append(UpKey(ctx, keys.up_key, metrics.up_key))
        self.append(KnuckleKey(ctx, keys.knuckle_key, metrics.knuckle_key))
        return self

    def _adjust_hold_symbol_positions(
        self, keys: ThumbCluster[SvalboardTargetKey]
    ) -> ThumbCluster[SvalboardTargetKey]:
        """Adjust hold/tap symbol positions in thumb cluster keys.

        Args:
            keys: The thumb cluster keys.

        Returns:
            A new ThumbCluster with adjusted labels.
        """
        hold_pos = self._render_context.hold_symbol_position
        if hold_pos == SplitSidePosition.QMK_DEFINED:
            return keys

        pad_side = KeyboardSide.LEFT if self._side == KeyboardSide.LEFT else KeyboardSide.RIGHT
        nail_side = KeyboardSide.RIGHT if self._side == KeyboardSide.LEFT else KeyboardSide.LEFT
        up_side = KeyboardSide.LEFT if self._side == KeyboardSide.LEFT else KeyboardSide.RIGHT
        knuckle_side = KeyboardSide.RIGHT if self._side == KeyboardSide.LEFT else KeyboardSide.LEFT

        return ThumbCluster(
            down_key=keys.down_key,
            pad_key=SvalboardTargetKey(
                _adjust_hold_symbol_label(hold_pos, pad_side, keys.pad_key.label),
                keys.pad_key.layer_switch,
            ),
            up_key=SvalboardTargetKey(
                _adjust_hold_symbol_label(hold_pos, up_side, keys.up_key.label),
                keys.up_key.layer_switch,
            ),
            nail_key=SvalboardTargetKey(
                _adjust_hold_symbol_label(hold_pos, nail_side, keys.nail_key.label),
                keys.nail_key.layer_switch,
            ),
            knuckle_key=SvalboardTargetKey(
                _adjust_hold_symbol_label(hold_pos, knuckle_side, keys.knuckle_key.label),
                keys.knuckle_key.layer_switch,
            ),
            double_down_key=keys.double_down_key,
        )


class FingerClusterComponent(KeyCluster[FingerCluster[SvalboardTargetKey]]):
    """Renders a finger cluster with all its keys.

    Attributes:
        _ASPECT_RATIO_DOUBLE_SOUTH: The aspect ratio when double_south key is present (3:4).
        _ASPECT_RATIO: The standard aspect ratio for finger clusters (1:1).
        _CLUSTER_WIDTH_PROPORTIONS: The proportional widths for each key.
        _layout: The computed layout for this cluster.
    """

    _ASPECT_RATIO_DOUBLE_SOUTH = AspectRatio("3:4")
    _ASPECT_RATIO = AspectRatio("1:1")

    _CLUSTER_WIDTH_PROPORTIONS = FingerClusterKeyProportions(
        center_key_width_proportion=0.309,
        outer_key_width_proportion=0.328,
        inset_width_proportion=0.018,
    )

    _layout: FingerClusterLayout

    def __init__(
        self,
        keymap_cluster: FingerCluster[SvalboardTargetKey],
        side: KeyboardSide,
        layout: Boundary,
        render_context: RenderContext,
        **kwargs,
    ):
        """Initialize a finger cluster component.

        Args:
            keymap_cluster: The finger cluster keymap data.
            side: The keyboard side (LEFT or RIGHT).
            layout: The layout boundary for this cluster.
            render_context: The rendering context with shared parameters.
            **kwargs: Additional arguments passed to the parent.
        """
        super().__init__(
            keymap_cluster,
            side,
            layout,
            FingerClusterComponent._ASPECT_RATIO_DOUBLE_SOUTH
            if render_context.has_double_south
            else FingerClusterComponent._ASPECT_RATIO,
            render_context,
            **kwargs,
        )
        self._layout = FingerClusterLayout(
            self._boundary, FingerClusterComponent._CLUSTER_WIDTH_PROPORTIONS
        )

    @override
    def override_args(self, side: KeyboardSide, layout: Boundary, kwargs: dict) -> dict:
        """Override SVG group arguments for finger cluster positioning.

        Args:
            side: The keyboard side.
            layout: The layout boundary.
            kwargs: The arguments to override.

        Returns:
            The modified arguments dictionary with transform applied.
        """
        _ = side
        transform = kwargs.pop("transform", "")
        if layout.pos.x != 0 or layout.pos.y != 0 or transform:
            full_transform = f"translate({layout.pos.x},{layout.pos.y})"
            if transform:
                full_transform = f"{full_transform} {transform}"
            kwargs["transform"] = full_transform
        return kwargs

    @override
    def build(self) -> DrawingElement:
        """Build the SVG element for this finger cluster.

        Returns:
            This component with all key elements appended.
        """
        ctx = ClusterRenderContext.from_render_context(self._render_context, self._side)
        k = self._adjust_hold_symbol_positions(self._keymap_cluster)
        c = self._get_key_colors(self._render_context)
        m = self._layout.metrics

        self.append(DirectionalKey(ctx, k.north_key, c.north_key, KeyDirection.NORTH, m.north_key))
        self.append(DirectionalKey(ctx, k.south_key, c.south_key, KeyDirection.SOUTH, m.south_key))
        self.append(DirectionalKey(ctx, k.east_key, c.east_key, KeyDirection.EAST, m.east_key))
        self.append(DirectionalKey(ctx, k.west_key, c.west_key, KeyDirection.WEST, m.west_key))
        self.append(CenterKey(ctx, k.center_key, c.center_key, m.center_key))
        if self._render_context.has_double_south:
            self.append(
                DoubleSouthKey(ctx, k.double_south_key, c.double_south_key, m.double_south_key)
            )
        return self

    def _adjust_hold_symbol_positions(
        self, keys: FingerCluster[SvalboardTargetKey]
    ) -> FingerCluster[SvalboardTargetKey]:
        """Adjust hold/tap symbol positions in finger cluster keys.

        Args:
            keys: The finger cluster keys.

        Returns:
            A new FingerCluster with adjusted labels.
        """
        hold_pos = self._render_context.hold_symbol_position
        if hold_pos == SplitSidePosition.QMK_DEFINED:
            return keys

        return FingerCluster(
            center_key=keys.center_key,
            north_key=keys.north_key,
            east_key=SvalboardTargetKey(
                _adjust_hold_symbol_label(hold_pos, KeyboardSide.LEFT, keys.east_key.label),
                keys.east_key.layer_switch,
            ),
            south_key=keys.south_key,
            west_key=SvalboardTargetKey(
                _adjust_hold_symbol_label(hold_pos, KeyboardSide.RIGHT, keys.west_key.label),
                keys.west_key.layer_switch,
            ),
            double_south_key=keys.double_south_key,
        )

    def _get_key_colors(self, ctx: RenderContext) -> FingerCluster[FingerClusterKeyColors]:
        """Get the color pair for each finger cluster key.

        Args:
            ctx: The render context with layer color information.

        Returns:
            A FingerCluster containing color pairs for each key.
        """
        c = ctx.layer_colors
        north_color = FingerClusterKeyColors(primary=c[4], accent=c[3])
        double_south_color = FingerClusterKeyColors(primary=c[2], accent=c[1])
        if ctx.has_double_south:
            center_color = FingerClusterKeyColors(primary=c[0], accent=c[0])
            south_color = FingerClusterKeyColors(primary=c[1], accent=c[0])
        else:
            center_color = FingerClusterKeyColors(primary=c[1], accent=c[1])
            south_color = FingerClusterKeyColors(primary=c[2], accent=c[1])

        if self._side == KeyboardSide.LEFT:
            east_color = FingerClusterKeyColors(primary=c[3], accent=c[2])
            west_color = FingerClusterKeyColors(primary=c[5], accent=c[4])
        else:
            east_color = FingerClusterKeyColors(primary=c[5], accent=c[4])
            west_color = FingerClusterKeyColors(primary=c[3], accent=c[2])

        return FingerCluster(
            center_key=center_color,
            north_key=north_color,
            east_key=east_color,
            south_key=south_color,
            west_key=west_color,
            double_south_key=double_south_color,
        )
