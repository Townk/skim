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

from skim.domain import KeyboardSide, KeyDirection

from .composable import Composable
from .geometry import Trapezoid
from .primitives import CompassDirection, MetricsComponent, Point, Size
from .render_context import TextStyle
from .rich_text import RichText, parse_into_spans
from .text import Font


def _mirror_metrics(
    *, anchor: Point, direction: CompassDirection, width: float, side: KeyboardSide
) -> tuple[Point, CompassDirection]:
    """Reflect ``(anchor, direction)`` across the key's vertical centre
    when ``side == LEFT``.

    The Svalboard's two halves are mirror images of each other, and the
    layer-indicator badge sits on the cluster-outward / cluster-inward
    edge accordingly. Each per-shape composable defines its anchor +
    direction in the right-hand reference orientation; this helper does
    the side-aware flip in one place so the composables don't each
    re-spell the mapping.
    """
    if side is KeyboardSide.RIGHT:
        return anchor, direction
    return Point(width - anchor.x, anchor.y), direction.mirrored_horizontal


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

# DirectionalKey (NORTH / SOUTH / EAST / WEST finger-cluster keys)
_DIRECTIONAL_FONT_HEIGHT_MULTIPLIER = 0.6
_DIRECTIONAL_LABEL_WIDTH_MULTIPLIER = 0.8
# Accent bar thickness, as a fraction of the cell width. The bar sits
# on the edge OPPOSITE the direction the key represents (NORTH key →
# bar on the south edge, etc.) so the unaccented edge points toward
# the cluster centre.
_DIRECTIONAL_ACCENT_SIZE_MULTIPLIER = 0.15

# DoubleSouthKey (the squat trapezoid that sits below the south key)
_DOUBLE_SOUTH_FONT_HEIGHT_MULTIPLIER = 0.5
# Trapezoid bottom is narrower than the top by this much (in cell-width
# fractions); ``bottom_width = width * (1 - slant)``.
_DOUBLE_SOUTH_SLANT_MULTIPLIER = 0.08
_DOUBLE_SOUTH_LABEL_WIDTH_MULTIPLIER = 0.7 - _DOUBLE_SOUTH_SLANT_MULTIPLIER
_DOUBLE_SOUTH_ACCENT_SIZE_MULTIPLIER = 0.15


@Composable(use_context=True)
def CenterKey(
    ctx,
    *,
    side: KeyboardSide,
    width: float,
    label_text: str,
    fill_color: str,
    label_color: str,
):
    """The center key of a finger cluster — a filled circle with a label.

    Reports ``Size(width, width)`` (the key is square-bounded; the
    circle inscribes that bbox) and :class:`SvalboardKeyMetrics`
    with the diagonal-toward-thumb indicator anchor — ``SOUTH_WEST``
    on the right hand, ``SOUTH_EAST`` on the left.

    Inputs are pre-resolved by the caller:

    * ``side`` — which half of the keyboard this key renders for.
      The shape is symmetric (a circle) so the drawing doesn't
      change; the indicator metrics flip horizontally.
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

    # Right-hand reference: indicator at the key's SW (lower-left,
    # toward the thumb). The mirror helper flips for the left hand.
    inset_x = half * _SQRT_HALF
    inset_y = half * _SQRT_HALF
    indicator_anchor, indicator_direction = _mirror_metrics(
        anchor=Point(half - inset_x, half + inset_y),
        direction=CompassDirection.SOUTH_WEST,
        width=width,
        side=side,
    )

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
            indicator_direction=indicator_direction,
        ),
    )


@Composable(use_context=True)
def DirectionalKey(
    ctx,
    *,
    side: KeyboardSide,
    direction: KeyDirection,
    width: float,
    label_text: str,
    fill_color: str,
    accent_color: str,
    label_color: str,
):
    """One of the four directional keys around a finger-cluster centre.

    Renders a rounded square (``width × width``) with a coloured
    accent bar on the edge OPPOSITE ``direction`` — a NORTH key's
    bar sits on the south edge, an EAST key's bar on the west edge,
    etc. — so the unaccented edge always points toward the cluster
    centre. Shape and accent placement are symmetric across the two
    keyboard halves; only the indicator metrics flip per side.

    Reports :class:`SvalboardKeyMetrics`. ``NORTH`` / ``EAST`` /
    ``WEST`` carry the indicator above the key on both sides
    (``CompassDirection.NORTH``, anchor at the top-edge midpoint).
    ``SOUTH`` carries it on the outward (away-from-thumb) side —
    ``EAST`` on the right hand, ``WEST`` on the left — with the
    anchor at the corresponding edge's vertical centre.

    The label sits at the cell centre, nudged a fraction toward the
    unaccented edge so the accent bar doesn't visually crowd it. East
    and west variants reduce the label's width budget to account for
    the side-mounted accent bar eating horizontal space.
    """
    del ctx  # RichText reads ``use_system_fonts`` from its own ctx.

    half = width / 2.0
    accent_size = width * _DIRECTIONAL_ACCENT_SIZE_MULTIPLIER
    accent_radius = accent_size / 2.0
    label_font_size = width * _DIRECTIONAL_FONT_HEIGHT_MULTIPLIER

    # Side-mounted accents (E / W) eat horizontal space, so the label
    # budget shrinks accordingly. N / S accents are vertical and don't
    # reduce horizontal text room.
    if direction in (KeyDirection.EAST, KeyDirection.WEST):
        label_width_budget = (width - accent_size) * _DIRECTIONAL_LABEL_WIDTH_MULTIPLIER
    else:
        label_width_budget = width * _DIRECTIONAL_LABEL_WIDTH_MULTIPLIER

    # Label position — nudged a quarter of an accent-size away from
    # the bar so the accent doesn't visually crowd the glyphs.
    label_offset = accent_size / 4.0
    if direction == KeyDirection.NORTH:
        label_dx, label_dy = 0.0, -label_offset
    elif direction == KeyDirection.SOUTH:
        label_dx, label_dy = 0.0, label_offset
    elif direction == KeyDirection.EAST:
        label_dx, label_dy = accent_size / 2.0, 0.0
    else:  # WEST
        label_dx, label_dy = -accent_size / 2.0, 0.0

    # Right-hand reference indicator metrics. N / E / W carry the
    # indicator above the key (no horizontal flip when mirrored); S
    # carries it on the outward / east edge — flipped to west for the
    # left hand by the mirror helper.
    if direction == KeyDirection.SOUTH:
        ref_anchor = Point(width, half)
        ref_direction = CompassDirection.EAST
    else:
        ref_anchor = Point(half, 0.0)
        ref_direction = CompassDirection.NORTH
    indicator_anchor, indicator_direction = _mirror_metrics(
        anchor=ref_anchor, direction=ref_direction, width=width, side=side
    )

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
        x, y = origin.x, origin.y
        # Main rounded rect — ``rx`` / ``ry`` use ``accent_radius`` so
        # the corner curvature matches the accent bar's rounding;
        # the bar tucks into the corners cleanly.
        d.append(
            draw.Rectangle(
                x=x,
                y=y,
                width=width,
                height=width,
                rx=accent_radius,
                ry=accent_radius,
                fill=fill_color,
            )
        )
        # Accent bar on the edge opposite the key's direction.
        if direction == KeyDirection.NORTH:
            bar_x, bar_y = x, y + width - accent_size
            bar_w, bar_h = width, accent_size
        elif direction == KeyDirection.SOUTH:
            bar_x, bar_y = x, y
            bar_w, bar_h = width, accent_size
        elif direction == KeyDirection.EAST:
            bar_x, bar_y = x, y
            bar_w, bar_h = accent_size, width
        else:  # WEST
            bar_x, bar_y = x + width - accent_size, y
            bar_w, bar_h = accent_size, width
        d.append(
            draw.Rectangle(
                x=bar_x,
                y=bar_y,
                width=bar_w,
                height=bar_h,
                rx=accent_radius,
                ry=accent_radius,
                fill=accent_color,
            )
        )
        # Label centred + nudged.
        cx = x + half + label_dx
        cy = y + half + label_dy
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
            indicator_direction=indicator_direction,
        ),
    )


@Composable(use_context=True)
def DoubleSouthKey(
    ctx,
    *,
    side: KeyboardSide,
    width: float,
    label_text: str,
    fill_color: str,
    accent_color: str,
    label_color: str,
):
    """The double-south key — a squat trapezoid below the south key.

    The shape is a vertical trapezoid: full ``width`` at the top, a
    fraction narrower at the bottom (``slant = 8%``). A coloured
    accent bar sits on the top edge — visually separating it from
    the south key directly above. The label is centred on the cell
    and nudged downward a fraction so the accent bar doesn't crowd
    it. Shape and accent are symmetric across the two halves;
    indicator metrics flip per ``side``.

    Reports :class:`SvalboardKeyMetrics` with the indicator on the
    outward (away-from-thumb) side: ``EAST`` on the right hand,
    ``WEST`` on the left.
    """
    del ctx  # RichText reads ``use_system_fonts`` from its own ctx.

    half = width / 2.0
    bottom_width = width * (1.0 - _DOUBLE_SOUTH_SLANT_MULTIPLIER)
    accent_size = width * _DOUBLE_SOUTH_ACCENT_SIZE_MULTIPLIER
    accent_radius = accent_size / 2.0
    label_font_size = width * _DOUBLE_SOUTH_FONT_HEIGHT_MULTIPLIER
    label_width_budget = width * _DOUBLE_SOUTH_LABEL_WIDTH_MULTIPLIER

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

    # Right-hand reference: indicator on the outward / east edge.
    # The mirror helper flips for the left hand.
    indicator_anchor, indicator_direction = _mirror_metrics(
        anchor=Point(width, half),
        direction=CompassDirection.EAST,
        width=width,
        side=side,
    )

    size = Size(width, width)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        # Trapezoid main shape — narrower at the bottom.
        d.append(
            Trapezoid(
                x=x,
                y=y,
                width=width,
                height=width,
                bottom_width=bottom_width,
                corners_radius=accent_radius,
                fill=fill_color,
            )
        )
        # Accent bar across the top.
        d.append(
            draw.Rectangle(
                x=x,
                y=y,
                width=width,
                height=accent_size,
                rx=accent_radius,
                ry=accent_radius,
                fill=accent_color,
            )
        )
        # Label centred + nudged downward by a quarter of an accent
        # size so it sits clear of the top bar.
        cx = x + half
        cy = y + half + accent_size / 4.0
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
            indicator_direction=indicator_direction,
        ),
    )


__all__ = [
    "CenterKey",
    "DirectionalKey",
    "DoubleSouthKey",
    "SvalboardKeyMetrics",
]
