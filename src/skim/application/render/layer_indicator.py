# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Layer-indicator composable — the small badge that marks a layer-switch key.

A :func:`LayerIndicator` paints next to a Svalboard key whose
``layer_switch`` is set: a coloured circle bearing the target
layer's number, plus a connector line tying the circle back to the
key's edge. The circle's position and the connector's geometry are
both derived from the key's :class:`SvalboardKeyMetrics` —
specifically ``indicator_anchor`` (the point on the key's edge
where the connector terminates) and ``indicator_direction`` (the
compass octant the indicator sits in relative to the key).

The composable is intentionally side-agnostic. Side-aware logic
lives on the key composable: the key reports its anchor +
direction in the orientation that matches its keyboard half. The
indicator just consumes those values.

Reports :class:`MetricsComponent[LayerIndicatorMetrics]` exposing
the geometry the cluster + overview routing layers need to do
their jobs without re-deriving it:

* The circle's bbox — the cluster reads this when deciding how
  far to shift its outer bounds to make room for indicators that
  protrude past the cluster edge.
* The routing-line origin + initial direction — where the
  overview-image's connector lines start and which way they head
  out of the indicator. The overview's routing code consumes
  these instead of computing the same geometry from the
  indicator's own internals.
"""

from __future__ import annotations

from dataclasses import dataclass

import drawsvg as draw

from .composable import Composable
from .font import Font
from .primitives import CompassDirection, MetricsComponent, Point, Size
from .render_context import TextStyle
from .rich_text import RichText

# ---------------------------------------------------------------------------
# Per-doc-width chrome ratios — connector / endpoint / circle stroke.
# Expressed as fractions of the document width so the rendered
# indicator chrome stays visually proportional across canvas sizes.
# ---------------------------------------------------------------------------

_CONNECTOR_WIDTH_RATIO = 2.0 / 1600.0
_CIRCLE_STROKE_WIDTH_RATIO = 2.0 / 1600.0
_ENDPOINT_RADIUS_RATIO = 2.0 / 1600.0
_ENDPOINT_INSET_RATIO = 4.0 / 1600.0

# Layer-number text inside the circle — sized as a multiple of the
# circle's radius so the digit always reads the same proportion of the
# badge regardless of badge diameter.
_LABEL_FONT_SIZE_RADIUS_MULTIPLIER = 1.2


@dataclass(frozen=True, slots=True, kw_only=True)
class LayerIndicatorMetrics:
    """Geometry the cluster + overview routing read off a built indicator.

    All coordinates are in the same frame as the indicator's
    ``draw_at`` origin — i.e., relative to the key's origin (the
    cluster passes the key origin through to the indicator so the
    anchor stays in key-local coords).

    Attributes
    ----------
    circle_center : Point
        Centre of the indicator circle. Combined with
        :attr:`circle_radius` the cluster can compute the badge's
        bbox to decide how far to shift outward to keep it on-canvas.
    circle_radius : float
        Half the circle's diameter. Pulled out as its own field so
        the cluster doesn't have to recover it from the bbox.
    routing_origin : Point
        Where an outward-routing line should begin — the circle's
        edge on the side OPPOSITE the connector to the key. The
        overview image's connector router starts paths from here.
    routing_direction : CompassDirection
        The initial heading of an outward routing line — the same
        compass octant the indicator sits in relative to its key.
        ``CompassDirection.NORTH`` for an above-the-key indicator,
        ``EAST`` for a right-of-key indicator, etc.
    """

    circle_center: Point
    circle_radius: float
    routing_origin: Point
    routing_direction: CompassDirection


@Composable(use_context=True)
def LayerIndicator(
    ctx,
    *,
    target_layer: int,
    anchor: Point,
    direction: CompassDirection,
    circle_diameter: float,
    gap: float,
    fill_color: str,
    stroke_color: str,
    label_color: str = "white",
):
    """Layer-indicator badge — circle + label + connector to its key.

    Reports ``Size(0, 0)`` because the indicator is *annotation* on
    a key that already claimed cluster layout space; the cluster
    paints both at the same origin and reads
    :class:`LayerIndicatorMetrics` to know where the indicator
    actually sits on the canvas (and therefore how far the cluster
    needs to shift to keep the indicator on-canvas).

    Inputs are pre-resolved by the caller:

    * ``target_layer`` — the layer index to show inside the badge.
      Painted as a string in :data:`label_color`.
    * ``anchor`` / ``direction`` — read off the key's
      :class:`SvalboardKeyMetrics`. ``anchor`` is in coords
      relative to the key origin; ``direction`` is the compass
      octant the indicator sits in.
    * ``circle_diameter`` / ``gap`` — cluster-decided sizing.
    * ``fill_color`` / ``stroke_color`` / ``label_color`` —
      already resolved from the palette by the cluster, so the
      indicator doesn't need to know about layer palettes.
    """
    radius = circle_diameter / 2.0
    doc_width = ctx.config.output.layout.width
    connector_width = doc_width * _CONNECTOR_WIDTH_RATIO
    circle_stroke_width = doc_width * _CIRCLE_STROKE_WIDTH_RATIO
    endpoint_radius = doc_width * _ENDPOINT_RADIUS_RATIO
    endpoint_inset = doc_width * _ENDPOINT_INSET_RATIO

    # The circle's centre sits ``gap + radius`` away from the
    # anchor along ``direction``. The unit vector of the direction
    # gives the per-axis offset; for diagonals it normalises to
    # ``±1/√2`` so the centre is the right radial distance from
    # the anchor (not √2× more).
    dx, dy = direction.unit_vector
    distance = gap + radius
    circle_center = Point(anchor.x + distance * dx, anchor.y + distance * dy)

    # The connector runs from the circle's edge nearest the anchor
    # to a point just inside the key (insetted along the same
    # direction so the line visually lands on the key's outline,
    # not exactly on top of it).
    line_start = Point(
        circle_center.x - radius * dx,
        circle_center.y - radius * dy,
    )
    line_end = Point(
        anchor.x - endpoint_inset * dx,
        anchor.y - endpoint_inset * dy,
    )

    # The routing line — for the overview image's connector paths —
    # departs from the circle's edge on the side OPPOSITE the key,
    # heading further out in the same compass direction.
    routing_origin = Point(
        circle_center.x + radius * dx,
        circle_center.y + radius * dy,
    )

    # Layer-number label — centred in the circle. RichText handles
    # the relaxation if the digit count outgrows the natural font
    # size; in practice layer numbers are 1–2 digits and never
    # trigger the shrink path.
    label_text = str(target_layer)
    label_font_size = radius * _LABEL_FONT_SIZE_RADIUS_MULTIPLIER
    label_style = TextStyle(font=Font.FINGER_KEY, size=label_font_size, color=label_color)
    label_el = RichText(
        text=label_text,
        style=label_style,
        max_width=circle_diameter * 0.8,
        min_font_size=1.0,
        text_anchor="middle",
        dominant_baseline="central",
    )

    # The indicator is annotation: it doesn't claim layout space.
    # The cluster lays the key out, then paints the indicator at
    # the same origin; ``draw_at`` paints both the key edge-piece
    # (line + endpoint) and the badge.
    size = Size(0.0, 0.0)

    def draw_at(d, origin):
        cx = origin.x + circle_center.x
        cy = origin.y + circle_center.y
        # 1. Connector line — drawn first so it sits beneath the
        # circle and endpoint.
        d.append(
            draw.Line(
                sx=origin.x + line_start.x,
                sy=origin.y + line_start.y,
                ex=origin.x + line_end.x,
                ey=origin.y + line_end.y,
                stroke=stroke_color,
                stroke_width=connector_width,
            )
        )
        # 2. Endpoint marker — small filled circle just inside the
        # key boundary.
        d.append(
            draw.Circle(
                cx=origin.x + line_end.x,
                cy=origin.y + line_end.y,
                r=endpoint_radius,
                fill=stroke_color,
            )
        )
        # 3. Indicator circle — fill + stroke.
        d.append(
            draw.Circle(
                cx=cx,
                cy=cy,
                r=radius,
                fill=fill_color,
                stroke=stroke_color,
                stroke_width=circle_stroke_width,
            )
        )
        # 4. Layer-number label centred on the circle.
        label_origin = Point(
            cx - label_el.size.width / 2.0,
            cy - label_el.size.height / 2.0,
        )
        label_el.draw_at(d, label_origin)

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=LayerIndicatorMetrics(
            circle_center=circle_center,
            circle_radius=radius,
            routing_origin=routing_origin,
            routing_direction=direction,
        ),
    )


__all__ = [
    "LayerIndicator",
    "LayerIndicatorMetrics",
]
