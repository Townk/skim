# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable building blocks for individual Svalboard keys.

The legacy :mod:`keys` module models keys as ``draw.Group`` subclasses
that pull a :class:`ClusterRenderContext` straight in and resolve
colours / labels internally. This module hosts the composable
equivalents — pure components that take resolved inputs (width,
label text, fill / label colours) and report a typed ``Size`` plus
:class:`SvalboardKeyMetrics`. Cluster-level resolution lives one
layer up; the key composable doesn't reach for context-derived
state beyond ``ctx.config.output.style.use_system_fonts``.

Key text is rendered through :func:`RichText` (the same
multi-span text composable the macros / tap-dances / symbols
sections use) so the key composable doesn't pull the legacy
:class:`Label` parser. Trade-offs vs. the legacy ``Label`` path:

* :class:`Label` uppercases keymap-key labels for *measurement*
  (a "keymap convention"), so a long lowercase label might pick a
  smaller font than RichText's same-case measurement does. Keys
  with lowercase labels render at a slightly larger font size
  here than they did under legacy. The painted text stays the
  caller's original case in both paths.
* :class:`SeparatorPart` renders the layer-switch ``|`` glyph at a
  custom narrower width. RichText emits the literal character
  instead. This shows up only on keys whose label embeds the
  separator (mostly layer-switch directional keys); on CenterKey
  in practice it doesn't apply.

The differences are intentional and surface as snapshot diffs when
the cluster code is migrated to call these composables. The diffs
are visible records of the migration's visual delta — not silent
regressions.
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
# Per-key sizing constants — mirror the ``CONFIG`` ``KeyConfig`` instances
# the legacy concrete keys pin on their classes (see :class:`keys.CenterKey`,
# etc.). Keeping these inline alongside the composable they apply to keeps
# each key shape self-contained — the eventual goal is for ``keys.py`` to
# retire and these values become the canonical source.
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

    # ``min_font_size=1`` matches what :meth:`Label.size_to_fit` does
    # by default — keys shrink as far as needed to fit the label
    # rather than ellipsis-truncating. Without this RichText pins
    # at the natural size and drops the label to ``…`` when wider
    # than the budget, which is wrong for key cells.
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
