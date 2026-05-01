# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The keymap-document composables.

A "keymap document" is the outermost rendered artifact of any
standalone special-keys image: the rounded background border, the
header (keymap title + Svalboard logo), the body, and an optional
copyright footer.

This module owns:

* :func:`KeymapDocument` — the outermost composable (rounded border
  + content padding around any inner content).
* :func:`KeymapMacroDocument` / :func:`KeymapTapDanceDocument` /
  :func:`KeymapSpecialKeysDocument` — the three concrete document
  composables. Each one fully renders itself: it builds its
  appropriate body section (``MacroSection`` / ``TapDanceSection`` /
  Row of both), wraps it in the document chrome (header + body +
  optional footer + border), and returns the complete component.
* :data:`BODY_SCALE` — the per-image body magnification multiplier
  used by the standalone images so chips and cells read at a visual
  weight comparable to layout keys.

Entry-point pattern
-------------------

Each ``draw_*_image`` function reduces to::

    def draw_macros_image(config, keymap):
        with using_render_context(RenderContext.build(config, keymap)):
            return render(KeymapMacroDocument(macros=...))

The ``KeymapMacroDocument`` composable encodes the entire layout;
the generic :func:`composable.render` paints it into an SVG.
"""

from __future__ import annotations

import drawsvg as draw

from .composable import Composable
from .footer import Footer
from .header import Header
from .legend import _LegendGeometry, _td_name_column_width
from .primitives import Column, Component, Padding, Row, Spacer
from .render_context import current_render_context
from .section_stripe import SectionStripeMetrics
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
    from .primitives import Size

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
# Document chrome assembly
# ---------------------------------------------------------------------------


def _with_document_chrome(
    body: Component,
    *,
    footer_section_title: str | None,
) -> Component:
    """Wrap ``body`` in header + (optional) footer + outer border.

    ``body`` is whatever the document's main content is — for
    standalone images that's a single :func:`MacroSection` /
    :func:`TapDanceSection`; for the combined image it's a Row of
    one of each. The chrome derives the slot width from
    ``body.size.width`` so the header spans the same width as the
    content beneath it (and the footer right-aligns inside the same
    width).

    ``footer_section_title`` controls the per-image footer height
    cap (see :func:`_footer_max_height`); pass ``None`` when there's
    no single dominant section title (the combined image).
    """
    ctx = current_render_context()
    metrics = ctx.document_metrics
    stripe_metrics = SectionStripeMetrics.for_doc_width(metrics.doc_width)
    content_w = body.size.width

    header = Header(
        title=_resolve_title(ctx.config),
        gap=2 * metrics.padding,
        max_width=content_w,
    )

    # Header → body uses half of the section-stripe rule offset (a
    # tuned breathing-room constant); body → footer uses the
    # canvas's bottom inset so the footer sits flush against the
    # bottom margin. Different gaps so the column structure is
    # nested rather than mixing per-pair gaps in one Column.
    body_block = Column(
        [header, body],
        gap=stripe_metrics.rule_offset * 0.5,
        align="start",
    )

    footer_text = ctx.config.output.copyright or ""
    if footer_text:
        footer = Footer(
            text=footer_text,
            width=content_w,
            max_height=_footer_max_height(section_title=footer_section_title),
        )
        full_block = Column([body_block, footer], gap=metrics.bottom_inset, align="start")
    else:
        full_block = body_block

    return KeymapDocument(
        content=full_block,
        content_padding=Padding(
            top=metrics.padding,
            right=metrics.padding,
            left=metrics.padding,
            bottom=metrics.bottom_inset,
        ),
    )


# ---------------------------------------------------------------------------
# Concrete document composables
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def KeymapMacroDocument(ctx, *, macros: list, scale: float = BODY_SCALE):
    """The full standalone macros image as a single composable.

    Builds the ``MACROS`` :func:`MacroSection` at ``scale`` and wraps
    it in the standard document chrome (header + optional footer +
    rounded border + content padding). Empty ``macros`` produces a
    chrome-only document with a zero-sized body.

    Wrap-detection: when no row would wrap at the user-requested
    canvas width, the section snug-fits its natural width and the
    canvas shrinks to wrap it. Otherwise the canvas keeps its
    user-requested width and the existing pill-wrap logic handles
    the overflow.
    """
    # Local import — :mod:`macros` imports from this module, so
    # importing eagerly would create a cycle.
    from .macros import MacroSection, macro_natural_widths

    metrics = ctx.document_metrics
    initial_content_w = metrics.doc_width - 2 * metrics.padding

    natural_widths = macro_natural_widths(macros, metrics.doc_width * scale)
    longest_natural = max(natural_widths) if natural_widths else 0.0
    no_wrapping = longest_natural <= initial_content_w
    content_w = longest_natural if (no_wrapping and longest_natural > 0) else initial_content_w

    body: Component = (
        MacroSection(macros=macros, content_width=content_w, scale=scale) if macros else Spacer()
    )
    document = _with_document_chrome(body, footer_section_title="MACROS")
    return document.size, document.draw_at


@Composable(use_context=True)
def KeymapTapDanceDocument(ctx, *, tap_dances: list, scale: float = BODY_SCALE):
    """The full standalone tap-dances image as a single composable.

    Builds the ``TAP-DANCE`` :func:`TapDanceSection` at ``scale``
    with the canvas content width as the table's ``max_width``
    budget — the table either snugly wraps its content (and the
    canvas shrinks to match) or stretches to the budget and
    truncates the longest names with ``"…"`` when they can't fit.
    Wraps the result in the standard document chrome.
    """
    # Local import — see :func:`KeymapMacroDocument`.
    from .tap_dance import TapDanceSection

    metrics = ctx.document_metrics
    initial_content_w = metrics.doc_width - 2 * metrics.padding

    body: Component = (
        TapDanceSection(tap_dances=tap_dances, scale=scale, max_width=initial_content_w)
        if tap_dances
        else Spacer()
    )
    document = _with_document_chrome(body, footer_section_title="TAP-DANCE")
    return document.size, document.draw_at


@Composable(use_context=True)
def KeymapSpecialKeysDocument(
    ctx,
    *,
    macros: list,
    tap_dances: list,
    scale: float = BODY_SCALE,
):
    """The combined macros + tap-dances image as a single composable.

    Macros section on the left, tap-dances on the right, separated
    by ``geom.column_gap``. Falls back to a single-column layout
    when only one of the two has content. Wraps the result in the
    standard document chrome.
    """
    # Local imports — see :func:`KeymapMacroDocument`.
    from .macros import MacroSection
    from .tap_dance import TapDanceSection

    metrics = ctx.document_metrics
    # Bodies render at ``scale``; the static name-column width and
    # the cross-column gap are computed against the scaled geom so
    # the two columns keep their proportions.
    scaled_geom = _LegendGeometry.for_doc_width(metrics.doc_width * scale)

    target_content_w = metrics.doc_width - 2 * metrics.padding
    col_gap = scaled_geom.column_gap
    col_w = (target_content_w - col_gap) / 2 if macros and tap_dances else target_content_w

    sections: list[Component] = []
    if macros:
        sections.append(MacroSection(macros=macros, content_width=col_w, width=col_w, scale=scale))
    if tap_dances:
        # Pin the legacy ``_td_name_column_width`` so the combined image
        # keeps its overview-style fixed name column instead of the
        # dynamic sizing the standalone tap-dances image uses.
        sections.append(
            TapDanceSection(
                tap_dances=tap_dances,
                width=col_w,
                scale=scale,
                name_column_width=_td_name_column_width(scaled_geom, tap_dances),
            )
        )

    if not sections:
        body: Component = Spacer()
    elif len(sections) == 1:
        body = sections[0]
    else:
        body = Row([sections[0], Spacer(width=col_gap), sections[1]], align="top")

    # Combined image has no single dominant section title, so the
    # footer keeps its natural size (matches the per-layer/overview).
    document = _with_document_chrome(body, footer_section_title=None)
    return document.size, document.draw_at


__all__ = [
    "BODY_SCALE",
    "KeymapDocument",
    "KeymapMacroDocument",
    "KeymapSpecialKeysDocument",
    "KeymapTapDanceDocument",
]
