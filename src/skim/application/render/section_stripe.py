# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The section title strip composable (e.g. ``MACROS``, ``TAP-DANCE``).

A :func:`SectionStripe` paints the title text on the left, the
``N ENTRIES`` count on the right, and an accent-coloured rule line
underneath. It's the first child of every :func:`LabeledSection` and
sets the visual character of the section beneath it (the colour of
the title and rule comes from the section's accent line).
"""

from __future__ import annotations

from dataclasses import dataclass

import drawsvg as draw

from .composable import Composable
from .legend import _LegendGeometry
from .primitives import Size


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionStripeMetrics:
    """Sizing constants for a :func:`SectionStripe`.

    Per-component metrics — derived from a doc_width via
    :meth:`for_doc_width`. Lives next to the composable that uses it
    so the component owns its measurements; nothing else in the
    codebase reads these values.

    The five fields cover everything a stripe paints: title
    typography (size + tracking), the right-aligned ``N ENTRIES``
    count typography (size + tracking), the rule line's vertical
    offset from the strip's top, and the rule's stroke width. The
    title is anchored at ``baseline_offset`` from the top.
    """

    title_font_size: float
    title_letter_spacing: float
    title_baseline_offset: float
    count_font_size: float
    count_letter_spacing: float
    rule_offset: float
    rule_stroke: float

    @classmethod
    def for_doc_width(cls, doc_width: float) -> SectionStripeMetrics:
        """Build from a (possibly scaled) document width.

        Currently delegates to ``_LegendGeometry`` for the underlying
        ratios so all section stripes across the app stay aligned;
        when the legacy legend module retires, the ratios can move
        here directly.
        """
        geom = _LegendGeometry.for_doc_width(doc_width)
        return cls(
            title_font_size=geom.title_font_size,
            title_letter_spacing=geom.title_letter_spacing,
            title_baseline_offset=geom.title_baseline_offset,
            count_font_size=geom.title_count_font_size,
            count_letter_spacing=geom.title_count_letter_spacing,
            rule_offset=geom.title_rule_offset,
            rule_stroke=geom.title_rule_stroke,
        )


@Composable(use_context=True)
def SectionStripe(
    ctx,
    *,
    title: str,
    count: int,
    width: float,
    accent_line: str,
):
    """Title text on the left, ``N ENTRIES`` on the right, rule line below.

    The element occupies the full ``width`` so a host's column layout
    can stretch the rule across the content area. Vertical extent
    matches what the legacy ``_draw_section_title`` reserved —
    ``rule_offset`` from the top to the rule line — so the composable
    can drop into a Column without changing the surrounding image's
    body offset.

    Reads its sizing constants from a freshly-built
    :class:`SectionStripeMetrics` derived from ``ctx`` (per the
    convention that component-specific metrics live with the
    component). Color of the title text and rule comes from
    ``accent_line`` — the section's derived accent — since that's a
    per-section value, not a theme preset.
    """
    metrics = SectionStripeMetrics.for_doc_width(ctx.config.output.layout.width)
    size = Size(width, metrics.rule_offset)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        d.append(
            draw.Text(
                title,
                x=x,
                y=y + metrics.title_baseline_offset,
                font_size=metrics.title_font_size,
                font_weight="700",
                letter_spacing=metrics.title_letter_spacing,
                text_anchor="start",
                font_family="'Roboto', sans-serif",
                fill=accent_line,
            )
        )
        d.append(
            draw.Text(
                f"{count} ENTRIES",
                x=x + width,
                y=y + metrics.title_baseline_offset,
                font_size=metrics.count_font_size,
                text_anchor="end",
                fill="#888",
                font_weight="400",
                letter_spacing=metrics.count_letter_spacing,
                font_family="'Roboto', sans-serif",
            )
        )
        d.append(
            draw.Line(
                sx=x,
                sy=y + metrics.rule_offset,
                ex=x + width,
                ey=y + metrics.rule_offset,
                stroke=accent_line,
                stroke_opacity=0.5,
                stroke_width=metrics.rule_stroke,
            )
        )

    return size, draw_at


__all__ = ["SectionStripe", "SectionStripeMetrics"]
