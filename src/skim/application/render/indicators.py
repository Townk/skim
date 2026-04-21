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
from skim.data.keyboard import FingerCluster, ThumbCluster
from skim.domain.domain_types import KeyboardSide, SvalboardTargetKey

from .layout import Boundary


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
        connector_target_y: float | None = None,
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
        self._connector_target_y = connector_target_y

        # Resolve colors
        if 0 <= target_layer < len(palette.layers):
            lc = palette.layers[target_layer]
            self._fill_color = lc.base_color
            self._stroke_color = lc[4]
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
                # connector_target_y overrides where the endpoint lands
                # (used for DD key where circle is above Down but endpoint is in DD)
                target_y = self._connector_target_y if self._connector_target_y is not None else self._key_y
                self._line_x1 = self._cx
                self._line_y1 = self._cy + self._radius
                self._line_x2 = self._cx
                self._line_y2 = target_y + _ENDPOINT_INSET
                self._ep_x = self._cx
                self._ep_y = target_y + _ENDPOINT_INSET
            case ConnectorType.HORIZONTAL:
                if self._offset_direction == OffsetDirection.LEFT:
                    self._line_x1 = self._cx + self._radius
                    self._line_y1 = self._cy
                    self._line_x2 = self._key_x + _ENDPOINT_INSET
                    self._line_y2 = self._cy
                    self._ep_x = self._key_x + _ENDPOINT_INSET
                    self._ep_y = self._cy
                else:
                    self._line_x1 = self._cx - self._radius
                    self._line_y1 = self._cy
                    self._line_x2 = self._key_x + self._key_width - _ENDPOINT_INSET
                    self._line_y2 = self._cy
                    self._ep_x = self._key_x + self._key_width - _ENDPOINT_INSET
                    self._ep_y = self._cy
            case ConnectorType.DIAGONAL:
                cos45 = math.cos(math.pi / 4)
                sin45 = math.sin(math.pi / 4)
                # Endpoint is 4px inside the key's edge, not from its center.
                # For the circular center key, edge is at key_width/2 from center.
                key_edge_r = self._key_width / 2
                inset_r = key_edge_r - _ENDPOINT_INSET
                if self._offset_direction == OffsetDirection.DIAGONAL_RIGHT:
                    self._line_x1 = self._cx - self._radius * cos45
                    self._line_y1 = self._cy - self._radius * sin45
                    self._line_x2 = key_cx + inset_r * cos45
                    self._line_y2 = key_cy + inset_r * sin45
                else:
                    self._line_x1 = self._cx + self._radius * cos45
                    self._line_y1 = self._cy - self._radius * sin45
                    self._line_x2 = key_cx - inset_r * cos45
                    self._line_y2 = key_cy + inset_r * sin45
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


def _finger_cluster_offset(
    key_name: str, side: KeyboardSide
) -> tuple[OffsetDirection, ConnectorType]:
    """Get the offset direction and connector type for a finger cluster key."""
    match key_name:
        case "north_key" | "east_key" | "west_key":
            return OffsetDirection.ABOVE, ConnectorType.VERTICAL
        case "center_key":
            if side == KeyboardSide.LEFT:
                return OffsetDirection.DIAGONAL_RIGHT, ConnectorType.DIAGONAL
            return OffsetDirection.DIAGONAL_LEFT, ConnectorType.DIAGONAL
        case "south_key" | "double_south_key":
            if side == KeyboardSide.LEFT:
                return OffsetDirection.LEFT, ConnectorType.HORIZONTAL
            return OffsetDirection.RIGHT, ConnectorType.HORIZONTAL
        case _:
            return OffsetDirection.ABOVE, ConnectorType.VERTICAL


_FINGER_KEY_NAMES = [
    "center_key", "north_key", "east_key", "south_key", "west_key", "double_south_key"
]


def _thumb_cluster_offset(
    key_name: str, side: KeyboardSide
) -> tuple[OffsetDirection, ConnectorType]:
    """Get the offset direction and connector type for a thumb cluster key."""
    is_left = side == KeyboardSide.LEFT
    outward = OffsetDirection.LEFT if is_left else OffsetDirection.RIGHT
    inward = OffsetDirection.RIGHT if is_left else OffsetDirection.LEFT

    match key_name:
        case "pad_key" | "up_key" | "down_key":
            return outward, ConnectorType.HORIZONTAL
        case "nail_key" | "knuckle_key":
            return inward, ConnectorType.HORIZONTAL
        case "double_down_key":
            return OffsetDirection.ABOVE, ConnectorType.VERTICAL
        case _:
            return outward, ConnectorType.HORIZONTAL


_THUMB_KEY_NAMES = [
    "down_key", "pad_key", "up_key", "nail_key", "knuckle_key", "double_down_key"
]

# Thumb key aspect ratios expressed as height_per_width (height = width * ratio)
_THUMB_KEY_HEIGHT_RATIOS: dict[str, float] = {
    "down_key": 2.6,
    "pad_key": 1 / 1.85,
    "up_key": 1 / 2.75,
    "nail_key": 1 / 1.95,
    "knuckle_key": 1 / 1.87,
    "double_down_key": 1.1,
}


class LayerIndicatorOverlay:
    """Orchestrates drawing layer indicators for an entire cluster."""

    def __init__(self, indicators: list[LayerIndicator]) -> None:
        self._indicators = indicators

    def build(self) -> list[SVGGroup]:
        """Build all indicator SVG groups."""
        return [ind.build() for ind in self._indicators]

    @classmethod
    def for_finger_cluster(
        cls,
        keys: FingerCluster[SvalboardTargetKey],
        metrics: FingerCluster[Boundary],
        side: KeyboardSide,
        palette: Palette,
        circle_diameter: float,
        gap: float,
        has_double_south: bool,
    ) -> "LayerIndicatorOverlay":
        """Create an overlay for a finger cluster."""
        indicators: list[LayerIndicator] = []

        for key_name in _FINGER_KEY_NAMES:
            if key_name == "double_south_key" and not has_double_south:
                continue

            key: SvalboardTargetKey = getattr(keys, key_name)
            if key.layer_switch is None:
                continue

            layout: Boundary = getattr(metrics, key_name)
            offset_dir, conn_type = _finger_cluster_offset(key_name, side)

            # Center key needs a larger gap so the diagonal circle clears
            # adjacent keys (E/W and S)
            key_gap = gap * 3 if key_name == "center_key" else gap

            indicators.append(LayerIndicator(
                key_x=layout.pos.x,
                key_y=layout.pos.y,
                key_width=layout.width,
                key_height=layout.width,  # finger cluster keys are square
                target_layer=key.layer_switch,
                palette=palette,
                circle_diameter=circle_diameter,
                gap=key_gap,
                offset_direction=offset_dir,
                connector_type=conn_type,
            ))

        return cls(indicators)

    @classmethod
    def for_thumb_cluster(
        cls,
        keys: ThumbCluster[SvalboardTargetKey],
        metrics: ThumbCluster[Boundary],
        down_key_metrics: Boundary,
        side: KeyboardSide,
        palette: Palette,
        circle_diameter: float,
        gap: float,
    ) -> "LayerIndicatorOverlay":
        """Create an overlay for a thumb cluster."""
        indicators: list[LayerIndicator] = []

        # Pre-compute UP and PAD circle center Ys to position the Down key
        # circle relative to them (avoids overlap with other keys).
        up_layout = metrics.up_key
        up_h = up_layout.width * _THUMB_KEY_HEIGHT_RATIOS["up_key"]
        up_circle_cy = up_layout.pos.y + up_h / 2.0

        pad_layout = metrics.pad_key
        pad_h = pad_layout.width * _THUMB_KEY_HEIGHT_RATIOS["pad_key"]
        pad_circle_cy = pad_layout.pos.y + pad_h / 2.0

        # Down circle Y = up_circle_cy + (up_circle_cy - pad_circle_cy)
        down_target_cy = up_circle_cy + (up_circle_cy - pad_circle_cy)

        for key_name in _THUMB_KEY_NAMES:
            key: SvalboardTargetKey = getattr(keys, key_name)
            if key.layer_switch is None:
                continue

            layout: Boundary = getattr(metrics, key_name)
            offset_dir, conn_type = _thumb_cluster_offset(key_name, side)

            # DD: circle position gap is measured from Down key's top edge,
            # but the connector endpoint goes into the DD key itself.
            if key_name == "double_down_key":
                ref_y = down_key_metrics.pos.y
                ref_height = layout.width * _THUMB_KEY_HEIGHT_RATIOS.get("down_key", 1.0)
                connector_target_y = layout.pos.y  # DD key's actual y
            elif key_name == "down_key":
                # Position the circle at down_target_cy instead of the
                # key's vertical center to avoid overlapping adjacent keys.
                # We achieve this by setting ref_y and ref_height so that
                # ref_y + ref_height/2 == down_target_cy.
                ref_height = layout.width * _THUMB_KEY_HEIGHT_RATIOS["down_key"]
                ref_y = down_target_cy - ref_height / 2.0
                connector_target_y = None
            else:
                ref_y = layout.pos.y
                ref_height = layout.width * _THUMB_KEY_HEIGHT_RATIOS.get(key_name, 1.0)
                connector_target_y = None

            indicators.append(LayerIndicator(
                key_x=layout.pos.x,
                key_y=ref_y,
                key_width=layout.width,
                key_height=ref_height,
                target_layer=key.layer_switch,
                palette=palette,
                circle_diameter=circle_diameter,
                gap=gap,
                offset_direction=offset_dir,
                connector_type=conn_type,
                connector_target_y=connector_target_y,
            ))

        return cls(indicators)
