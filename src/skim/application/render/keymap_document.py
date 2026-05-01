# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The keymap document chrome and assembly helpers.

A "keymap document" is the outermost rendered artifact of any
standalone special-keys image: the rounded background border, the
header (keymap title + Svalboard logo), the body, and an optional
copyright footer.

This module owns:

* :func:`KeymapDocument` — the outermost composable (rounded border
  around the rest of the content).
* :func:`render` — assembles header + body + (optional) footer into
  a :class:`KeymapDocument` and produces the final ``draw.Drawing``.
* :data:`BODY_SCALE` — the per-image body magnification multiplier
  used by the standalone images so chips and cells read at a visual
  weight comparable to layout keys.

Per-section composables (``MacroSection``, ``TapDanceSection``) are
in their own modules; this one only owns the chrome that wraps them.
"""

from __future__ import annotations

import drawsvg as draw

from .composable import Composable
from .footer import Footer
from .header import Header
from .legend import _LegendGeometry
from .primitives import (
    Column,
    Component,
    Padding,
    Point,
    Size,
    Spacer,
)
from .render_context import current_render_context
from .text import Font

# The body of a standalone special-keys image (the macro / tap-dance
# section content) renders at this multiple of the configured document
# width — chips, cells, pills and column labels grow against the title
# / footer / outer paddings, which stay at their unscaled per-image
# sizes. The chosen multiplier (1.5×) makes the body comparable to the
# layout-key sizing of the per-layer images so a special-keys page reads
# at a similar visual weight to a per-layer page when displayed at the
# same width.
BODY_SCALE = 1.5


# ---------------------------------------------------------------------------
# Helpers (ctx-aware)
# ---------------------------------------------------------------------------


def _resolve_title(config) -> str:
    """Pick the keymap title to render in the top-left of the image."""
    if config.output.keymap_title:
        return config.output.keymap_title
    if config.keyboard.layers:
        first = config.keyboard.layers[0]
        return f"{first.variant or first.name} Layers Layout"
    return "Keymap Layout"


def _section_title_max_height(label: str) -> float:
    """Rendered height of a section title label (e.g. ``"MACROS"``).

    Used as the ``max_height`` cap for the footer in the standalone solo
    images so the copyright never reads taller than the section title
    above the body. Measured with ``getbbox()`` for the same font and
    size :class:`SectionStripe` actually paints with — the geometry is
    derived from the active :class:`RenderContext`.
    """
    ctx = current_render_context()
    geom = _LegendGeometry.for_doc_width(ctx.config.output.layout.width)
    pil_font = Font.FINGER_KEY.load(int(round(max(geom.title_font_size, 1.0))))
    left, top, right, bottom = pil_font.getbbox(label)
    del left, right
    return float(bottom - top)


def _footer_max_height(*, section_title: str | None) -> float | None:
    """Pick the ``max_height`` cap for the footer based on the host image.

    The standalone solo images (macros / tap-dances) cap the footer at
    the rendered height of their section title so the copyright doesn't
    dwarf the legend it sits below. The combined ``special-keys`` image
    (and any image without a single dominant section title) leaves the
    footer at its natural size by passing ``None``.
    """
    if section_title is None:
        return None
    return _section_title_max_height(section_title)


# ---------------------------------------------------------------------------
# Outer chrome
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def KeymapDocument(ctx, *, content: Component, content_padding: Padding):
    """The outermost composable — rounded background border + content padding.

    Owns two parent-level layout concerns at once:

    * The rounded background border, painted INSIDE the document
      extent inset by ``ctx.document_metrics.margin``.
    * The content padding (``content_padding``) that insets the
      child from the document edges. The document's reported size
      grows by ``content_padding.horizontal`` /
      ``content_padding.vertical`` so the canvas wraps the padded
      content exactly.
    """
    size = Size(
        content.size.width + content_padding.horizontal,
        content.size.height + content_padding.vertical,
    )
    palette = ctx.theme.palette
    border = ctx.config.output.style.border
    margin = ctx.document_metrics.margin

    def draw_at(d, origin):
        d.append(
            draw.Rectangle(
                x=origin.x + margin,
                y=origin.y + margin,
                width=size.width - 2 * margin,
                height=size.height - 2 * margin,
                rx=border.radius if border else None,
                ry=border.radius if border else None,
                fill=palette.background_color,
                stroke=palette.border_color if border else None,
                stroke_width=border.width if border else None,
            )
        )
        content.draw_at(d, origin.offset(content_padding.left, content_padding.top))

    return size, draw_at


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------


def render(
    *,
    body: Component,
    content_w: float,
    footer_section_title: str | None,
) -> draw.Drawing:
    """Wrap ``body`` in the standard chrome (header / footer / border).

    ``body`` is whatever sits between the header and the footer — for
    standalone images that's a single :func:`MacroSection` or
    :func:`TapDanceSection`; for the combined image it's a Row of
    one of each separated by a Spacer. ``footer_section_title``
    controls the per-image footer height cap (see
    :func:`_footer_max_height`); pass ``None`` for images without a
    single dominant section title.
    """
    ctx = current_render_context()
    metrics = ctx.document_metrics
    geom = _LegendGeometry.for_doc_width(ctx.config.output.layout.width)

    header = Header(
        title=_resolve_title(ctx.config),
        gap=2 * metrics.padding,
        max_width=content_w,
    )

    children: list[Component] = [
        header,
        Spacer(height=geom.title_rule_offset * 0.5),
        body,
    ]

    footer_text = ctx.config.output.copyright or ""
    if footer_text:
        # Footer knows it's right-aligned — give it the slot width
        # and it paints the text at the right edge itself, no parent
        # alignment wrapper needed.
        footer = Footer(
            text=footer_text,
            width=content_w,
            max_height=_footer_max_height(section_title=footer_section_title),
        )
        children.extend([Spacer(height=metrics.bottom_inset), footer])

    column = Column(children, align="start")
    document = KeymapDocument(
        content=column,
        content_padding=Padding(
            top=metrics.padding,
            right=metrics.padding,
            left=metrics.padding,
            bottom=metrics.bottom_inset,
        ),
    )
    return _make_drawing(document)


def _make_drawing(content: Component) -> draw.Drawing:
    """Create the SVG ``Drawing`` for ``content`` and paint it.

    Displays at the user-requested ``layout.width`` and exposes the
    natural canvas via ``viewBox`` so the requested ``--width`` is
    honoured while content scales proportionally.
    """
    ctx = current_render_context()
    canvas_w = content.size.width
    canvas_h = content.size.height
    display_w = ctx.config.output.layout.width
    display_h = canvas_h * (display_w / canvas_w) if canvas_w else canvas_h

    d = draw.Drawing(display_w, display_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

    if not ctx.config.output.style.use_system_fonts:
        for font in Font:
            d.append_css(font.css_style)

    content.draw_at(d, Point(0, 0))
    return d


__all__ = [
    "BODY_SCALE",
    "KeymapDocument",
    "render",
]
