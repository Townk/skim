# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The keymap-document composables — top component for every image.

A "keymap document" is the outermost rendered artifact of any image
the renderer produces: the rounded background border, the header
(keymap title + Svalboard logo), the body, and an optional copyright
footer. Every entry point in :mod:`skim.application.render` reduces
to ``render(<SomeDocument>(...))``.

This module owns:

* :func:`KeymapDocument` — the outermost composable (rounded border
  + content padding around any inner content). Every concrete
  document below wraps its assembled column in this one.
* The concrete document composables:
    * :func:`KeymapLayerDocument` — per-layer keymap image.
    * :func:`KeymapOverviewDocument` — multi-layer overview image.
    * :func:`KeymapMacroDocument` / :func:`KeymapTapDanceDocument` /
      :func:`KeymapSpecialKeysDocument` — standalone special-keys
      images.
    * :func:`KeymapSymbolDocument` — standalone symbols image.
* :data:`BODY_SCALE` — the per-image body magnification multiplier
  used by the standalone special-keys / symbols images so chips and
  cells read at a visual weight comparable to layout keys.

Entry-point pattern
-------------------

Each ``draw_*_image`` function reduces to::

    def draw_macros_image(config, keymap):
        with using_render_context(RenderContext.build(config, keymap)):
            return render(KeymapMacroDocument(macros=...))

The document composable encodes the entire layout; the generic
:func:`composable.render` paints it into an SVG.

Body composables (``KeymapLayer``, ``KeymapOverview``,
``MacroSection``, ``TapDanceSection``, ``SymbolSection``) live in
their own modules. Those modules import ``KeymapDocument`` from this
file, so the concrete document factories below pull their bodies in
via local imports inside each function to keep the import graph
acyclic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import drawsvg as draw

from .composable import Composable
from .footer import Footer
from .header import Header
from .primitives import Column, Component, Row, Size, Spacer

if TYPE_CHECKING:
    from skim.data import KeycodeMappings, SvalboardKeymap, SvalboardLayout
    from skim.domain import SvalboardMacro, SvalboardTapDance, SvalboardTargetKey

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
def KeymapLayerDocument(
    ctx,
    *,
    layer: SvalboardLayout[SvalboardTargetKey],
    qmk_index: int,
    title: str,
    copyright: str | None = None,
    macros: tuple[SvalboardMacro[SvalboardTargetKey], ...] = (),
    tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...] = (),
    raw_layer_keycodes: list[str] | None = None,
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
):
    """The full per-layer keymap image as a single composable.

    Stacks :func:`Header`, :func:`KeymapLayer`, the optional
    macro / TD legend (:func:`MacroSection` next to
    :func:`TapDanceSection` in a :class:`Row` when both have
    content; whichever is non-empty alone otherwise), the optional
    symbol legend (:func:`SymbolSection`), and an optional
    :func:`Footer` in a :class:`Column`, then wraps in
    :func:`KeymapDocument` for the rounded background border +
    content_offset chrome.

    A falsy ``copyright`` (``None`` or ``""``) suppresses the
    footer. Macro / TD legend appears only when the style flag
    ``show_special_keys_legend`` is on AND the layer references
    at least one macro or tap-dance. Symbol legend appears only
    when ``show_symbol_legend`` is on AND
    ``raw_layer_keycodes`` + ``keycode_mappings`` are provided
    AND the layer has resolvable symbols.
    """
    from .keymap_layer import KeymapLayer
    from .legend import collect_used_ids, resolve_macros, resolve_tap_dances
    from .macros import MacroSection
    from .symbol_legend import collect_used_descriptions
    from .symbols import FlowDirection, SymbolSection
    from .tap_dance import TapDanceSection

    config = ctx.config
    metrics = ctx.document_metrics
    content_offset = metrics.margin + metrics.border_width + metrics.inset
    doc_content_w = metrics.doc_width - 2 * content_offset

    # Build the keyboard area first — its actual width may exceed the
    # configured ``doc_content_w`` when inward indicators bleed past
    # the keys-only edges and the column has to grow. Every other
    # child of the column (header / sections / footer) sizes against
    # the keyboard area's width so they fill the column edge-to-edge
    # rather than being left-aligned with a gap on the right.
    keymap_layer = KeymapLayer(
        layer=layer,
        qmk_index=qmk_index,
        target_content_w=doc_content_w,
    )
    content_w = keymap_layer.size.width

    macro_entries: list = []
    td_entries: list = []
    if config.output.style.show_special_keys_legend:
        used_macro_ids, used_td_ids = collect_used_ids(layer)
        macro_entries = resolve_macros(used_macro_ids, macros)
        td_entries = resolve_tap_dances(used_td_ids, tap_dances)

    # Macro / TD section width split — same policy as
    # :func:`KeymapSpecialKeysDocument`. Half the content width
    # each when both have content; the full content width when
    # only one section is present.
    col_gap = metrics.column_gap
    col_w = (content_w - col_gap) / 2 if macro_entries and td_entries else content_w
    macro_section = (
        MacroSection(macros=macro_entries, content_width=col_w) if macro_entries else None
    )
    td_section = TapDanceSection(tap_dances=td_entries, max_width=col_w) if td_entries else None

    symbol_section = None
    if config.output.style.show_symbol_legend and raw_layer_keycodes and keycode_mappings:
        symbol_entries = collect_used_descriptions(
            raw_layer_keycodes,
            raw_keymap,
            keycode_mappings,
            include_transparent=not config.output.style.show_transparent_fallthrough,
        )
        if symbol_entries:
            flow_value = config.output.style.symbol_legend_flow.value
            typed_flow: FlowDirection = "row" if flow_value == "row" else "column"
            symbol_section = SymbolSection(
                entries=symbol_entries,
                max_width=content_w,
                column_count=config.output.style.symbol_legend_columns,
                flow=typed_flow,
            )

    with Column(gap=metrics.inset, align="start") as content:
        Header(
            title=title,
            min_gap=2 * metrics.inset,
            max_width=content_w,
        )
        content.add(keymap_layer)
        if macro_section and td_section:
            Row([macro_section, td_section], gap=col_gap, align="top")
        elif macro_section:
            content.add(macro_section)
        elif td_section:
            content.add(td_section)
        if symbol_section is not None:
            content.add(symbol_section)
        if copyright:
            Footer(text=copyright, max_width=content_w)

    return KeymapDocument(content=content)


@Composable(use_context=True)
def KeymapOverviewDocument(
    ctx,
    *,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    title: str,
    copyright: str | None = None,
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
):
    """The full overview image as a single composable.

    Stacks :func:`Header`, :func:`KeymapOverview`, the optional macro
    / TD legend, the optional symbol legend, and an optional
    :func:`Footer` in a :class:`Column`, then wraps in
    :func:`KeymapDocument` for the rounded background border +
    content_offset chrome.

    When ``keymap`` has no layers there's nothing to render — return
    a zero-sized :func:`Spacer` so the caller skips painting.
    """
    from .keymap_overview import KeymapOverview
    from .legend import all_macros, all_tap_dances
    from .macros import MacroSection
    from .symbol_legend import collect_used_descriptions
    from .symbols import FlowDirection, SymbolSection
    from .tap_dance import TapDanceSection

    config = ctx.config
    metrics = ctx.document_metrics
    content_offset = metrics.margin + metrics.border_width + metrics.inset
    doc_content_w = metrics.doc_width - 2 * content_offset

    if not keymap.layers:
        return Spacer()

    body = KeymapOverview(keymap=keymap)
    content_w = max(body.size.width, doc_content_w)

    # Macro / TD legend — the overview shows ALL macros and tap-dances,
    # not just those used on a specific layer.
    macro_entries: list = []
    td_entries: list = []
    if config.output.style.show_special_keys_legend:
        macro_entries = all_macros(keymap.macros)
        td_entries = all_tap_dances(keymap.tap_dances)

    col_gap = metrics.column_gap
    col_w = (content_w - col_gap) / 2 if macro_entries and td_entries else content_w
    macro_section = (
        MacroSection(macros=macro_entries, content_width=col_w) if macro_entries else None
    )
    td_section = TapDanceSection(tap_dances=td_entries, max_width=col_w) if td_entries else None

    # Symbol legend — union across all rendered layers.
    symbol_section = None
    if (
        config.output.style.show_symbol_legend
        and raw_keymap is not None
        and keycode_mappings is not None
    ):
        all_raw_keycodes: list[str] = []
        for layer_cfg in config.keyboard.layers:
            qmk_idx = layer_cfg.index
            if qmk_idx in raw_keymap.layers and qmk_idx in keymap.layers:
                all_raw_keycodes.extend(k for k in raw_keymap.layers[qmk_idx] if k is not None)
        symbol_entries = collect_used_descriptions(
            all_raw_keycodes,
            raw_keymap,
            keycode_mappings,
            include_transparent=not config.output.style.show_transparent_fallthrough,
        )
        if symbol_entries:
            flow_value = config.output.style.symbol_legend_flow.value
            typed_flow: FlowDirection = "row" if flow_value == "row" else "column"
            symbol_section = SymbolSection(
                entries=symbol_entries,
                max_width=content_w,
                column_count=config.output.style.symbol_legend_columns,
                flow=typed_flow,
            )

    with Column(gap=metrics.inset, align="start") as content:
        Header(
            title=title,
            min_gap=2 * metrics.inset,
            max_width=content_w,
        )
        content.add(body)
        # Macro and tap-dance sections share a Row when both are
        # present, mirroring :func:`KeymapLayerDocument` /
        # :func:`KeymapSpecialKeysDocument`. ``col_gap`` is
        # ``metrics.column_gap`` — the canonical horizontal spacing.
        if macro_section is not None and td_section is not None:
            Row([macro_section, td_section], gap=col_gap, align="top")
        elif macro_section is not None:
            content.add(macro_section)
        elif td_section is not None:
            content.add(td_section)
        if symbol_section is not None:
            content.add(symbol_section)
        if copyright:
            Footer(text=copyright, max_width=content_w)

    return KeymapDocument(content=content)


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
    "KeymapLayerDocument",
    "KeymapMacroDocument",
    "KeymapOverviewDocument",
    "KeymapSpecialKeysDocument",
    "KeymapSymbolDocument",
    "KeymapTapDanceDocument",
]
