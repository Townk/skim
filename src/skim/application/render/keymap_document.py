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
  Row of both) inside a ``with Column(...)`` block, then wraps the
  result in :func:`KeymapDocument` for the rounded border.
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
from .primitives import Column, Component, Padding, Row, Size, Spacer

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
# Helpers
# ---------------------------------------------------------------------------


def _resolve_title(config) -> str:
    """Pick the keymap title to render in the top-left of the image."""
    if config.output.keymap_title:
        return config.output.keymap_title
    if config.keyboard.layers:
        first = config.keyboard.layers[0]
        return f"{first.variant or first.name} Layers Layout"
    return "Keymap Layout"


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
# Concrete document composables
# ---------------------------------------------------------------------------


def _document_padding(metrics) -> Padding:
    """The standard outer-content inset used by every keymap document."""
    return Padding(
        top=metrics.padding,
        right=metrics.padding,
        left=metrics.padding,
        bottom=metrics.bottom_inset,
    )


@Composable(use_context=True)
def KeymapMacroDocument(ctx, *, macros: list, scale: float = BODY_SCALE):
    """The full standalone macros image as a single composable.

    When ``macros`` is empty there's no document to render — return
    a zero-sized :func:`Spacer` so the caller skips painting.

    Wrap-detection: when no row would wrap at the user-requested
    canvas width, the section snug-fits its natural width and the
    canvas shrinks to wrap it. Otherwise the canvas keeps its
    user-requested width and the existing pill-wrap logic handles
    the overflow.
    """
    if not macros:
        return Spacer()

    # Local import — :mod:`macros` imports from this module.
    from .macros import MacroSection, macro_natural_widths

    metrics = ctx.document_metrics
    initial_content_w = metrics.doc_width - 2 * metrics.padding

    natural_widths = macro_natural_widths(macros, metrics.doc_width * scale)
    longest_natural = max(natural_widths) if natural_widths else 0.0
    no_wrapping = longest_natural <= initial_content_w
    content_w = longest_natural if (no_wrapping and longest_natural > 0) else initial_content_w

    section = MacroSection(macros=macros, content_width=content_w, scale=scale)

    with Column(gap=section.metrics.rule_offset * 0.5, align="start") as content:
        Header(
            title=_resolve_title(ctx.config),
            gap=2 * metrics.padding,
            max_width=content_w,
        )
        content.add(section)
        if ctx.config.output.copyright:
            Footer(text=ctx.config.output.copyright, width=content_w)

    return KeymapDocument(content=content, content_padding=_document_padding(metrics))


@Composable(use_context=True)
def KeymapTapDanceDocument(ctx, *, tap_dances: list, scale: float = BODY_SCALE):
    """The full standalone tap-dances image as a single composable.

    When ``tap_dances`` is empty there's no document to render —
    return a zero-sized :func:`Spacer` so the caller skips painting.

    Builds the ``TAP-DANCE`` :func:`TapDanceSection` with the canvas
    content width as the table's ``max_width`` budget — the table
    either snugly wraps its content (and the canvas shrinks to
    match) or stretches to the budget and truncates the longest
    names with ``"…"`` when they can't fit.
    """
    if not tap_dances:
        return Spacer()

    # Local import — :mod:`tap_dance` imports from this module.
    from .tap_dance import TapDanceSection

    metrics = ctx.document_metrics
    initial_content_w = metrics.doc_width - 2 * metrics.padding

    section = TapDanceSection(tap_dances=tap_dances, scale=scale, max_width=initial_content_w)
    content_w = section.size.width

    with Column(gap=section.metrics.rule_offset * 0.5, align="start") as content:
        Header(
            title=_resolve_title(ctx.config),
            gap=2 * metrics.padding,
            max_width=content_w,
        )
        content.add(section)
        if ctx.config.output.copyright:
            Footer(text=ctx.config.output.copyright, width=content_w)

    return KeymapDocument(content=content, content_padding=_document_padding(metrics))


@Composable(use_context=True)
def KeymapSpecialKeysDocument(
    ctx,
    *,
    macros: list,
    tap_dances: list,
    scale: float = BODY_SCALE,
):
    """The combined macros + tap-dances image as a single composable.

    When both ``macros`` and ``tap_dances`` are empty there's no
    document to render — return a zero-sized :func:`Spacer` so the
    caller skips painting.

    Macros section on the left, tap-dances on the right, separated
    by ``geom.column_gap``. Falls back to a single-column layout
    when only one of the two has content.
    """
    if not macros and not tap_dances:
        return Spacer()

    # Local imports — both modules import from this one.
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

    # Build sections first so we can read their ``rule_offset`` for
    # the document gap and attach them inside the with-block via
    # ``content.add(...)``. Both sections expose the same
    # ``rule_offset`` (they derive it from the shared section-stripe
    # metrics), so either one drives the document gap.
    macro_section = (
        MacroSection(macros=macros, content_width=col_w, width=col_w, scale=scale)
        if macros
        else None
    )
    td_section = (
        TapDanceSection(
            tap_dances=tap_dances,
            width=col_w,
            scale=scale,
            name_column_width=_td_name_column_width(scaled_geom, tap_dances),
        )
        if tap_dances
        else None
    )
    gap_source = macro_section or td_section
    assert gap_source is not None  # guaranteed by the empty-check above

    with Column(gap=gap_source.metrics.rule_offset * 0.5, align="start") as content:
        Header(
            title=_resolve_title(ctx.config),
            gap=2 * metrics.padding,
            max_width=target_content_w,
        )
        if macro_section and td_section:
            with Row(gap=col_gap, align="top") as body_row:
                body_row.add(macro_section)
                body_row.add(td_section)
        elif macro_section:
            content.add(macro_section)
        else:
            assert td_section is not None
            content.add(td_section)
        if ctx.config.output.copyright:
            Footer(text=ctx.config.output.copyright, width=target_content_w)

    return KeymapDocument(content=content, content_padding=_document_padding(metrics))


__all__ = [
    "BODY_SCALE",
    "KeymapDocument",
    "KeymapMacroDocument",
    "KeymapSpecialKeysDocument",
    "KeymapTapDanceDocument",
]
