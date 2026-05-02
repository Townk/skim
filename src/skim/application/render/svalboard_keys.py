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

from skim.domain import Alignment, KeyboardSide, KeyDirection

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

# Thumb-cluster aspect ratios — height as a fraction of the cell width.
# Some thumb keys are taller than wide (Down / DoubleDown), others wider
# than tall (Up / Pad / Nail / Knuckle). The cluster passes the natural
# ``width``; ``height = width * RATIO`` falls out per shape.
_DOWN_HEIGHT_RATIO = 2.6
_DOUBLE_DOWN_HEIGHT_RATIO = 1.1
_UP_HEIGHT_RATIO = 1.0 / 2.75
_PAD_HEIGHT_RATIO = 1.0 / 1.85
_NAIL_HEIGHT_RATIO = 1.0 / 1.95
_KNUCKLE_HEIGHT_RATIO = 1.0 / 1.87

# DownKey — tall narrow trapezoid (top narrower); label at bottom.
_DOWN_SLANT_MULTIPLIER = 0.25
_DOWN_CORNER_RADIUS_MULTIPLIER = 0.12
_DOWN_FONT_HEIGHT_MULTIPLIER = 0.15
_DOWN_LABEL_WIDTH_MULTIPLIER = 0.8 - _DOWN_SLANT_MULTIPLIER / 2
_DOWN_LABEL_BOTTOM_MARGIN_MULTIPLIER = 0.10
# DownKey indicator anchors at the bottom-ish of the key — most of
# the upper half is occluded by the pad / up / nail / knuckle keys
# at typing time, so the indicator badge wants to sit on the visible
# (lower) part of the outward edge. The 0.84 ratio matches the
# legacy ``LayerIndicatorOverlay.for_thumb_cluster`` placement
# (``down_target_cy = up_cy + (up_cy - pad_cy)`` evaluated at the
# legacy thumb-cluster proportions, divided by the down key's
# height).
_DOWN_INDICATOR_ANCHOR_Y_RATIO = 0.84

# DoubleDownKey — squat trapezoid with stroke outline; centred label.
_DOUBLE_DOWN_SLANT_MULTIPLIER = 0.08
_DOUBLE_DOWN_STROKE_MULTIPLIER = 0.05
_DOUBLE_DOWN_CORNER_RADIUS_MULTIPLIER = 0.13
_DOUBLE_DOWN_FONT_HEIGHT_MULTIPLIER = 0.6
_DOUBLE_DOWN_LABEL_WIDTH_MULTIPLIER = 0.8 - _DOUBLE_DOWN_SLANT_MULTIPLIER

# UpKey — wide short horizontal trapezoid, slanted on the OUTWARD side
# (right hand: slant on the left edge). Drawn as two stacked
# trapezoids — the outer paints in the stroke colour and is slightly
# larger; the inner paints the fill on top.
_UP_SLANT_MULTIPLIER = 0.12
_UP_STROKE_MULTIPLIER = 0.025
_UP_CORNER_RADIUS_MULTIPLIER = 0.05
_UP_FONT_HEIGHT_MULTIPLIER = 0.45
_UP_LABEL_WIDTH_MULTIPLIER = 0.8
_UP_LABEL_MARGIN_MULTIPLIER = 0.10

# PadKey, NailKey, KnuckleKey — vertical trapezoid (bottom narrower);
# the narrow face aligns to one side or the other depending on the
# keyboard half. PadKey's narrow bottom goes outward (right hand →
# right edge); NailKey / KnuckleKey go inward (right hand → left edge).
_PAD_SLANT_MULTIPLIER = 0.035
_PAD_CORNER_RADIUS_MULTIPLIER = 0.05
_PAD_FONT_HEIGHT_MULTIPLIER = 0.4
_PAD_LABEL_WIDTH_MULTIPLIER = 0.8 - _PAD_SLANT_MULTIPLIER
_PAD_LABEL_MARGIN_MULTIPLIER = 0.1 + _PAD_SLANT_MULTIPLIER

_NAIL_SLANT_MULTIPLIER = 0.03
_NAIL_CORNER_RADIUS_MULTIPLIER = 0.05
_NAIL_FONT_HEIGHT_MULTIPLIER = 0.4
_NAIL_LABEL_WIDTH_MULTIPLIER = 0.8 - _NAIL_SLANT_MULTIPLIER
_NAIL_LABEL_MARGIN_MULTIPLIER = 0.1 + _NAIL_SLANT_MULTIPLIER

_KNUCKLE_SLANT_MULTIPLIER = 0.028
_KNUCKLE_CORNER_RADIUS_MULTIPLIER = 0.05
_KNUCKLE_FONT_HEIGHT_MULTIPLIER = 0.4
_KNUCKLE_LABEL_WIDTH_MULTIPLIER = 0.8 - _KNUCKLE_SLANT_MULTIPLIER
_KNUCKLE_LABEL_MARGIN_MULTIPLIER = 0.1 + _KNUCKLE_SLANT_MULTIPLIER


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
        spans=parse_into_spans(label_text, label_style, separator_background=fill_color),
        style=label_style,
        max_width=label_width_budget,
        min_font_size=1.0,
        text_anchor="middle",
        dominant_baseline="central",
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
        spans=parse_into_spans(label_text, label_style, separator_background=fill_color),
        style=label_style,
        max_width=label_width_budget,
        min_font_size=1.0,
        text_anchor="middle",
        dominant_baseline="central",
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
        spans=parse_into_spans(label_text, label_style, separator_background=fill_color),
        style=label_style,
        max_width=label_width_budget,
        min_font_size=1.0,
        text_anchor="middle",
        dominant_baseline="central",
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


# ---------------------------------------------------------------------------
# Thumb-cluster keys
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def DownKey(
    ctx,
    *,
    side: KeyboardSide,
    width: float,
    label_text: str,
    fill_color: str,
    label_color: str,
):
    """The down key — tall narrow trapezoid at the bottom of the thumb cluster.

    The shape is symmetric (top-narrower vertical trapezoid with the
    slant split equally between left and right edges) so the drawing
    is identical on both halves; only the indicator metrics flip per
    side. The label sits near the bottom of the key — thumb keys
    print their labels at the visible part of the key (the part not
    occluded by the thumb when typing).

    Reports :class:`SvalboardKeyMetrics` with the indicator on the
    outward (away-from-thumb) edge: ``EAST`` on the right hand,
    ``WEST`` on the left.
    """
    del ctx  # RichText reads ``use_system_fonts`` from its own ctx.

    height = width * _DOWN_HEIGHT_RATIO
    top_width = width * (1.0 - _DOWN_SLANT_MULTIPLIER)
    corner_radius = width * _DOWN_CORNER_RADIUS_MULTIPLIER
    label_font_size = height * _DOWN_FONT_HEIGHT_MULTIPLIER
    label_width_budget = width * _DOWN_LABEL_WIDTH_MULTIPLIER

    label_style = TextStyle(font=Font.THUMB_KEY, size=label_font_size, color=label_color)
    label_el = RichText(
        spans=parse_into_spans(label_text, label_style, separator_background=fill_color),
        style=label_style,
        max_width=label_width_budget,
        min_font_size=1.0,
        text_anchor="middle",
        dominant_baseline="central",
    )

    indicator_anchor, indicator_direction = _mirror_metrics(
        anchor=Point(width, height * _DOWN_INDICATOR_ANCHOR_Y_RATIO),
        direction=CompassDirection.EAST,
        width=width,
        side=side,
    )

    size = Size(width, height)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        d.append(
            Trapezoid(
                x=x,
                y=y,
                width=width,
                height=height,
                top_width=top_width,
                corners_radius=corner_radius,
                fill=fill_color,
            )
        )
        # Label centred horizontally, near the bottom of the key
        # (visible part — the part not occluded by the thumb).
        label_bottom_y = y + height - height * _DOWN_LABEL_BOTTOM_MARGIN_MULTIPLIER
        label_origin = Point(
            x + width / 2.0 - label_el.size.width / 2.0,
            label_bottom_y - label_el.size.height,
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
def DoubleDownKey(
    ctx,
    *,
    side: KeyboardSide,
    width: float,
    label_text: str,
    fill_color: str,
    label_color: str,
    stroke_color: str,
):
    """The double-down key — squat trapezoid with a stroke outline.

    Sits between the down key and the up key in the thumb cluster.
    Shape is symmetric (top-narrower vertical trapezoid), so the
    drawing is identical on both halves. The indicator always sits
    above the key — :class:`CompassDirection.NORTH` is mirror-
    invariant under horizontal reflection, so the metrics happen to
    be side-invariant for this one too.
    """
    del ctx  # RichText reads ``use_system_fonts`` from its own ctx.

    height = width * _DOUBLE_DOWN_HEIGHT_RATIO
    top_width = width * (1.0 - _DOUBLE_DOWN_SLANT_MULTIPLIER)
    stroke_width = width * _DOUBLE_DOWN_STROKE_MULTIPLIER
    corner_radius = width * _DOUBLE_DOWN_CORNER_RADIUS_MULTIPLIER
    label_font_size = height * _DOUBLE_DOWN_FONT_HEIGHT_MULTIPLIER
    label_width_budget = width * _DOUBLE_DOWN_LABEL_WIDTH_MULTIPLIER

    label_style = TextStyle(font=Font.THUMB_KEY, size=label_font_size, color=label_color)
    label_el = RichText(
        spans=parse_into_spans(label_text, label_style, separator_background=fill_color),
        style=label_style,
        max_width=label_width_budget,
        min_font_size=1.0,
        text_anchor="middle",
        dominant_baseline="central",
    )

    indicator_anchor, indicator_direction = _mirror_metrics(
        anchor=Point(width / 2.0, 0.0),
        direction=CompassDirection.NORTH,
        width=width,
        side=side,
    )

    size = Size(width, height)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        d.append(
            Trapezoid(
                x=x,
                y=y,
                width=width,
                height=height,
                top_width=top_width,
                corners_radius=corner_radius,
                fill=fill_color,
                stroke=stroke_color,
                stroke_width=stroke_width,
            )
        )
        # Label centred at the cell centre.
        cx = x + width / 2.0
        cy = y + height / 2.0
        label_origin = Point(
            cx - label_el.size.width / 2.0,
            cy - label_el.size.height / 2.0,
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
def UpKey(
    ctx,
    *,
    side: KeyboardSide,
    width: float,
    label_text: str,
    fill_color: str,
    label_color: str,
    stroke_color: str,
):
    """The up key — wide short horizontal trapezoid at the top of the cluster.

    Asymmetric: the outward (away-from-thumb) edge is full-height,
    the inward edge is shorter — the outline tapers from the
    outward end down to the inward end. Drawn as a stroke + fill
    pair (outer trapezoid in stroke colour, slightly larger; inner
    trapezoid in fill colour). Mirrors visually per side.

    Label sits at the wide end of the key — outward — anchored
    away from the inward taper so the text doesn't crowd the slant.
    Indicator on the same outward edge.
    """
    del ctx  # RichText reads ``use_system_fonts`` from its own ctx.

    height = width * _UP_HEIGHT_RATIO
    short_face = height * (1.0 - _UP_SLANT_MULTIPLIER)
    stroke_width = width * _UP_STROKE_MULTIPLIER
    corner_radius = width * _UP_CORNER_RADIUS_MULTIPLIER
    label_font_size = height * _UP_FONT_HEIGHT_MULTIPLIER
    label_width_budget = width * _UP_LABEL_WIDTH_MULTIPLIER

    # Right hand: slant on the inward (LEFT) edge → left edge is short.
    # Left hand: slant on the inward (RIGHT) edge → right edge is short.
    if side is KeyboardSide.RIGHT:
        inner_left_height: float | None = short_face
        inner_right_height: float | None = None  # full height
    else:
        inner_left_height = None
        inner_right_height = short_face

    # Outer (stroke) trapezoid is slightly larger so the stroke shows
    # around the inner fill. ``2.3 * stroke_width`` extra height
    # mirrors the legacy hand-tuned bump.
    outer_extra_w = stroke_width * 2.0
    outer_extra_h = stroke_width * 2.3
    outer_short_face = (height + outer_extra_h) * (1.0 - _UP_SLANT_MULTIPLIER)
    if side is KeyboardSide.RIGHT:
        outer_left_height: float | None = outer_short_face
        outer_right_height: float | None = None
    else:
        outer_left_height = None
        outer_right_height = outer_short_face

    # Label position: anchored to the OUTWARD edge.
    # Right hand: outward = right; text_anchor=start, x near left
    # would put label on the inward (slanted) side — wrong. Use the
    # legacy convention: text anchored to the outward end with x at
    # the outward edge minus margin.
    if side is KeyboardSide.RIGHT:
        # Outward edge is RIGHT; label anchors to start, with x near
        # left edge. This is the legacy mapping (label on the wide
        # full-height outer side). The label visually sits on the
        # full-height side opposite the slant.
        label_text_anchor = "start"
        label_x_factor = _UP_LABEL_MARGIN_MULTIPLIER
    else:
        label_text_anchor = "end"
        label_x_factor = 1.0 - _UP_LABEL_MARGIN_MULTIPLIER

    label_style = TextStyle(font=Font.THUMB_KEY, size=label_font_size, color=label_color)
    label_el = RichText(
        spans=parse_into_spans(label_text, label_style, separator_background=fill_color),
        style=label_style,
        max_width=label_width_budget,
        min_font_size=1.0,
        text_anchor=label_text_anchor,
        dominant_baseline="central",
    )

    indicator_anchor, indicator_direction = _mirror_metrics(
        anchor=Point(width, height / 2.0),
        direction=CompassDirection.EAST,
        width=width,
        side=side,
    )

    size = Size(width, height)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        # Outer (stroke) trapezoid.
        d.append(
            Trapezoid(
                x=x - stroke_width,
                y=y - stroke_width,
                width=width + outer_extra_w,
                height=height + outer_extra_h,
                left_height=outer_left_height,
                right_height=outer_right_height,
                corners_radius=corner_radius,
                align_y=Alignment.START,
                fill=stroke_color,
            )
        )
        # Inner (fill) trapezoid.
        d.append(
            Trapezoid(
                x=x,
                y=y,
                width=width,
                height=height,
                left_height=inner_left_height,
                right_height=inner_right_height,
                corners_radius=corner_radius,
                align_y=Alignment.START,
                fill=fill_color,
            )
        )
        # Label vertically centred on the SHORT face (the slanted
        # half), x anchored per side. The legacy positions the label
        # at half the short-face height — same intent here.
        label_y = y + short_face / 2.0
        label_x = x + width * label_x_factor
        # Translate ``text_anchor`` + ``dominant_baseline=central`` to
        # an offset for the bbox top-left.
        if label_text_anchor == "start":
            anchor_dx = 0.0
        elif label_text_anchor == "end":
            anchor_dx = -label_el.size.width
        else:  # "middle"
            anchor_dx = -label_el.size.width / 2.0
        label_origin = Point(label_x + anchor_dx, label_y - label_el.size.height / 2.0)
        label_el.draw_at(d, label_origin)

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=SvalboardKeyMetrics(
            indicator_anchor=indicator_anchor,
            indicator_direction=indicator_direction,
        ),
    )


def _vertical_trapezoid_thumb_key(
    *,
    side: KeyboardSide,
    width: float,
    label_text: str,
    fill_color: str,
    label_color: str,
    height_ratio: float,
    slant_multiplier: float,
    corner_radius_multiplier: float,
    font_height_multiplier: float,
    label_width_multiplier: float,
    label_margin_multiplier: float,
    narrow_bottom_outward: bool,
    indicator_outward: bool,
) -> MetricsComponent[SvalboardKeyMetrics]:
    """Shared body for the four similar thumb keys.

    Pad / Nail / Knuckle (and Up's vertical-trapezoid cousins, if any)
    differ only in: aspect ratio, slant amount, where the narrow
    bottom face aligns relative to the thumb, and where the
    indicator sits relative to the thumb. ``narrow_bottom_outward``
    + ``indicator_outward`` capture both choices as bools — the
    helper resolves the per-side alignment, label-anchor side, and
    indicator anchor / direction in one place.
    """
    height = width * height_ratio
    bottom_width = width * (1.0 - slant_multiplier)
    corner_radius = width * corner_radius_multiplier
    label_font_size = height * font_height_multiplier
    label_width_budget = width * label_width_multiplier

    is_right = side is KeyboardSide.RIGHT
    # Outward direction in the canvas: right hand → right edge,
    # left hand → left edge.
    outward_is_right = is_right

    # Trapezoid alignment of the narrow bottom face.
    narrow_on_right = (outward_is_right and narrow_bottom_outward) or (
        not outward_is_right and not narrow_bottom_outward
    )
    align_x = Alignment.END if narrow_on_right else Alignment.START

    # Label anchored on the slanted edge — the side that faces the
    # cluster's centre. With ``narrow_bottom`` trapezoids the wider
    # face sits at the top and the slant runs from the wide top to
    # the narrow bottom along the OPPOSITE side from the bottom-narrow
    # corner: when the narrow bottom is right-aligned, the slant runs
    # along the LEFT edge (from top-left out to bottom-narrow-left).
    # The label sits on that slanted side because — for both pad
    # (narrow-bottom-outward) and nail / knuckle (narrow-bottom-inward) —
    # that orients the text toward the cluster's centre line, matching
    # the legacy thumb-key conventions.
    if narrow_on_right:
        label_text_anchor = "start"
        label_x_factor = label_margin_multiplier
    else:
        label_text_anchor = "end"
        label_x_factor = 1.0 - label_margin_multiplier

    # Indicator: outward edge on the right hand vs. left hand differs;
    # the mirror helper does the reflection. ``ref_anchor`` is the
    # right-hand reference position for the indicator.
    if indicator_outward:
        ref_anchor = Point(width, height / 2.0)
        ref_direction = CompassDirection.EAST
    else:  # inward
        ref_anchor = Point(0.0, height / 2.0)
        ref_direction = CompassDirection.WEST
    indicator_anchor, indicator_direction = _mirror_metrics(
        anchor=ref_anchor, direction=ref_direction, width=width, side=side
    )

    label_style = TextStyle(font=Font.THUMB_KEY, size=label_font_size, color=label_color)
    label_el = RichText(
        spans=parse_into_spans(label_text, label_style, separator_background=fill_color),
        style=label_style,
        max_width=label_width_budget,
        min_font_size=1.0,
        text_anchor=label_text_anchor,
        dominant_baseline="central",
    )

    size = Size(width, height)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        d.append(
            Trapezoid(
                x=x,
                y=y,
                width=width,
                height=height,
                bottom_width=bottom_width,
                corners_radius=corner_radius,
                align_x=align_x,
                fill=fill_color,
            )
        )
        # Label vertically centred on the cell.
        label_x = x + width * label_x_factor
        if label_text_anchor == "start":
            anchor_dx = 0.0
        elif label_text_anchor == "end":
            anchor_dx = -label_el.size.width
        else:
            anchor_dx = -label_el.size.width / 2.0
        label_origin = Point(
            label_x + anchor_dx,
            y + height / 2.0 - label_el.size.height / 2.0,
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
def PadKey(
    ctx,
    *,
    side: KeyboardSide,
    width: float,
    label_text: str,
    fill_color: str,
    label_color: str,
):
    """The pad key — vertical trapezoid with the narrow face on the OUTWARD edge.

    Sits next to the up key, tapering down toward the outward edge.
    Indicator on the outward (away-from-thumb) side.
    """
    del ctx
    return _vertical_trapezoid_thumb_key(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
        height_ratio=_PAD_HEIGHT_RATIO,
        slant_multiplier=_PAD_SLANT_MULTIPLIER,
        corner_radius_multiplier=_PAD_CORNER_RADIUS_MULTIPLIER,
        font_height_multiplier=_PAD_FONT_HEIGHT_MULTIPLIER,
        label_width_multiplier=_PAD_LABEL_WIDTH_MULTIPLIER,
        label_margin_multiplier=_PAD_LABEL_MARGIN_MULTIPLIER,
        narrow_bottom_outward=True,
        indicator_outward=True,
    )


@Composable(use_context=True)
def NailKey(
    ctx,
    *,
    side: KeyboardSide,
    width: float,
    label_text: str,
    fill_color: str,
    label_color: str,
):
    """The nail key — vertical trapezoid with the narrow face on the INWARD edge.

    Mirrored shape of :func:`PadKey` — narrow bottom on the
    thumb-side (right hand → left edge); indicator on the same
    inward side.
    """
    del ctx
    return _vertical_trapezoid_thumb_key(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
        height_ratio=_NAIL_HEIGHT_RATIO,
        slant_multiplier=_NAIL_SLANT_MULTIPLIER,
        corner_radius_multiplier=_NAIL_CORNER_RADIUS_MULTIPLIER,
        font_height_multiplier=_NAIL_FONT_HEIGHT_MULTIPLIER,
        label_width_multiplier=_NAIL_LABEL_WIDTH_MULTIPLIER,
        label_margin_multiplier=_NAIL_LABEL_MARGIN_MULTIPLIER,
        narrow_bottom_outward=False,
        indicator_outward=False,
    )


@Composable(use_context=True)
def KnuckleKey(
    ctx,
    *,
    side: KeyboardSide,
    width: float,
    label_text: str,
    fill_color: str,
    label_color: str,
):
    """The knuckle key — same shape pattern as :func:`NailKey`, different proportions.

    Narrow bottom on the inward (thumb-facing) edge, indicator on the
    same inward side. Slant amount is slightly smaller than NailKey's
    (key is squatter relative to its width).
    """
    del ctx
    return _vertical_trapezoid_thumb_key(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
        height_ratio=_KNUCKLE_HEIGHT_RATIO,
        slant_multiplier=_KNUCKLE_SLANT_MULTIPLIER,
        corner_radius_multiplier=_KNUCKLE_CORNER_RADIUS_MULTIPLIER,
        font_height_multiplier=_KNUCKLE_FONT_HEIGHT_MULTIPLIER,
        label_width_multiplier=_KNUCKLE_LABEL_WIDTH_MULTIPLIER,
        label_margin_multiplier=_KNUCKLE_LABEL_MARGIN_MULTIPLIER,
        narrow_bottom_outward=False,
        indicator_outward=False,
    )


__all__ = [
    "CenterKey",
    "DirectionalKey",
    "DoubleDownKey",
    "DoubleSouthKey",
    "DownKey",
    "KnuckleKey",
    "NailKey",
    "PadKey",
    "SvalboardKeyMetrics",
    "UpKey",
]
