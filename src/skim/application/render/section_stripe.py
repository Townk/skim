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

import drawsvg as draw

from .composable import Composable, Size
from .legend import _LegendGeometry


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
    ``title_rule_offset`` from the top to the rule line — so the
    composable can drop into a Column without changing the surrounding
    image's body offset.

    Reads its sizing constants from a fresh ``_LegendGeometry``
    derived from ``ctx`` (per the convention that component-specific
    metrics live with the component, not on the context). Color of
    the title text and rule comes from ``accent_line`` — the section's
    derived accent — since that's a per-section value, not a theme
    preset.
    """
    geom = _LegendGeometry.for_doc_width(ctx.config.output.layout.width)
    height = geom.title_rule_offset
    size = Size(width, height)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        d.append(
            draw.Text(
                title,
                x=x,
                y=y + geom.title_baseline_offset,
                font_size=geom.title_font_size,
                font_weight="700",
                letter_spacing=geom.title_letter_spacing,
                text_anchor="start",
                font_family="'Roboto', sans-serif",
                fill=accent_line,
            )
        )
        d.append(
            draw.Text(
                f"{count} ENTRIES",
                x=x + width,
                y=y + geom.title_baseline_offset,
                font_size=geom.title_count_font_size,
                text_anchor="end",
                fill="#888",
                font_weight="400",
                letter_spacing=geom.title_count_letter_spacing,
                font_family="'Roboto', sans-serif",
            )
        )
        d.append(
            draw.Line(
                sx=x,
                sy=y + geom.title_rule_offset,
                ex=x + width,
                ey=y + geom.title_rule_offset,
                stroke=accent_line,
                stroke_opacity=0.5,
                stroke_width=geom.title_rule_stroke,
            )
        )

    return size, draw_at


__all__ = ["SectionStripe"]
