# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Key rendering components for the Svalboard keyboard.

This module provides SVG rendering components for individual keys, including
finger cluster keys (center, directional, double-south) and thumb cluster keys
(down, up, pad, nail, knuckle, double-down).
"""

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass

import drawsvg as draw

from skim.domain import Alignment, KeyboardSide, KeyDirection, SvalboardTargetKey

from .context import (
    ClusterRenderContext,
    FingerClusterKeyColors,
)
from .geometry import (
    AspectRatio,
    Trapezoid,
    dimensions_from_ratio,
)
from .layout import Boundary
from .text import Font, Label


@dataclass(frozen=True)
class KeyConfig:
    """Configuration for key rendering parameters.

    Attributes:
        aspect_ratio: The aspect ratio for the key shape.
        font_height_multiplier: Multiplier for font size relative to key height.
        label_width_multiplier: Multiplier for label width relative to key width.
        stroke_width_multiplier: Multiplier for stroke width. Default: 1.0.
        corner_radius_width_multiplier: Multiplier for corner radius. Default: 1.0.
        slant_size_multiplier: Multiplier for trapezoid slant. Default: 0.0.
        label_margin_size_multiplier: Multiplier for label margin. Default: 0.0.
    """

    aspect_ratio: AspectRatio
    font_height_multiplier: float
    label_width_multiplier: float
    stroke_width_multiplier: float = 1.0
    corner_radius_width_multiplier: float = 1.0
    slant_size_multiplier: float = 0.0
    label_margin_size_multiplier: float = 0.0

    @property
    def trapezoid_small_face_multiplier(self) -> float:
        return 1.0 - self.slant_size_multiplier


class Key(draw.Group, metaclass=ABCMeta):
    """Base class for keyboard key rendering.

    Attributes:
        x: The x coordinate of the key.
        y: The y coordinate of the key.
        width: The width of the key.
        height: The height of the key.
        label: The parsed label for this key.
        font_height_multi: Multiplier for font size relative to key height.
        font: The font to use for the label.
        fill_color: The fill color of the key.
        stroke_color: The stroke color of the key shape.
        label_color: The text color used to render the label.
    """

    x: float
    y: float
    width: float
    height: float
    label: Label
    font_height_multi: float
    font: Font
    fill_color: str
    stroke_color: str | None
    label_color: str

    def __init__(
        self,
        label: str,
        x: float = 0,
        y: float = 0,
        width: float | None = None,
        height: float | None = None,
        font_height_multi: float = 0.5,
        font: Font = Font.FINGER_KEY,
        letter_spacing: float | None = None,
        fill_color: str = "#666",
        stroke_color: str = "#FFF",
        label_color: str | None = None,
        use_system_fonts: bool = False,
        **kwargs,
    ):
        """Initialize a key.

        Args:
            label: The label text for this key.
            x: The x coordinate. Default: 0.
            y: The y coordinate. Default: 0.
            width: The width, or None to calculate from height using aspect ratio.
            height: The height, or None to calculate from width using aspect ratio.
            font_height_multi: Multiplier for font size. Default: 0.5.
            font: The font to use. Default: FINGER_KEY.
            letter_spacing: Optional letter spacing in SVG units.
            fill_color: The fill color. Default: "#666".
            stroke_color: The shape stroke color. Default: "#FFF".
            label_color: Optional override for the label text color. Defaults
                to ``stroke_color``.
            use_system_fonts: Whether to use system font families. Default: False.
            **kwargs: Additional arguments passed to the parent Group.
        """
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.width, self.height = dimensions_from_ratio(self.aspect_ratio, width, height)
        resolved_label_color = label_color if label_color is not None else stroke_color
        self.label = Label(
            label,
            font=font,
            text_color=resolved_label_color,
            background_color=fill_color,
            text_anchor=self.text_anchor,
            dominant_baseline=self.dominant_baseline,
            letter_spacing=letter_spacing,
        )
        self.font_height_multi = font_height_multi
        self.font = font
        self.fill_color = fill_color
        self.stroke_color = stroke_color
        self.label_color = resolved_label_color
        self._use_system_fonts = use_system_fonts
        self.build()

    def build(self) -> None:
        """Build the SVG elements for this key.

        Appends the key shape and label text to this group.
        """
        self.append(self.shape)
        label_x, label_y = self.label_coordinates
        font_size = self.label.size_to_fit(
            self.label_width,
            round(self.height * self.font_height_multi),
        )
        self.append(self.label.build_text(label_x, label_y, font_size, self._use_system_fonts))

    @property
    def text_anchor(self) -> str:
        return "middle"

    @property
    def dominant_baseline(self) -> str:
        return "central"

    @property
    def label_width(self) -> float:
        return self.width

    @property
    @abstractmethod
    def aspect_ratio(self) -> AspectRatio:
        """Get the aspect ratio for this key shape.

        Returns:
            The AspectRatio to maintain for this key.
        """
        pass

    @property
    @abstractmethod
    def shape(self) -> draw.DrawingElement:
        """Get the SVG shape element for this key.

        Returns:
            A DrawingElement representing the key shape.
        """
        pass

    @property
    @abstractmethod
    def label_coordinates(self) -> tuple[float, float]:
        """Get the (x, y) coordinates for the label text.

        Returns:
            Tuple of (x, y) coordinates for label placement.
        """
        pass


class DownKey(Key):
    """The down key in a thumb cluster.

    A tall, narrow key with a slanted top, positioned at the bottom of the
    thumb cluster.
    """

    CONFIG = KeyConfig(
        aspect_ratio=AspectRatio("1:2.6"),
        slant_size_multiplier=0.25,
        stroke_width_multiplier=0.04,
        corner_radius_width_multiplier=0.12,
        font_height_multiplier=0.15,
        label_width_multiplier=0.8 - 0.25 / 2,
        label_margin_size_multiplier=0.10,
    )

    def __init__(
        self,
        ctx: ClusterRenderContext,
        key: SvalboardTargetKey,
        layout: Boundary,
        **kwargs,
    ):
        """Initialize a down key.

        Args:
            ctx: The cluster render context.
            key: The target key with label and layer info.
            layout: The layout boundary for this key.
            **kwargs: Additional arguments passed to the parent Key.
        """
        fill_color = ctx.key_fill_color(key, ctx.layer_colors.base_color)
        super().__init__(
            label=key.label,
            x=layout.pos.x,
            y=layout.pos.y,
            width=layout.width,
            font=Font.THUMB_KEY,
            font_height_multi=self.CONFIG.font_height_multiplier,
            fill_color=fill_color,
            stroke_color=ctx.palette.key_label_color,
            label_color=ctx.key_label_color(key, fill_color),
            use_system_fonts=ctx.use_system_fonts,
            **kwargs,
        )

    @property
    def aspect_ratio(self) -> AspectRatio:
        return self.CONFIG.aspect_ratio

    @property
    def shape(self) -> draw.DrawingElement:
        return Trapezoid(
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            top_width=self.width * self.CONFIG.trapezoid_small_face_multiplier,
            corners_radius=self.width * self.CONFIG.corner_radius_width_multiplier,
            fill=self.fill_color,
        )

    @property
    def dominant_baseline(self) -> str:
        return "bottom"

    @property
    def label_width(self) -> float:
        return self.width * self.CONFIG.label_width_multiplier

    @property
    def label_coordinates(self) -> tuple[float, float]:
        label_y = (self.y + self.height) - (self.height * self.CONFIG.label_margin_size_multiplier)
        label_x = self.x + self.width / 2
        return label_x, label_y


class DoubleDownKey(Key):
    """The double-down key in a thumb cluster.

    A small key with a stroke outline, positioned above the down key.
    """

    CONFIG = KeyConfig(
        aspect_ratio=AspectRatio("1:1.1"),
        slant_size_multiplier=0.08,
        stroke_width_multiplier=0.05,
        corner_radius_width_multiplier=0.13,
        font_height_multiplier=0.6,
        label_width_multiplier=0.8 - 0.08,
    )

    side: KeyboardSide

    def __init__(
        self,
        ctx: ClusterRenderContext,
        key: SvalboardTargetKey,
        layout: Boundary,
        **kwargs,
    ):
        """Initialize a double-down key.

        Args:
            ctx: The cluster render context.
            key: The target key with label and layer info.
            layout: The layout boundary for this key.
            **kwargs: Additional arguments passed to the parent Key.
        """
        self.side = ctx.side
        fill_color = ctx.key_fill_color(key, ctx.layer_colors.dark_accent_color)
        super().__init__(
            label=key.label,
            x=layout.pos.x,
            y=layout.pos.y,
            width=layout.width,
            fill_color=fill_color,
            stroke_color=ctx.palette.key_label_color,
            label_color=ctx.key_label_color(key, fill_color),
            font=Font.THUMB_KEY,
            font_height_multi=self.CONFIG.font_height_multiplier,
            use_system_fonts=ctx.use_system_fonts,
            **kwargs,
        )

    @property
    def aspect_ratio(self) -> AspectRatio:
        return self.CONFIG.aspect_ratio

    @property
    def shape(self) -> draw.DrawingElement:
        return Trapezoid(
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            top_width=self.width * self.CONFIG.trapezoid_small_face_multiplier,
            corners_radius=self.width * self.CONFIG.corner_radius_width_multiplier,
            fill=self.fill_color,
            stroke=self.stroke_color,
            stroke_width=self.width * self.CONFIG.stroke_width_multiplier,
        )

    @property
    def label_width(self) -> float:
        return self.width * self.CONFIG.label_width_multiplier

    @property
    def label_coordinates(self) -> tuple[float, float]:
        label_y = self.y + self.height / 2
        label_x = self.x + self.width / 2
        return label_x, label_y


class UpKey(Key):
    """The up key in a thumb cluster.

    A wide, short key with a slanted side, positioned at the top of the
    thumb cluster. The slant direction depends on the keyboard side.
    """

    CONFIG = KeyConfig(
        aspect_ratio=AspectRatio("2.75:1"),
        slant_size_multiplier=0.12,
        stroke_width_multiplier=0.025,
        corner_radius_width_multiplier=0.05,
        font_height_multiplier=0.45,
        label_width_multiplier=0.8,
        label_margin_size_multiplier=0.1,
    )

    side: KeyboardSide

    def __init__(
        self,
        ctx: ClusterRenderContext,
        key: SvalboardTargetKey,
        layout: Boundary,
        **kwargs,
    ):
        """Initialize an up key.

        Args:
            ctx: The cluster render context.
            key: The target key with label and layer info.
            layout: The layout boundary for this key.
            **kwargs: Additional arguments passed to the parent Key.
        """
        self.side = ctx.side
        fill_color = ctx.key_fill_color(key, ctx.layer_colors.dark_accent_color)
        super().__init__(
            label=key.label,
            x=layout.pos.x,
            y=layout.pos.y,
            width=layout.width,
            fill_color=fill_color,
            stroke_color=ctx.palette.key_label_color,
            label_color=ctx.key_label_color(key, fill_color),
            font=Font.THUMB_KEY,
            font_height_multi=self.CONFIG.font_height_multiplier,
            use_system_fonts=ctx.use_system_fonts,
            **kwargs,
        )

    @property
    def aspect_ratio(self) -> AspectRatio:
        return self.CONFIG.aspect_ratio

    @property
    def shape(self) -> draw.DrawingElement:
        stroke_width = self.width * self.CONFIG.stroke_width_multiplier
        w = self.width + stroke_width * 2
        h = self.height + stroke_width * 2.3
        g = draw.Group()
        g.append(
            Trapezoid(
                x=self.x - stroke_width,
                y=self.y - stroke_width,
                width=w,
                height=h,
                right_height=h * self.CONFIG.trapezoid_small_face_multiplier
                if self.side == KeyboardSide.LEFT
                else None,
                left_height=h * self.CONFIG.trapezoid_small_face_multiplier
                if self.side == KeyboardSide.RIGHT
                else None,
                corners_radius=self.width * self.CONFIG.corner_radius_width_multiplier,
                align_y=Alignment.START,
                fill=self.stroke_color,
            )
        )
        g.append(
            Trapezoid(
                x=self.x,
                y=self.y,
                width=self.width,
                height=self.height,
                right_height=self.height * self.CONFIG.trapezoid_small_face_multiplier
                if self.side == KeyboardSide.LEFT
                else None,
                left_height=self.height * self.CONFIG.trapezoid_small_face_multiplier
                if self.side == KeyboardSide.RIGHT
                else None,
                corners_radius=self.width * self.CONFIG.corner_radius_width_multiplier,
                align_y=Alignment.START,
                fill=self.fill_color,
            )
        )
        return g

    @property
    def text_anchor(self) -> str:
        return "end" if self.side == KeyboardSide.LEFT else "start"

    @property
    def label_width(self) -> float:
        return self.width * self.CONFIG.label_width_multiplier

    @property
    def label_coordinates(self) -> tuple[float, float]:
        label_y = self.y + self.height * self.CONFIG.trapezoid_small_face_multiplier / 2.0
        if self.side == KeyboardSide.LEFT:
            label_x = self.x + self.width * (1.0 - self.CONFIG.label_margin_size_multiplier)
        else:
            label_x = self.x + self.width * self.CONFIG.label_margin_size_multiplier
        return label_x, label_y


class PadKey(Key):
    """The pad key in a thumb cluster.

    A medium-width key positioned to the left/right of the up key,
    depending on the keyboard side.
    """

    CONFIG = KeyConfig(
        aspect_ratio=AspectRatio("1.85:1"),
        slant_size_multiplier=0.035,
        stroke_width_multiplier=0.025,
        corner_radius_width_multiplier=0.05,
        font_height_multiplier=0.4,
        label_width_multiplier=0.8 - 0.035,
        label_margin_size_multiplier=0.1 + 0.035,
    )

    side: KeyboardSide

    def __init__(
        self,
        ctx: ClusterRenderContext,
        key: SvalboardTargetKey,
        layout: Boundary,
        **kwargs,
    ):
        """Initialize a pad key.

        Args:
            ctx: The cluster render context.
            key: The target key with label and layer info.
            layout: The layout boundary for this key.
            **kwargs: Additional arguments passed to the parent Key.
        """
        self.side = ctx.side
        fill_color = ctx.key_fill_color(key, ctx.palette.neutral_color)
        super().__init__(
            label=key.label,
            x=layout.pos.x,
            y=layout.pos.y,
            width=layout.width,
            fill_color=fill_color,
            stroke_color=ctx.palette.key_label_color,
            label_color=ctx.key_label_color(key, fill_color),
            font=Font.THUMB_KEY,
            font_height_multi=self.CONFIG.font_height_multiplier,
            use_system_fonts=ctx.use_system_fonts,
            **kwargs,
        )

    @property
    def aspect_ratio(self) -> AspectRatio:
        return self.CONFIG.aspect_ratio

    @property
    def shape(self) -> draw.DrawingElement:
        return Trapezoid(
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            bottom_width=self.width * self.CONFIG.trapezoid_small_face_multiplier,
            corners_radius=self.width * self.CONFIG.corner_radius_width_multiplier,
            align_x=Alignment.START if self.side == KeyboardSide.LEFT else Alignment.END,
            fill=self.fill_color,
        )

    @property
    def text_anchor(self) -> str:
        return "end" if self.side == KeyboardSide.LEFT else "start"

    @property
    def label_width(self) -> float:
        return self.width * self.CONFIG.label_width_multiplier

    @property
    def label_coordinates(self) -> tuple[float, float]:
        label_y = self.y + self.height / 2.0
        if self.side == KeyboardSide.LEFT:
            label_x = self.x + self.width * (1.0 - self.CONFIG.label_margin_size_multiplier)
        else:
            label_x = self.x + self.width * self.CONFIG.label_margin_size_multiplier
        return label_x, label_y


class NailKey(Key):
    """The nail key in a thumb cluster.

    A medium-width key positioned opposite the pad key, depending on the
    keyboard side.
    """

    CONFIG = KeyConfig(
        aspect_ratio=AspectRatio("1.95:1"),
        slant_size_multiplier=0.03,
        stroke_width_multiplier=0.025,
        corner_radius_width_multiplier=0.05,
        font_height_multiplier=0.4,
        label_width_multiplier=0.8 - 0.03,
        label_margin_size_multiplier=0.1 + 0.03,
    )

    side: KeyboardSide

    def __init__(
        self,
        ctx: ClusterRenderContext,
        key: SvalboardTargetKey,
        layout: Boundary,
        **kwargs,
    ):
        """Initialize a nail key.

        Args:
            ctx: The cluster render context.
            key: The target key with label and layer info.
            layout: The layout boundary for this key.
            **kwargs: Additional arguments passed to the parent Key.
        """
        self.side = ctx.side
        fill_color = ctx.key_fill_color(key, ctx.palette.neutral_color)
        super().__init__(
            label=key.label,
            x=layout.pos.x,
            y=layout.pos.y,
            width=layout.width,
            fill_color=fill_color,
            stroke_color=ctx.palette.key_label_color,
            label_color=ctx.key_label_color(key, fill_color),
            font=Font.THUMB_KEY,
            font_height_multi=self.CONFIG.font_height_multiplier,
            use_system_fonts=ctx.use_system_fonts,
            **kwargs,
        )

    @property
    def aspect_ratio(self) -> AspectRatio:
        return self.CONFIG.aspect_ratio

    @property
    def shape(self) -> draw.DrawingElement:
        return Trapezoid(
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            bottom_width=self.width * self.CONFIG.trapezoid_small_face_multiplier,
            corners_radius=self.width * self.CONFIG.corner_radius_width_multiplier,
            align_x=Alignment.END if self.side == KeyboardSide.LEFT else Alignment.START,
            fill=self.fill_color,
        )

    @property
    def text_anchor(self) -> str:
        return "start" if self.side == KeyboardSide.LEFT else "end"

    @property
    def label_width(self) -> float:
        return self.width * self.CONFIG.label_width_multiplier

    @property
    def label_coordinates(self) -> tuple[float, float]:
        label_y = self.y + self.height / 2.0
        if self.side == KeyboardSide.LEFT:
            label_x = self.x + self.width * self.CONFIG.label_margin_size_multiplier
        else:
            label_x = self.x + self.width * (1.0 - self.CONFIG.label_margin_size_multiplier)
        return label_x, label_y


class KnuckleKey(Key):
    """The knuckle key in a thumb cluster.

    A medium-width key positioned opposite the nail key, depending on the
    keyboard side.
    """

    CONFIG = KeyConfig(
        aspect_ratio=AspectRatio("1.87:1"),
        slant_size_multiplier=0.028,
        stroke_width_multiplier=0.025,
        corner_radius_width_multiplier=0.05,
        font_height_multiplier=0.4,
        label_width_multiplier=0.8 - 0.028,
        label_margin_size_multiplier=0.1 + 0.028,
    )

    side: KeyboardSide

    def __init__(
        self,
        ctx: ClusterRenderContext,
        key: SvalboardTargetKey,
        layout: Boundary,
        **kwargs,
    ):
        """Initialize a knuckle key.

        Args:
            ctx: The cluster render context.
            key: The target key with label and layer info.
            layout: The layout boundary for this key.
            **kwargs: Additional arguments passed to the parent Key.
        """
        self.side = ctx.side
        fill_color = ctx.key_fill_color(key, ctx.palette.neutral_color)
        super().__init__(
            label=key.label,
            x=layout.pos.x,
            y=layout.pos.y,
            width=layout.width,
            fill_color=fill_color,
            stroke_color=ctx.palette.key_label_color,
            label_color=ctx.key_label_color(key, fill_color),
            font=Font.THUMB_KEY,
            font_height_multi=self.CONFIG.font_height_multiplier,
            use_system_fonts=ctx.use_system_fonts,
            **kwargs,
        )

    @property
    def aspect_ratio(self) -> AspectRatio:
        return self.CONFIG.aspect_ratio

    @property
    def shape(self) -> draw.DrawingElement:
        return Trapezoid(
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            bottom_width=self.width * self.CONFIG.trapezoid_small_face_multiplier,
            corners_radius=self.width * self.CONFIG.corner_radius_width_multiplier,
            align_x=Alignment.END if self.side == KeyboardSide.LEFT else Alignment.START,
            fill=self.fill_color,
        )

    @property
    def text_anchor(self) -> str:
        return "start" if self.side == KeyboardSide.LEFT else "end"

    @property
    def label_width(self) -> float:
        return self.width * self.CONFIG.label_width_multiplier

    @property
    def label_coordinates(self) -> tuple[float, float]:
        label_y = self.y + self.height / 2.0
        if self.side == KeyboardSide.LEFT:
            label_x = self.x + self.width * self.CONFIG.label_margin_size_multiplier
        else:
            label_x = self.x + self.width * (1.0 - self.CONFIG.label_margin_size_multiplier)
        return label_x, label_y


class CenterKey(Key):
    """The center key in a finger cluster.

    A circular key positioned at the center of the cluster.
    """

    CONFIG = KeyConfig(
        aspect_ratio=AspectRatio("1:1"),
        font_height_multiplier=0.6,
        label_width_multiplier=0.7,
    )

    def __init__(
        self,
        ctx: ClusterRenderContext,
        key: SvalboardTargetKey,
        colors: FingerClusterKeyColors,
        layout: Boundary,
        **kwargs,
    ):
        """Initialize a center key.

        Args:
            ctx: The cluster render context.
            key: The target key with label and layer info.
            colors: The color pair for this key.
            layout: The layout boundary for this key.
            **kwargs: Additional arguments passed to the parent Key.
        """
        fill_color = ctx.key_fill_color(key, colors.primary)
        super().__init__(
            label=key.label,
            x=layout.pos.x,
            y=layout.pos.y,
            width=layout.width,
            height=layout.width,
            fill_color=fill_color,
            stroke_color=ctx.palette.key_label_color,
            label_color=ctx.key_label_color(key, fill_color),
            font=Font.FINGER_KEY,
            font_height_multi=self.CONFIG.font_height_multiplier,
            use_system_fonts=ctx.use_system_fonts,
            **kwargs,
        )

    @property
    def aspect_ratio(self) -> AspectRatio:
        return self.CONFIG.aspect_ratio

    @property
    def shape(self) -> draw.DrawingElement:
        half_size = self.width / 2.0
        return draw.Circle(
            cx=self.x + half_size,
            cy=self.y + half_size,
            r=half_size,
            fill=self.fill_color,
        )

    @property
    def label_width(self) -> float:
        return self.width * self.CONFIG.label_width_multiplier

    @property
    def label_coordinates(self) -> tuple[float, float]:
        label_y = self.y + self.height / 2
        # label_y = self.y + self.height * 0.521
        label_x = self.x + self.width / 2
        return label_x, label_y


class DoubleSouthKey(Key):
    """The double-south key in a finger cluster.

    A square key with an accent bar at the top, positioned below the south key.
    """

    CONFIG = KeyConfig(
        aspect_ratio=AspectRatio("1:1"),
        font_height_multiplier=0.5,
        slant_size_multiplier=0.08,
        label_width_multiplier=0.7 - 0.08,
    )
    ACCENT_SIZE_MULTI = 0.15

    _accent_color: str

    def __init__(
        self,
        ctx: ClusterRenderContext,
        key: SvalboardTargetKey,
        colors: FingerClusterKeyColors,
        layout: Boundary,
        **kwargs,
    ):
        """Initialize a double-south key.

        Args:
            ctx: The cluster render context.
            key: The target key with label and layer info.
            colors: The color pair for this key.
            layout: The layout boundary for this key.
            **kwargs: Additional arguments passed to the parent Key.
        """
        self._accent_color = ctx.key_fill_color(key, colors.accent, True)
        fill_color = ctx.key_fill_color(key, colors.primary)
        super().__init__(
            label=key.label,
            x=layout.pos.x,
            y=layout.pos.y,
            width=layout.width,
            height=layout.width,
            fill_color=fill_color,
            stroke_color=ctx.palette.key_label_color,
            label_color=ctx.key_label_color(key, fill_color),
            font=Font.FINGER_KEY,
            font_height_multi=self.CONFIG.font_height_multiplier,
            use_system_fonts=ctx.use_system_fonts,
            **kwargs,
        )

    @property
    def aspect_ratio(self) -> AspectRatio:
        return self.CONFIG.aspect_ratio

    @property
    def shape(self) -> draw.DrawingElement:
        accent_size = self.width * self.ACCENT_SIZE_MULTI
        accent_radius_size = accent_size / 2.0
        group = draw.Group()
        group.append(
            Trapezoid(
                x=self.x,
                y=self.y,
                width=self.width,
                height=self.height,
                bottom_width=self.width * self.CONFIG.trapezoid_small_face_multiplier,
                corners_radius=accent_radius_size,
                fill=self.fill_color,
            )
        )

        group.append(
            draw.Rectangle(
                x=self.x,
                y=self.y,
                width=self.width,
                height=self.width * self.ACCENT_SIZE_MULTI,
                rx=accent_radius_size,
                ry=accent_radius_size,
                fill=self._accent_color,
            )
        )
        return group

    @property
    def label_width(self) -> float:
        return self.width * self.CONFIG.label_width_multiplier

    @property
    def label_coordinates(self) -> tuple[float, float]:
        label_y = (self.y + self.height / 2.0) + (self.width * self.ACCENT_SIZE_MULTI / 4.0)
        label_x = self.x + self.width / 2
        return label_x, label_y


class DirectionalKey(Key):
    """Unified directional key class for N/S/E/W finger cluster keys.

    Consolidates NorthKey, SouthKey, EastKey, WestKey into a single class
    that determines accent bar position based on the direction parameter.

    Attributes:
        _accent_color: The accent color for the directional bar.
        _direction: The direction (NORTH, SOUTH, EAST, WEST) for this key.
    """

    CONFIG = KeyConfig(
        aspect_ratio=AspectRatio("1:1"),
        font_height_multiplier=0.6,
        label_width_multiplier=0.8,
    )
    ACCENT_SIZE_MULTI = 0.15

    _accent_color: str
    _direction: KeyDirection

    def __init__(
        self,
        ctx: ClusterRenderContext,
        key: SvalboardTargetKey,
        colors: FingerClusterKeyColors,
        direction: KeyDirection,
        layout: Boundary,
        **kwargs,
    ):
        """Initialize a directional key.

        Args:
            ctx: The cluster render context.
            key: The target key with label and layer info.
            colors: The color pair for this key.
            direction: The direction (NORTH, SOUTH, EAST, WEST) for the accent bar.
            layout: The layout boundary for this key.
            **kwargs: Additional arguments passed to the parent Key.
        """
        self._direction = direction
        self._accent_color = ctx.key_fill_color(key, colors.accent, True)
        fill_color = ctx.key_fill_color(key, colors.primary)
        super().__init__(
            label=key.label,
            x=layout.pos.x,
            y=layout.pos.y,
            width=layout.width,
            height=layout.width,
            font=Font.FINGER_KEY,
            font_height_multi=self.CONFIG.font_height_multiplier,
            fill_color=fill_color,
            stroke_color=ctx.palette.key_label_color,
            label_color=ctx.key_label_color(key, fill_color),
            use_system_fonts=ctx.use_system_fonts,
            **kwargs,
        )

    @property
    def aspect_ratio(self) -> AspectRatio:
        return self.CONFIG.aspect_ratio

    @property
    def shape(self) -> draw.DrawingElement:
        accent_size = self.width * DirectionalKey.ACCENT_SIZE_MULTI
        accent_radius_size = accent_size / 2.0
        group = draw.Group()

        # Main rectangle
        group.append(
            draw.Rectangle(
                x=self.x,
                y=self.y,
                width=self.width,
                height=self.height,
                rx=accent_radius_size,
                ry=accent_radius_size,
                fill=self.fill_color,
            )
        )

        # Accent bar position depends on direction
        if self._direction == KeyDirection.NORTH:
            # Accent at bottom
            group.append(
                draw.Rectangle(
                    x=self.x,
                    y=self.y + self.height - accent_size,
                    width=self.width,
                    height=accent_size,
                    rx=accent_radius_size,
                    ry=accent_radius_size,
                    fill=self._accent_color,
                )
            )
        elif self._direction == KeyDirection.SOUTH:
            # Accent at top
            group.append(
                draw.Rectangle(
                    x=self.x,
                    y=self.y,
                    width=self.width,
                    height=accent_size,
                    rx=accent_radius_size,
                    ry=accent_radius_size,
                    fill=self._accent_color,
                )
            )
        elif self._direction == KeyDirection.EAST:
            # Accent at left
            group.append(
                draw.Rectangle(
                    x=self.x,
                    y=self.y,
                    width=accent_size,
                    height=self.height,
                    rx=accent_radius_size,
                    ry=accent_radius_size,
                    fill=self._accent_color,
                )
            )
        elif self._direction == KeyDirection.WEST:
            # Accent at right
            group.append(
                draw.Rectangle(
                    x=self.x + self.width - accent_size,
                    y=self.y,
                    width=accent_size,
                    height=self.height,
                    rx=accent_radius_size,
                    ry=accent_radius_size,
                    fill=self._accent_color,
                )
            )

        return group

    @property
    def label_width(self) -> float:
        if self._direction in (KeyDirection.EAST, KeyDirection.WEST):
            # Horizontal accent reduces label width
            return (
                self.width - self.width * DirectionalKey.ACCENT_SIZE_MULTI
            ) * self.CONFIG.label_width_multiplier
        return self.width * self.CONFIG.label_width_multiplier

    @property
    def label_coordinates(self) -> tuple[float, float]:
        accent_offset = self.width * DirectionalKey.ACCENT_SIZE_MULTI

        if self._direction == KeyDirection.NORTH:
            # Label shifted up
            label_y = (self.y + self.height / 2.0) - (accent_offset / 4.0)
            label_x = self.x + self.width / 2
        elif self._direction == KeyDirection.SOUTH:
            # Label shifted down
            label_y = (self.y + self.height / 2.0) + (accent_offset / 4.0)
            label_x = self.x + self.width / 2
        elif self._direction == KeyDirection.EAST:
            # Label shifted right
            label_y = self.y + self.height / 2.0
            label_x = (self.x + self.width / 2.0) + (accent_offset / 2.0)
        else:  # WEST
            # Label shifted left
            label_y = self.y + self.height / 2.0
            label_x = (self.x + self.width / 2.0) - (accent_offset / 2.0)

        return label_x, label_y
