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
from .primitives import Column, Component, Row, Size, Spacer

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
# Outer chrome
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def KeymapDocument(ctx, *, content: Component):
    """The outermost composable — rounded background border + content offset.

    Owns the document-level chrome on every side:

    * The rounded background border, stroked at
      ``ctx.document_metrics.margin`` from the canvas edge.
    * The canvas-edge → content offset, computed as
      ``margin + border_width + inset`` so the content sits inside
      the border with ``inset`` of breathing room on every side.

    The document's reported size grows by ``2 * (margin + border_width
    + inset)`` on each axis so the canvas wraps the offset content
    exactly.
    """
    metrics = ctx.document_metrics
    content_offset = metrics.margin + metrics.border_width + metrics.inset
    size = Size(
        content.size.width + 2 * content_offset,
        content.size.height + 2 * content_offset,
    )
    palette = ctx.theme.palette
    border = ctx.config.output.style.border
    margin = metrics.margin

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
        content.draw_at(d, origin.offset(content_offset, content_offset))

    return size, draw_at


# ---------------------------------------------------------------------------
# Concrete document composables
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def KeymapMacroDocument(
    ctx,
    *,
    macros: list,
    title: str,
    copyright: str | None = None,
    scale: float = BODY_SCALE,
):
    """The full standalone macros image as a single composable.

    When ``macros`` is empty there's no document to render — return
    a zero-sized :func:`Spacer` so the caller skips painting.

    Wrap-detection: when no row would wrap at the user-requested
    canvas width, the section snug-fits its natural width and the
    canvas shrinks to wrap it. Otherwise the canvas keeps its
    user-requested width and the existing pill-wrap logic handles
    the overflow.

    ``title`` and ``copyright`` are passed in by the entry point —
    the composable doesn't reach into ``ctx.config`` for either.
    A falsy ``copyright`` (``None`` or ``""``) suppresses the footer.
    """
    if not macros:
        return Spacer()

    # Local import — :mod:`macros` imports from this module.
    from .macros import MacroSection, macro_natural_widths

    metrics = ctx.document_metrics
    content_offset = metrics.margin + metrics.border_width + metrics.inset
    initial_content_w = metrics.doc_width - 2 * content_offset

    natural_widths = macro_natural_widths(macros, scale=scale)
    longest_natural = max(natural_widths) if natural_widths else 0.0
    no_wrapping = longest_natural <= initial_content_w
    content_w = longest_natural if (no_wrapping and longest_natural > 0) else initial_content_w

    section = MacroSection(macros=macros, content_width=content_w, wrap_content=True, scale=scale)

    with Column(gap=metrics.inset, align="start") as content:
        Header(title=title, min_gap=2 * metrics.inset, max_width=content_w)
        content.add(section)
        if copyright:
            Footer(text=copyright, max_width=content_w)

    return KeymapDocument(content=content)


@Composable(use_context=True)
def KeymapTapDanceDocument(
    ctx,
    *,
    tap_dances: list,
    title: str,
    copyright: str | None = None,
    scale: float = BODY_SCALE,
):
    """The full standalone tap-dances image as a single composable.

    When ``tap_dances`` is empty there's no document to render —
    return a zero-sized :func:`Spacer` so the caller skips painting.

    Builds the ``TAP-DANCE`` :func:`TapDanceSection` with the canvas
    content width as the table's ``max_width`` budget — the table
    either snugly wraps its content (and the canvas shrinks to
    match) or stretches to the budget and truncates the longest
    names with ``"…"`` when they can't fit.

    ``title`` and ``copyright`` are passed in by the entry point —
    the composable doesn't reach into ``ctx.config`` for either.
    A falsy ``copyright`` (``None`` or ``""``) suppresses the footer.
    """
    if not tap_dances:
        return Spacer()

    # Local import — :mod:`tap_dance` imports from this module.
    from .tap_dance import TapDanceSection

    metrics = ctx.document_metrics
    content_offset = metrics.margin + metrics.border_width + metrics.inset
    initial_content_w = metrics.doc_width - 2 * content_offset

    section = TapDanceSection(
        tap_dances=tap_dances,
        wrap_content=True,
        scale=scale,
        max_width=initial_content_w,
    )
    content_w = section.size.width

    with Column(gap=metrics.inset, align="start") as content:
        Header(title=title, min_gap=2 * metrics.inset, max_width=content_w)
        content.add(section)
        if copyright:
            Footer(text=copyright, max_width=content_w)

    return KeymapDocument(content=content)


@Composable(use_context=True)
def KeymapSpecialKeysDocument(
    ctx,
    *,
    macros: list,
    tap_dances: list,
    title: str,
    copyright: str | None = None,
):
    """The combined macros + tap-dances image as a single composable.

    When both ``macros`` and ``tap_dances`` are empty there's no
    document to render — return a zero-sized :func:`Spacer` so the
    caller skips painting.

    Macros section on the left, tap-dances on the right, separated
    by ``metrics.column_gap``. Falls back to a single-column layout
    when only one of the two has content. Bodies render at their
    natural (unscaled) size — only the standalone single-section
    images use ``BODY_SCALE``.

    ``title`` and ``copyright`` are passed in by the entry point —
    the composable doesn't reach into ``ctx.config`` for either.
    A falsy ``copyright`` (``None`` or ``""``) suppresses the footer.
    """
    if not macros and not tap_dances:
        return Spacer()

    # Local imports — both modules import from this one.
    from .macros import MacroSection
    from .tap_dance import TapDanceSection

    metrics = ctx.document_metrics
    content_offset = metrics.margin + metrics.border_width + metrics.inset

    target_content_w = metrics.doc_width - 2 * content_offset
    col_gap = metrics.column_gap
    col_w = (target_content_w - col_gap) / 2 if macros and tap_dances else target_content_w

    # Pre-build sections so they can be attached inside the with-block
    # via ``content.add(...)`` / ``body_row.add(...)``.
    #
    # ``max_width=col_w`` on the TD section lets the named-chip area
    # grow until it either fits the longest name or hits the column's
    # right edge (which lines up with the document's right padding).
    # Without it the table falls back to the legacy fixed name-column
    # width and either over-truncates short names or fails to fit
    # long ones.
    macro_section = MacroSection(macros=macros, content_width=col_w) if macros else None
    td_section = TapDanceSection(tap_dances=tap_dances, max_width=col_w) if tap_dances else None

    with Column(gap=metrics.inset, align="start") as content:
        Header(title=title, min_gap=2 * metrics.inset, max_width=target_content_w)
        if macro_section and td_section:
            Row([macro_section, td_section], gap=col_gap, align="top")
        elif macro_section:
            content.add(macro_section)
        elif td_section:
            content.add(td_section)
        if copyright:
            Footer(text=copyright, max_width=target_content_w)

    return KeymapDocument(content=content)


@Composable(use_context=True)
def KeymapSymbolDocument(
    ctx,
    *,
    entries: list,
    title: str,
    copyright: str | None = None,
    flow: str = "column",
    scale: float = BODY_SCALE,
):
    """The full standalone symbols image as a single composable.

    When ``entries`` is empty there's no document to render — return
    a zero-sized :func:`Spacer` so the caller skips painting.

    Builds the ``SYMBOLS`` :func:`SymbolSection` using the canvas
    content width as the table's ``max_width`` budget; the table
    picks the largest column count that fits and the canvas snugs to
    the actual painted width.

    ``title`` and ``copyright`` are passed in by the entry point —
    the composable doesn't reach into ``ctx.config`` for either.
    A falsy ``copyright`` (``None`` or ``""``) suppresses the footer.

    ``flow`` mirrors :class:`symbols.FlowDirection` — accepts the
    string ``"row"`` or ``"column"``; anything else falls back to
    ``"column"``-major (the historical default).
    """
    if not entries:
        return Spacer()

    # Local import — :mod:`symbols` imports from this module.
    from .symbols import FlowDirection, SymbolSection

    metrics = ctx.document_metrics
    content_offset = metrics.margin + metrics.border_width + metrics.inset
    initial_content_w = metrics.doc_width - 2 * content_offset
    typed_flow: FlowDirection = "row" if flow == "row" else "column"
    column_count = ctx.config.output.style.symbol_legend_columns

    section = SymbolSection(
        entries=entries,
        max_width=initial_content_w,
        wrap_content=True,
        column_count=column_count,
        flow=typed_flow,
        scale=scale,
    )
    content_w = section.size.width

    with Column(gap=metrics.inset, align="start") as content:
        Header(title=title, min_gap=2 * metrics.inset, max_width=content_w)
        content.add(section)
        if copyright:
            Footer(text=copyright, max_width=content_w)

    return KeymapDocument(content=content)


__all__ = [
    "BODY_SCALE",
    "KeymapDocument",
    "KeymapMacroDocument",
    "KeymapSpecialKeysDocument",
    "KeymapSymbolDocument",
    "KeymapTapDanceDocument",
]
