# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Standalone images for macros, tap-dances, and the combined special-keys legend.

These images surface the macro/tap-dance content from a keymap as their own
SVGs (no keyboard, no layer-specific filtering). They share the per-layer
image's outer chrome — rounded border, keymap title top-left, Svalboard
logo top-right, copyright bottom-right — and reuse the existing macro /
tap-dance row builders so the rendered chips and pills match the overview's
legend exactly.

Rendering pipeline
------------------

For all three images:

1. The outer chrome (header, footer, padding, margin, border) lays out
   at the user-requested ``config.output.layout.width`` — title and
   footer typography stay at the same per-layer-equivalent sizes.
2. The body composables (``_MacrosBody``, ``TapDanceTable``) render
   their chips, cells, pills and column labels at ``_BODY_SCALE``
   (currently ``1.5``) so the legend reads at a visual weight
   comparable to layout keys in a per-layer image.
3. After laying out the body, the canvas width may shrink to wrap the
   content snugly (TD table always; macros only when no row had to wrap).
4. The SVG ``width`` attribute is set back to the requested ``--width``
   and the natural (possibly shrunken) canvas is exposed via
   ``viewBox`` — the image displays at the requested width and the
   content scales proportionally.
"""

import drawsvg as draw

from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey

from .composable import (
    Align,
    BaseComponent,
    Column,
    Component,
    Composable,
    Padding,
    Point,
    Row,
    Size,
    Spacer,
)
from .footer import Footer
from .header import Header
from .legend import (
    _flatten_macro_pills,
    _layout_pill_lines,
    _LegendGeometry,
    _td_name_column_width,
    all_macros,
    all_tap_dances,
    build_macro_row,
    macro_row_height,
)
from .legend_components import SectionStripe, TapDanceTable
from .render_context import RenderContext, current_render_context, using_render_context
from .styling import derive_accent_line
from .text import Font

# The body of a standalone special-keys image (the macro / tap-dance
# section content) renders at this multiple of the configured document
# width — chips, cells, pills and column labels grow against the title
# / footer / outer paddings, which stay at their unscaled per-image
# sizes. The chosen multiplier (1.5×) makes the body comparable to the
# layout-key sizing of the per-layer images so a special-keys page reads
# at a similar visual weight to a per-layer page when displayed at the
# same width.
_BODY_SCALE = 1.5


# ---------------------------------------------------------------------------
# Helpers (ctx-aware)
# ---------------------------------------------------------------------------


def _resolve_title(config: SkimConfig) -> str:
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
# Composable image scaffolding
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def _CanvasFrame(ctx, *, content: Component):
    """Outer chrome: rounded background border around ``content``.

    The natural size matches ``content`` exactly — the border is
    painted INSIDE that extent, inset by ``ctx.document_metrics.margin``,
    mirroring the historical positional layout (where the border
    surrounded the canvas minus margin and the content sat at offset
    ``padding`` from the canvas edge). The content's :meth:`draw_at`
    runs at the same origin so its top-left aligns with the canvas
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


def _section_block(
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


def _render_image(
    *,
    body: Component,
    content_w: float,
    footer_section_title: str | None,
) -> draw.Drawing:
    """Wrap ``body`` in the standard chrome (header / footer / border).

    ``body`` is whatever sits between the header and the footer — for
    standalone images that's a single :func:`_section_block`; for the
    combined image it's a Row of two section blocks separated by a
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
    image = _CanvasFrame(content=padded)
    return _make_drawing(image)


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


def _render_section_image(
    *,
    body: Component,
    section_title: str,
    section_color: str,
    section_count: int,
    content_w: float,
) -> draw.Drawing:
    """Wrap a single section's ``body`` in the standard chrome.

    Convenience wrapper around :func:`_render_image` that builds the
    one-section :func:`_section_block` for callers that only ever need
    a single :class:`SectionStripe`.
    """
    section = _section_block(
        title=section_title,
        color=section_color,
        count=section_count,
        width=content_w,
        body=body,
    )
    return _render_image(
        body=section,
        content_w=content_w,
        footer_section_title=section_title,
    )


# ---------------------------------------------------------------------------
# Macros image
# ---------------------------------------------------------------------------


def _macro_natural_widths(macros: list, geom: _LegendGeometry) -> list[float]:
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
def _MacrosBody(
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
    against — the standalone macros image passes ``1.5`` so chips
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
        # The MACROS body renders at ``_BODY_SCALE``; use the scaled
        # geom for wrap-detection so ``_macro_natural_widths`` reports
        # the same widths the body composable will lay out against.
        scaled_geom = _LegendGeometry.for_doc_width(metrics.doc_width * _BODY_SCALE)
        macro_line = derive_accent_line(palette.macro_color)

        initial_content_w = metrics.doc_width - 2 * metrics.padding

        # Lay out using the *initial* content width so wrap detection matches
        # what the user-requested canvas would normally produce. If the longest
        # natural row fits within ``initial_content_w`` no row wraps and we can
        # shrink the canvas; otherwise we keep the canvas at ``--width`` and let
        # the existing pill-wrap logic handle the overflow.
        natural_widths = _macro_natural_widths(macros, scaled_geom)
        longest_natural = max(natural_widths) if natural_widths else 0.0
        no_wrapping = longest_natural <= initial_content_w
        content_w = longest_natural if (no_wrapping and longest_natural > 0) else initial_content_w

        body: Component = (
            _MacrosBody(
                macros=macros,
                accent_fill=palette.macro_color,
                accent_line=macro_line,
                text_color=palette.text_color,
                content_width=content_w,
                scale=_BODY_SCALE,
            )
            if macros
            else Spacer()
        )

        return _render_section_image(
            body=body,
            section_title="MACROS",
            section_color=macro_line,
            section_count=len(macros),
            content_w=content_w,
        )


# ---------------------------------------------------------------------------
# Tap-dances image
# ---------------------------------------------------------------------------


def draw_tap_dances_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the standalone tap-dances image.

    Builds the table via the :func:`TapDanceTable` composable with the
    canvas content width as the budget — the table either snugly wraps
    its content (and the canvas shrinks to match) or stretches to the
    budget and truncates the longest names with ``"…"`` when they
    can't fit.
    """
    with using_render_context(RenderContext.build(config, keymap)) as ctx:
        tap_dances = all_tap_dances(keymap.tap_dances)
        palette = ctx.theme.palette
        metrics = ctx.document_metrics
        td_line = derive_accent_line(palette.tap_dance_color)

        initial_content_w = metrics.doc_width - 2 * metrics.padding

        # Build the table component first so we can shrink the canvas to
        # match it. ``max_width`` caps the table at the canvas budget;
        # when names would overflow the cap they're auto-truncated.
        table = TapDanceTable(
            tap_dances=tap_dances,
            accent_fill=palette.tap_dance_color,
            accent_line=td_line,
            text_color=palette.text_color,
            scale=_BODY_SCALE,
            max_width=initial_content_w,
        )
        content_w = min(initial_content_w, table.size.width) if tap_dances else initial_content_w
        body: Component = table if tap_dances else Spacer()

        return _render_section_image(
            body=body,
            section_title="TAP-DANCE",
            section_color=td_line,
            section_count=len(tap_dances),
            content_w=content_w,
        )


# ---------------------------------------------------------------------------
# Special-keys image (macros + tap-dances side by side, 1.5× scale)
# ---------------------------------------------------------------------------


def draw_special_keys_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the combined special-keys image (macros left, tap-dances right).

    Mirrors the overview's two-column legend, just at the standalone scale.
    Falls back to a single column when only one section has content.
    """
    with using_render_context(RenderContext.build(config, keymap)) as ctx:
        macros = all_macros(keymap.macros)
        tap_dances = all_tap_dances(keymap.tap_dances)
        palette = ctx.theme.palette
        metrics = ctx.document_metrics
        # Bodies render at ``_BODY_SCALE``; the static name-column
        # width and the cross-column gap are computed against the
        # scaled geom so the two columns keep their proportions.
        scaled_geom = _LegendGeometry.for_doc_width(metrics.doc_width * _BODY_SCALE)
        macro_line = derive_accent_line(palette.macro_color)
        td_line = derive_accent_line(palette.tap_dance_color)

        target_content_w = metrics.doc_width - 2 * metrics.padding
        col_gap = scaled_geom.column_gap
        col_w = (target_content_w - col_gap) / 2 if macros and tap_dances else target_content_w

        sections: list[Component] = []
        if macros:
            sections.append(
                _section_block(
                    title="MACROS",
                    color=macro_line,
                    count=len(macros),
                    width=col_w,
                    body=_MacrosBody(
                        macros=macros,
                        accent_fill=palette.macro_color,
                        accent_line=macro_line,
                        text_color=palette.text_color,
                        content_width=col_w,
                        scale=_BODY_SCALE,
                    ),
                )
            )
        if tap_dances:
            # Pin the legacy ``_td_name_column_width`` so the combined image
            # keeps its overview-style fixed name column instead of the
            # dynamic sizing the standalone tap-dances image uses.
            td_table = TapDanceTable(
                tap_dances=tap_dances,
                accent_fill=palette.tap_dance_color,
                accent_line=td_line,
                text_color=palette.text_color,
                scale=_BODY_SCALE,
                name_column_width=_td_name_column_width(scaled_geom, tap_dances),
            )
            sections.append(
                _section_block(
                    title="TAP-DANCE",
                    color=td_line,
                    count=len(tap_dances),
                    width=col_w,
                    body=td_table,
                )
            )

        if not sections:
            body: Component = Spacer()
        elif len(sections) == 1:
            body = sections[0]
        else:
            body = Row([sections[0], Spacer(width=col_gap), sections[1]], align="top")

        return _render_image(
            body=body,
            content_w=target_content_w,
            # Combined image has no single dominant section title, so the
            # footer keeps its natural size (matches the per-layer/overview).
            footer_section_title=None,
        )
