# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The keymap document chrome and assembly helpers.

A "keymap document" is the outermost rendered artifact of any
standalone special-keys image: the rounded background border, the
header (keymap title + Svalboard logo), zero-or-more labeled body
sections, and an optional copyright footer.

This module owns:

* :func:`KeymapDocument` — the outermost composable (rounded border
  around the rest of the content).
* :func:`LabeledSection` — a section with a :func:`SectionStripe`
  header and a body Component beneath. Used directly by standalone
  images and stacked side-by-side via Row in the combined image.
* :func:`render` — assembles header + body + (optional) footer into
  a :class:`KeymapDocument` and produces the final ``draw.Drawing``.
* :func:`render_single_section_document` — convenience wrapper for
  the standalone macros / tap-dances images that always render
  exactly one labeled section.
* :data:`BODY_SCALE` — the per-image body magnification multiplier
  used by the standalone images so chips and cells read at a visual
  weight comparable to layout keys.
"""

from __future__ import annotations

import drawsvg as draw

from .composable import (
    Align,
    BaseComponent,
    Column,
    Component,
    Composable,
    Padding,
    Point,
    Spacer,
)
from .footer import Footer
from .header import Header
from .legend import _LegendGeometry
from .render_context import current_render_context
from .section_stripe import SectionStripe
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
def KeymapDocument(ctx, *, content: Component):
    """The outermost composable — rounded background border around ``content``.

    The natural size matches ``content`` exactly — the border is
    painted INSIDE that extent, inset by ``ctx.document_metrics.margin``,
    mirroring the historical positional layout (where the border
    surrounded the canvas minus margin and the content sat at offset
    ``padding`` from the canvas edge). The content's :meth:`draw_at`
    runs at the same origin so its top-left aligns with the document
    top-left.
    """
    size = content.size
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
        content.draw_at(d, origin)

    return size, draw_at


# ---------------------------------------------------------------------------
# Labeled section + render helpers
# ---------------------------------------------------------------------------


def LabeledSection(
    *,
    title: str,
    color: str,
    count: int,
    width: float,
    body: Component,
) -> BaseComponent:
    """One section as a Column: ``SectionStripe`` + spacer + body.

    The same shape both standalone images and the combined image use —
    the combined image places two of these side-by-side in a Row.
    Reads the inter-strip / body gap from the unscaled section-stripe
    geometry so the spacing matches what every image variant uses.
    """
    ctx = current_render_context()
    geom = _LegendGeometry.for_doc_width(ctx.config.output.layout.width)
    return Column(
        [
            SectionStripe(title=title, count=count, width=width, accent_line=color),
            Spacer(height=2 * geom.title_baseline_offset),
            body,
        ],
        align="start",
    )


def render(
    *,
    body: Component,
    content_w: float,
    footer_section_title: str | None,
) -> draw.Drawing:
    """Wrap ``body`` in the standard chrome (header / footer / border).

    ``body`` is whatever sits between the header and the footer — for
    standalone images that's a single :func:`LabeledSection`; for the
    combined image it's a Row of two labeled sections separated by a
    Spacer. ``footer_section_title`` controls the per-image footer
    height cap (see :func:`_footer_max_height`); pass ``None`` for
    images without a single dominant section title.
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
        footer = Footer(
            text=footer_text,
            max_height=_footer_max_height(section_title=footer_section_title),
        )
        children.extend(
            [
                Spacer(height=metrics.bottom_inset),
                Align(footer, width=content_w, horizontal="end"),
            ]
        )

    column = Column(children, align="start")
    padded = Padding(
        column,
        top=metrics.padding,
        right=metrics.padding,
        left=metrics.padding,
        bottom=metrics.bottom_inset,
    )
    document = KeymapDocument(content=padded)
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


def render_single_section_document(
    *,
    body: Component,
    section_title: str,
    section_color: str,
    section_count: int,
    content_w: float,
) -> draw.Drawing:
    """Wrap a single section's ``body`` in the standard chrome.

    Convenience wrapper around :func:`render` that builds the
    one-section :func:`LabeledSection` for callers that only ever need
    a single :class:`SectionStripe`.
    """
    section = LabeledSection(
        title=section_title,
        color=section_color,
        count=section_count,
        width=content_w,
        body=body,
    )
    return render(
        body=section,
        content_w=content_w,
        footer_section_title=section_title,
    )


__all__ = [
    "BODY_SCALE",
    "KeymapDocument",
    "LabeledSection",
    "render",
    "render_single_section_document",
]
