# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Layer indicator rendering for keyboard visualization.

This module provides SVG components for rendering colored circle indicators
next to layer-switching keys, showing the target layer number with a
connector line linking the circle to its key.
"""

import math
from enum import Enum

import drawsvg as draw

from skim.data.config import Palette


class SVGGroup(draw.Group):
    """A drawsvg Group with an as_svg() convenience method."""

    def as_svg(self) -> str:
        """Return the SVG XML string for this group by wrapping in a Drawing."""
        d = draw.Drawing(0, 0)
        d.append(self)
        full = d.as_svg()
        # Extract just the content inside <svg>...</svg>
        start = full.find("<g")
        end = full.rfind("</g>") + len("</g>")
        if start != -1 and end > start:
            return full[start:end]
        return full


class OffsetDirection(Enum):
    """Direction to offset the indicator circle from its key."""

    ABOVE = "above"
    LEFT = "left"
    RIGHT = "right"
    DIAGONAL_LEFT = "diagonal_left"
    DIAGONAL_RIGHT = "diagonal_right"


class ConnectorType(Enum):
    """Type of connector line between circle and key."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    DIAGONAL = "diagonal"


_CONNECTOR_WIDTH = 2
_CIRCLE_STROKE_WIDTH = 2
_ENDPOINT_RADIUS = 2
_ENDPOINT_INSET = 4
_FALLBACK_FILL = "#808080"
_FALLBACK_STROKE = "#606060"


class LayerIndicator:
    """Renders a single layer indicator circle with connector line.

    The indicator consists of:
    - A filled circle with the target layer's base color
    - A 2px outline using the target layer's gradient[1]
    - A 0-indexed layer number label in white
    - A connector line from the circle edge to the key
    - A 4px endpoint circle drawn 4px inside the key boundary
    """

    def __init__(
        self,
        key_x: float,
        key_y: float,
        key_width: float,
        key_height: float,
        target_layer: int,
        palette: Palette,
        circle_diameter: float,
        gap: float,
        offset_direction: OffsetDirection,
        connector_type: ConnectorType,
    ) -> None:
        self._key_x = key_x
        self._key_y = key_y
        self._key_width = key_width
        self._key_height = key_height
        self._target_layer = target_layer
        self._palette = palette
        self._radius = circle_diameter / 2
        self._gap = gap
        self._offset_direction = offset_direction
        self._connector_type = connector_type

        # Resolve colors
        if 0 <= target_layer < len(palette.layers):
            lc = palette.layers[target_layer]
            self._fill_color = lc.base_color
            self._stroke_color = lc[1]
        else:
            self._fill_color = _FALLBACK_FILL
            self._stroke_color = _FALLBACK_STROKE

        # Compute positions
        self._compute_circle_center()
        self._compute_connector()

    @property
    def circle_center_x(self) -> float:
        return self._cx

    @property
    def circle_center_y(self) -> float:
        return self._cy

    def _compute_circle_center(self) -> None:
        key_cx = self._key_x + self._key_width / 2
        key_cy = self._key_y + self._key_height / 2
        r = self._radius

        match self._offset_direction:
            case OffsetDirection.ABOVE:
                self._cx = key_cx
                self._cy = self._key_y - self._gap - r
            case OffsetDirection.LEFT:
                self._cx = self._key_x - self._gap - r
                self._cy = key_cy
            case OffsetDirection.RIGHT:
                self._cx = self._key_x + self._key_width + self._gap + r
                self._cy = key_cy
            case OffsetDirection.DIAGONAL_RIGHT:
                dist = self._key_width / 2 + self._gap + r
                offset = dist / math.sqrt(2)
                self._cx = key_cx + offset
                self._cy = key_cy + offset
            case OffsetDirection.DIAGONAL_LEFT:
                dist = self._key_width / 2 + self._gap + r
                offset = dist / math.sqrt(2)
                self._cx = key_cx - offset
                self._cy = key_cy + offset

    def _compute_connector(self) -> None:
        """Compute connector line start (circle edge) and end (inside key)."""
        key_cx = self._key_x + self._key_width / 2
        key_cy = self._key_y + self._key_height / 2

        match self._connector_type:
            case ConnectorType.VERTICAL:
                self._line_x1 = self._cx
                self._line_y1 = self._cy + self._radius
                self._line_x2 = self._cx
                self._line_y2 = self._key_y
                self._ep_x = self._cx
                self._ep_y = self._key_y + _ENDPOINT_INSET
            case ConnectorType.HORIZONTAL:
                if self._offset_direction == OffsetDirection.LEFT:
                    self._line_x1 = self._cx + self._radius
                    self._line_y1 = self._cy
                    self._line_x2 = self._key_x
                    self._line_y2 = self._cy
                    self._ep_x = self._key_x + _ENDPOINT_INSET
                    self._ep_y = self._cy
                else:
                    self._line_x1 = self._cx - self._radius
                    self._line_y1 = self._cy
                    self._line_x2 = self._key_x + self._key_width
                    self._line_y2 = self._cy
                    self._ep_x = self._key_x + self._key_width - _ENDPOINT_INSET
                    self._ep_y = self._cy
            case ConnectorType.DIAGONAL:
                cos45 = math.cos(math.pi / 4)
                sin45 = math.sin(math.pi / 4)
                if self._offset_direction == OffsetDirection.DIAGONAL_RIGHT:
                    self._line_x1 = self._cx - self._radius * cos45
                    self._line_y1 = self._cy - self._radius * sin45
                    self._line_x2 = key_cx + _ENDPOINT_INSET * cos45
                    self._line_y2 = key_cy + _ENDPOINT_INSET * sin45
                else:
                    self._line_x1 = self._cx + self._radius * cos45
                    self._line_y1 = self._cy - self._radius * sin45
                    self._line_x2 = key_cx - _ENDPOINT_INSET * cos45
                    self._line_y2 = key_cy + _ENDPOINT_INSET * sin45
                self._ep_x = self._line_x2
                self._ep_y = self._line_y2

    def build(self) -> SVGGroup:
        """Build the SVG group containing the indicator."""
        g = SVGGroup()

        g.append(draw.Raw(
            f'<line x1="{self._line_x1}" y1="{self._line_y1}"'
            f' x2="{self._line_x2}" y2="{self._line_y2}"'
            f' stroke="{self._stroke_color}" stroke-width="{_CONNECTOR_WIDTH}" />'
        ))

        g.append(draw.Circle(
            self._ep_x, self._ep_y,
            _ENDPOINT_RADIUS,
            fill=self._stroke_color,
        ))

        g.append(draw.Circle(
            self._cx, self._cy,
            self._radius,
            fill=self._fill_color,
            stroke=self._stroke_color,
            stroke_width=_CIRCLE_STROKE_WIDTH,
        ))

        g.append(draw.Text(
            str(self._target_layer),
            font_size=self._radius * 1.2,
            x=self._cx,
            y=self._cy,
            fill="white",
            text_anchor="middle",
            dominant_baseline="central",
            font_family="Roboto, sans-serif",
            font_weight="bold",
        ))

        return g
