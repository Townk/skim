# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable building blocks for individual Svalboard keys.

Each key composable is a pure component that takes resolved inputs
(width, label text, fill / label colours) and reports a typed
``Size`` plus :class:`SvalboardKeyMetrics`. Cluster-level resolution
lives one layer up; the key composable doesn't reach for
context-derived state beyond ``ctx.config.output.style.use_system_fonts``.

Key text renders through :func:`RichText` — the same multi-span
text composable the macros / tap-dances / symbols sections use —
so labels with Nerd Font tokens land on the right per-span fonts
and a long label shrinks to fit via the relaxation loop.
"""

from __future__ import annotations

from dataclasses import dataclass

import drawsvg as draw

from .composable import Composable
from .primitives import CompassDirection, MetricsComponent, Point, Size
from .render_context import TextStyle
from .rich_text import RichText, parse_into_spans
from .text import Font


@dataclass(frozen=True, slots=True, kw_only=True)
class SvalboardKeyMetrics:
    """Metrics exposed by every Svalboard-key composable.

    Surfaces the geometry the cluster needs to lay out a layer
    indicator around the key:

    * :attr:`indicator_anchor` — where the connector line should
      attach to the key, in coordinates relative to the key's
      origin. The cluster computes the indicator-circle position,
      offsets back toward the anchor, and routes a line from circle
      edge to (anchor minus a small inset) so the line lands on the
      key's outline.
    * :attr:`indicator_direction` — the compass octant the indicator
      sits in relative to the key. The cluster reads this to pick
      the connector's offset rule (vertical / horizontal / diagonal)
      without re-deriving it from the key's shape.

    Routing the indicator concern through metrics keeps the key
    composable itself focused on shape + label — the cluster-level
    indicator code is the consumer.
    """

    indicator_anchor: Point
    indicator_direction: CompassDirection


# ---------------------------------------------------------------------------
# Per-key sizing constants — kept inline alongside the composable they
# apply to so each key shape stays self-contained. ``WIDTH_MULTIPLIER``
# values are fractions of the cell width; ``FONT_HEIGHT_MULTIPLIER`` is the
# label's natural font size as a fraction of the cell height (RichText
# shrinks below this when the label wouldn't fit at that size).
# ---------------------------------------------------------------------------

# CenterKey
_CENTER_FONT_HEIGHT_MULTIPLIER = 0.6
_CENTER_LABEL_WIDTH_MULTIPLIER = 0.7
# A circle's SW edge sits at angle 225° from the centre — same point on
# the perimeter regardless of size. Cached as a unit-vector offset
# (``(W/2 + dx*r, W/2 + dy*r)`` where ``r = W/2``) so the metrics
# computation stays a simple multiply.
_SQRT_HALF = 0.7071067811865476  # 1 / sqrt(2)


@Composable(use_context=True)
def CenterKey(
    ctx,
    *,
    width: float,
    label_text: str,
    fill_color: str,
    label_color: str,
):
    """The center key of a finger cluster — a filled circle with a label.

    Reports ``Size(width, width)`` (the key is square-bounded; the
    circle inscribes that bbox) and :class:`SvalboardKeyMetrics`
    with the SW-corner indicator anchor (the cluster on a left-hand
    keyboard mirrors the side externally — the metrics describe the
    key's natural / right-hand orientation).

    Inputs are pre-resolved by the caller:

    * ``width`` — the cluster has already chosen the cell size.
    * ``label_text`` — the parsed-target-key's display label
      (the cluster reads this off ``SvalboardTargetKey.label``).
    * ``fill_color`` — already gone through ``key_fill_color`` so
      transparent / filled / accented variants land at the right
      colour.
    * ``label_color`` — already through ``key_label_color`` so the
      contrast pick is the cluster's concern, not the key's.
    """
    use_system_fonts = ctx.config.output.style.use_system_fonts
    del use_system_fonts  # RichText reads the flag from ctx itself.

    half = width / 2.0
    label_width_budget = width * _CENTER_LABEL_WIDTH_MULTIPLIER
    label_font_size = width * _CENTER_FONT_HEIGHT_MULTIPLIER

    # The cluster on a right-hand keyboard places the indicator at
    # the key's SW (lower-left); a left-hand cluster mirrors. Spell
    # the natural orientation here; mirroring is the cluster's job.
    inset_x = half * _SQRT_HALF
    inset_y = half * _SQRT_HALF
    indicator_anchor = Point(half - inset_x, half + inset_y)

    # ``min_font_size=1`` lets the relaxation shrink the label as
    # far as needed to fit the cell. Without it RichText pins at
    # the natural size and drops the label to ``…`` when wider
    # than the budget — wrong for key cells, where shrinking is
    # the correct overflow response.
    label_style = TextStyle(font=Font.FINGER_KEY, size=label_font_size, color=label_color)
    label_el = RichText(
        spans=parse_into_spans(label_text, label_style),
        style=label_style,
        max_width=label_width_budget,
        min_font_size=1.0,
        text_anchor="middle",
        dominant_baseline="central",
        separator="",
    )

    size = Size(width, width)

    def draw_at(d, origin):
        cx = origin.x + half
        cy = origin.y + half
        d.append(draw.Circle(cx=cx, cy=cy, r=half, fill=fill_color))
        # RichText paints from its bbox top-left; centre the bbox on
        # (cx, cy) so ``text_anchor="middle"`` + ``dominant_baseline="central"``
        # land the rendered glyphs at the key's centre.
        label_origin = Point(
            cx - label_el.size.width / 2,
            cy - label_el.size.height / 2,
        )
        label_el.draw_at(d, label_origin)

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=SvalboardKeyMetrics(
            indicator_anchor=indicator_anchor,
            indicator_direction=CompassDirection.SOUTH_WEST,
        ),
    )


__all__ = [
    "CenterKey",
    "SvalboardKeyMetrics",
]
