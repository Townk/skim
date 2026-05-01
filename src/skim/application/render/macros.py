# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The macros section composables and standalone-image entry point.

* :class:`MacroMetrics` — sizing constants for the macro rows.
* :func:`MacroTable` — stacked macro rows wrapping the legacy
  ``build_macro_row`` so the rendered pills/chips match what the
  overview's macro section paints.
* :func:`MacroSection` — a ``MACROS`` :func:`SectionStripe` followed
  by a :func:`MacroTable`, laid out in a Column with the section's
  standard inter-strip / body gap.
* :func:`macro_natural_widths` — pre-pass helper that reports each
  macro's natural single-line width; used by image entry points to
  decide whether to shrink the canvas to wrap content.
* :func:`draw_macros_image` — the standalone macros image entry
  point.
"""

from __future__ import annotations

from dataclasses import dataclass

import drawsvg as draw

from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey

from .composable import Composable, render
from .legend import (
    _flatten_macro_pills,
    _layout_pill_lines,
    _LegendGeometry,
    all_macros,
    build_macro_row,
    macro_row_height,
)
from .primitives import Column, MetricsComponent, Size
from .render_context import RenderContext, using_render_context
from .section_stripe import SectionStripe, SectionStripeMetrics
from .styling import derive_accent_line


@dataclass(frozen=True, slots=True, kw_only=True)
class MacroSectionMetrics:
    """Metrics exposed by a built :func:`MacroSection`.

    The single field is the section title strip's ``rule_offset`` —
    surfaced so the parent document doesn't need to import
    :class:`SectionStripeMetrics` just to compute the gap that
    should sit above and below the section. Document composables
    use ``section.metrics.rule_offset * 0.5`` as the inter-sibling
    gap, matching the legacy positional-layout breathing constant.
    """

    rule_offset: float


@dataclass(frozen=True, slots=True, kw_only=True)
class MacroMetrics:
    """Sizing constants for the macros composables.

    Owns the chip dimensions (the colored tag at the head of each
    row) and the row-spacing constants for the macro section. Pill
    geometry — the per-step pills painted to the right of each chip —
    isn't owned here yet because :func:`build_macro_row` (the legacy
    overview-shared helper) still computes its own pill metrics from
    the underlying ``_LegendGeometry``. When that helper retires,
    pill metrics will move here.

    Currently delegates to ``_LegendGeometry`` so values stay aligned
    across the codebase; the ratios can move here directly once the
    legacy legend module retires.
    """

    chip_width: float
    row_gap: float
    row_content_indent_gap: float
    pill_gap: float

    @classmethod
    def for_doc_width(cls, doc_width: float) -> MacroMetrics:
        geom = _LegendGeometry.for_doc_width(doc_width)
        return cls(
            chip_width=geom.tag_w,
            row_gap=geom.row_gap,
            row_content_indent_gap=geom.row_content_indent_gap,
            pill_gap=geom.pill_gap,
        )


def macro_natural_widths(macros: list, doc_width: float) -> list[float]:
    """Width each macro would render at if every pill sat on a single line.

    Computes against the underlying ``_LegendGeometry`` (the legacy
    pill-layout helper expects it directly); image entry points pass
    the same scaled doc_width the body composable will lay out
    against so the wrap detection matches the rendered widths
    exactly.
    """
    geom = _LegendGeometry.for_doc_width(doc_width)
    indent = geom.tag_w + geom.row_content_indent_gap
    widths: list[float] = []
    for macro in macros:
        pills = _flatten_macro_pills(macro)
        if not pills:
            widths.append(indent)
            continue
        # ``_layout_pill_lines`` accounts for ``pill_gap``; querying it with
        # an effectively unbounded width returns a single line whose total
        # width is the natural macro row width.
        lines = _layout_pill_lines(pills, line_width=float("inf"), geom=geom)
        line = lines[0]
        line_w = sum(w for _, _, w in line) + max(0, len(line) - 1) * geom.pill_gap
        widths.append(indent + line_w)
    return widths


@Composable(use_context=True)
def MacroTable(
    ctx,
    *,
    macros: list,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    content_width: float,
    scale: float = 1.0,
):
    """Stacked macro rows with the legend's natural row-gap spacing.

    Wraps the existing :func:`build_macro_row` helper so the rendered
    pills and chips match what the overview's macro section paints.
    Per-row height respects ``content_width`` (pills wrap to additional
    lines when they don't fit).

    ``scale`` multiplies the doc-width the row's geometry is built
    against — the standalone macros image passes ``BODY_SCALE`` so chips
    and pills render larger than they would in an inline appearance,
    leaving the surrounding title and footer at their unscaled sizes.
    """
    doc_width = ctx.config.output.layout.width * scale
    metrics = MacroMetrics.for_doc_width(doc_width)
    use_system_fonts = ctx.config.output.style.use_system_fonts

    row_heights = [macro_row_height(m, content_width, doc_width=doc_width) for m in macros]
    total_h = sum(row_heights) + max(0, len(macros) - 1) * metrics.row_gap
    size = Size(content_width, total_h)

    def draw_at(d, origin):
        cursor = origin.y
        for i, macro in enumerate(macros):
            if i > 0:
                cursor += metrics.row_gap
            d.append(
                build_macro_row(
                    macro,
                    x=origin.x,
                    y=cursor,
                    content_width=content_width,
                    accent_fill=accent_fill,
                    accent_line=accent_line,
                    text_color=text_color,
                    use_system_fonts=use_system_fonts,
                    doc_width=doc_width,
                )
            )
            cursor += row_heights[i]

    return size, draw_at


@Composable(use_context=True)
def MacroSection(
    ctx,
    *,
    macros: list,
    content_width: float,
    width: float | None = None,
    scale: float = 1.0,
):
    """The MACROS section — :func:`SectionStripe` + :func:`MacroTable`.

    Encapsulates the title strip, the section's accent colours
    (derived from the theme's macro palette colour) and the standard
    inter-strip / body gap. Both the standalone macros image and the
    combined special-keys image render this composable directly.

    ``content_width`` is the layout budget passed to :func:`MacroTable`
    for pill-wrap detection — pills wrap to extra lines when they
    don't fit. ``width`` sets the :func:`SectionStripe`'s extent
    (where the count text lands and where the rule ends); when
    ``None`` (standalone-image case) the stripe snugs to the table's
    actual width, when given (combined-image case) it spans the slot.

    ``scale`` is forwarded to the underlying :func:`MacroTable` so the
    chips / pills enlarge while the section title strip stays at the
    unscaled per-image size.
    """
    palette = ctx.theme.palette
    accent_fill = palette.macro_color
    accent_line = derive_accent_line(accent_fill)
    stripe_metrics = SectionStripeMetrics.for_doc_width(ctx.config.output.layout.width)

    table = MacroTable(
        macros=macros,
        accent_fill=accent_fill,
        accent_line=accent_line,
        text_color=palette.text_color,
        content_width=content_width,
        scale=scale,
    )
    stripe_width = width if width is not None else table.size.width
    inner = Column(
        [
            SectionStripe(
                title="MACROS",
                count=len(macros),
                width=stripe_width,
                accent_line=accent_line,
            ),
            table,
        ],
        gap=ctx.document_metrics.section_spacing,
        align="start",
    )
    return MetricsComponent(
        size=inner.size,
        draw_fn=inner.draw_fn,
        metrics=MacroSectionMetrics(rule_offset=stripe_metrics.rule_offset),
    )


def _resolve_title(config: SkimConfig) -> str:
    """Pick the keymap title to render in the top-left of the image.

    Lives at the entry-point layer (next to :func:`draw_macros_image`)
    rather than inside the document composable so the binding from
    config to the rendered title string sits at the boundary where
    config is consumed; the document composable just receives the
    final string. The other two image entry points
    (:func:`tap_dance.draw_tap_dances_image`,
    :func:`special_keys.draw_special_keys_image`) import from here so
    every standalone-image render goes through the same resolver.
    """
    if config.output.keymap_title:
        return config.output.keymap_title
    if config.keyboard.layers:
        first = config.keyboard.layers[0]
        return f"{first.variant or first.name} Layers Layout"
    return "Keymap Layout"


def draw_macros_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the standalone macros image."""
    # Local import — :mod:`keymap_document` lazy-imports from this
    # module, so importing it eagerly would create a cycle.
    from .keymap_document import KeymapMacroDocument

    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapMacroDocument(
                macros=all_macros(keymap.macros),
                title=_resolve_title(config),
                copyright=config.output.copyright,
            )
        )


__all__ = [
    "MacroSection",
    "MacroSectionMetrics",
    "MacroTable",
    "draw_macros_image",
    "macro_natural_widths",
]
