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

from skim.data import resolve_spacing

from .composable import Composable
from .primitives import Size
from .render_context import RenderContext

# ---------------------------------------------------------------------------
# Per-doc-width ratios — title font size, letter spacing, rule
# offset, and the count-suffix typography. Sized as fractions of
# the document width so the title strip stays visually proportional
# across canvas sizes.
# ---------------------------------------------------------------------------

_TITLE_FONT_SIZE_RATIO = 11.0 / 1600.0
_TITLE_LETTER_SPACING_RATIO = 3.0 / 1600.0
_COUNT_FONT_SIZE_RATIO = 10.0 / 1600.0
_COUNT_LETTER_SPACING_RATIO = 1.0 / 1600.0
# Visible breathing room between the title's bottom edge and the
# rule line below. The strip is sized as ``title_font_size +
# title_rule_gap`` — top-anchored title, no dangling space above.
_TITLE_RULE_GAP_RATIO = 9.0 / 1600.0
_RULE_STROKE_RATIO = 1.2 / 1600.0


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionStripeMetrics:
    """Sizing constants for a :func:`SectionStripe`.

    Per-component metrics — derived from a doc_width via
    :meth:`for_doc_width`. Lives next to the composable that uses it
    so the component owns its measurements; nothing else in the
    codebase reads these values.

    The strip is top-anchored: the title text's em-box top sits at
    ``y=0`` and the rule line lands at ``title_font_size +
    title_rule_gap``. ``rule_offset`` (== strip total height) is
    surfaced for parents that need to align baseline-relative chrome
    around the strip.
    """

    title_font_size: float
    title_letter_spacing: float
    count_font_size: float
    count_letter_spacing: float
    title_rule_gap: float
    rule_offset: float
    rule_stroke: float

    @classmethod
    def for_doc_width(cls, doc_width: float) -> SectionStripeMetrics:
        """Build from a (possibly scaled) document width.

        Test-friendly factory: applies the built-in default
        ``title_rule_gap`` proportion (no Spacing override). Production
        callers should use :meth:`from_ctx` so the user's
        ``Spacing.section_title_rule_gap`` is honoured.
        """
        title_font_size = doc_width * _TITLE_FONT_SIZE_RATIO
        title_rule_gap = doc_width * _TITLE_RULE_GAP_RATIO
        return cls(
            title_font_size=title_font_size,
            title_letter_spacing=doc_width * _TITLE_LETTER_SPACING_RATIO,
            count_font_size=doc_width * _COUNT_FONT_SIZE_RATIO,
            count_letter_spacing=doc_width * _COUNT_LETTER_SPACING_RATIO,
            title_rule_gap=title_rule_gap,
            rule_offset=title_font_size + title_rule_gap,
            rule_stroke=doc_width * _RULE_STROKE_RATIO,
        )

    @classmethod
    def from_ctx(cls, ctx: RenderContext) -> SectionStripeMetrics:
        """Build from the active render context.

        Reads ``Spacing.section_title_rule_gap`` from the user's config
        and resolves it through :func:`resolve_spacing`. Falls back to
        the built-in default proportion when the field is ``None``.
        """
        doc_width = ctx.config.output.layout.width
        title_font_size = doc_width * _TITLE_FONT_SIZE_RATIO
        title_rule_gap = resolve_spacing(
            ctx.config.output.layout.spacing.section_title_rule_gap,
            base=doc_width,
            default_proportion=_TITLE_RULE_GAP_RATIO,
        )
        return cls(
            title_font_size=title_font_size,
            title_letter_spacing=doc_width * _TITLE_LETTER_SPACING_RATIO,
            count_font_size=doc_width * _COUNT_FONT_SIZE_RATIO,
            count_letter_spacing=doc_width * _COUNT_LETTER_SPACING_RATIO,
            title_rule_gap=title_rule_gap,
            rule_offset=title_font_size + title_rule_gap,
            rule_stroke=doc_width * _RULE_STROKE_RATIO,
        )


@Composable(use_context=True)
def SectionStripe(
    ctx,
    *,
    title: str,
    count: int,
    width: float,
    accent_line: str,
    show_count: bool = True,
):
    """Title text on the left, ``N ENTRIES`` on the right, rule line below.

    The element occupies the full ``width`` so a host's column layout
    can stretch the rule across the content area. Vertical extent
    matches what the legacy ``_draw_section_title`` reserved —
    ``rule_offset`` from the top to the rule line — so the composable
    can drop into a Column without changing the surrounding image's
    body offset.

    ``show_count`` toggles the right-aligned ``N ENTRIES`` text.
    Macro and tap-dance sections always show it; the symbols section
    suppresses it when rendered inside a per-layer image (where the
    count adds chrome that competes with the keyboard for attention)
    and shows it in the standalone symbols image.

    Reads its sizing constants from a freshly-built
    :class:`SectionStripeMetrics` derived from ``ctx`` (per the
    convention that component-specific metrics live with the
    component). Color of the title text and rule comes from
    ``accent_line`` — the section's derived accent — since that's a
    per-section value, not a theme preset.
    """
    metrics = SectionStripeMetrics.from_ctx(ctx)
    size = Size(width, metrics.rule_offset)

    def draw_at(d, origin):
        x, y = origin.x, origin.y
        # Top-anchor both texts via ``text-before-edge`` so the strip
        # has no configurable dangling space above the title; the
        # only configurable vertical value is the title→rule gap.
        d.append(
            draw.Text(
                title,
                x=x,
                y=y,
                font_size=metrics.title_font_size,
                font_weight="700",
                letter_spacing=metrics.title_letter_spacing,
                text_anchor="start",
                dominant_baseline="text-before-edge",
                font_family="'Roboto', sans-serif",
                fill=accent_line,
            )
        )
        if show_count:
            d.append(
                draw.Text(
                    f"{count} ENTRIES",
                    x=x + width,
                    y=y,
                    font_size=metrics.count_font_size,
                    text_anchor="end",
                    dominant_baseline="text-before-edge",
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
