# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The macros section composables and standalone-image entry point.

* :func:`MacroList` — stacked macro rows wrapping the legacy
  ``build_macro_row`` so the rendered pills/chips match what the
  overview's macro section paints.
* :func:`macro_natural_widths` — pre-pass helper that reports each
  macro's natural single-line width; used by image entry points to
  decide whether to shrink the canvas to wrap content.
* :func:`draw_macros_image` — the standalone macros image entry
  point.
"""

from __future__ import annotations

import drawsvg as draw

from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey

from .composable import Component, Composable, Size, Spacer
from .keymap_document import BODY_SCALE, render_single_section_document
from .legend import (
    _flatten_macro_pills,
    _layout_pill_lines,
    _LegendGeometry,
    all_macros,
    build_macro_row,
    macro_row_height,
)
from .render_context import RenderContext, using_render_context
from .styling import derive_accent_line


def macro_natural_widths(macros: list, geom: _LegendGeometry) -> list[float]:
    """Width each macro would render at if every pill sat on a single line."""
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
def MacroList(
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
    geom = _LegendGeometry.for_doc_width(doc_width)
    use_system_fonts = ctx.config.output.style.use_system_fonts

    row_heights = [macro_row_height(m, content_width, doc_width=doc_width) for m in macros]
    total_h = sum(row_heights) + max(0, len(macros) - 1) * geom.row_gap
    size = Size(content_width, total_h)

    def draw_at(d, origin):
        cursor = origin.y
        for i, macro in enumerate(macros):
            if i > 0:
                cursor += geom.row_gap
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


def draw_macros_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the standalone macros image."""
    with using_render_context(RenderContext.build(config, keymap)) as ctx:
        macros = all_macros(keymap.macros)
        palette = ctx.theme.palette
        metrics = ctx.document_metrics
        # The MACROS body renders at ``BODY_SCALE``; use the scaled
        # geom for wrap-detection so ``macro_natural_widths`` reports
        # the same widths the body composable will lay out against.
        scaled_geom = _LegendGeometry.for_doc_width(metrics.doc_width * BODY_SCALE)
        macro_line = derive_accent_line(palette.macro_color)

        initial_content_w = metrics.doc_width - 2 * metrics.padding

        # Lay out using the *initial* content width so wrap detection matches
        # what the user-requested canvas would normally produce. If the longest
        # natural row fits within ``initial_content_w`` no row wraps and we can
        # shrink the canvas; otherwise we keep the canvas at ``--width`` and let
        # the existing pill-wrap logic handle the overflow.
        natural_widths = macro_natural_widths(macros, scaled_geom)
        longest_natural = max(natural_widths) if natural_widths else 0.0
        no_wrapping = longest_natural <= initial_content_w
        content_w = longest_natural if (no_wrapping and longest_natural > 0) else initial_content_w

        body: Component = (
            MacroList(
                macros=macros,
                accent_fill=palette.macro_color,
                accent_line=macro_line,
                text_color=palette.text_color,
                content_width=content_w,
                scale=BODY_SCALE,
            )
            if macros
            else Spacer()
        )

        return render_single_section_document(
            body=body,
            section_title="MACROS",
            section_color=macro_line,
            section_count=len(macros),
            content_w=content_w,
        )


__all__ = [
    "MacroList",
    "draw_macros_image",
    "macro_natural_widths",
]
