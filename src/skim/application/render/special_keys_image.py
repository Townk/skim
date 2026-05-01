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
legend exactly, just at a larger scale.

Rendering pipeline
------------------

For all three images:

1. The geometry is built at ``1.5 × config.output.layout.width`` so chips,
   fonts, paddings and the title scale together. The initial canvas width
   matches the requested ``--width`` so the layout respects the user's size.
2. After laying out the body, the canvas width may shrink to wrap the
   content snugly (TD table always; macros only when no row had to wrap).
3. The SVG ``width`` attribute is set back to the requested ``--width`` and
   the natural (possibly shrunken) canvas is exposed via ``viewBox`` — the
   image displays at the requested width and the content scales
   proportionally.

The keymap title and Svalboard logo therefore both scale together with the
chips and pills, since everything lives inside the same viewBox.
"""

from dataclasses import dataclass

import drawsvg as draw

from skim.data import Palette, SkimConfig, SvalboardKeymap
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
from .layout import KeymapLayoutMetrics
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
from .overview import HeaderDims, compute_header_dims
from .overview_layout import _outer_padding
from .render_context import RenderContext, using_render_context
from .styling import derive_accent_line
from .text import Font

# Every standalone image renders its body geometry at this multiple of the
# configured document width. Chips, fonts, paddings, gaps, the title text
# and the Svalboard logo all grow together at this scale.
_SCALE = 1.5


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ImageSetup:
    """Pre-computed per-image rendering parameters.

    ``initial_canvas_w`` is the canvas width used for layout (= the requested
    output width at the 1.5× geometry scale); ``padding`` and friends share
    the same scaled coordinate system. The SVG that ships back to the caller
    sets its ``width`` attribute to ``display_w`` and exposes the natural
    (possibly shrunken) canvas via ``viewBox`` so everything scales together
    when the SVG is rendered.
    """

    config: SkimConfig
    keymap: SvalboardKeymap[SvalboardTargetKey]
    palette: Palette
    geom: _LegendGeometry
    header_dims: HeaderDims
    initial_canvas_w: float
    display_w: float
    padding: float
    margin: float
    bottom_inset: float
    use_system_fonts: bool
    title_text: str


def _resolve_title(config: SkimConfig) -> str:
    """Pick the keymap title to render in the top-left of the image."""
    if config.output.keymap_title:
        return config.output.keymap_title
    if config.keyboard.layers:
        first = config.keyboard.layers[0]
        return f"{first.variant or first.name} Layers Layout"
    return "Keymap Layout"


def _build_setup(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> _ImageSetup:
    """Build the per-image setup at 1.5× geometry scale.

    The initial canvas width is the requested ``--width`` (because the body
    lays out as if the user-requested canvas is what we have to fill); the
    SVG ``width`` attribute will be the same ``--width`` so the displayed
    output respects the user's size after the natural canvas shrinks.
    """
    real_doc_width = config.output.layout.width
    scaled_doc_width = real_doc_width * _SCALE

    # Build a config copy with the scaled layout width so all metrics-derived
    # sizes (logo, title font, padding, copyright font) come out at 1.5×.
    scaled_layout = config.output.layout.model_copy(update={"width": scaled_doc_width})
    scaled_output = config.output.model_copy(update={"layout": scaled_layout})
    scaled_config = config.model_copy(update={"output": scaled_output})

    metrics = KeymapLayoutMetrics.from_config(scaled_config)
    padding = _outer_padding(metrics)
    geom = _LegendGeometry.for_doc_width(scaled_doc_width)
    header_dims = compute_header_dims(scaled_config, keymap)

    return _ImageSetup(
        config=scaled_config,
        keymap=keymap,
        palette=scaled_config.output.style.palette,
        geom=geom,
        header_dims=header_dims,
        initial_canvas_w=scaled_doc_width,
        display_w=real_doc_width,
        padding=padding,
        margin=metrics.margin,
        bottom_inset=metrics.inset + metrics.margin,
        use_system_fonts=scaled_config.output.style.use_system_fonts,
        title_text=_resolve_title(config),
    )


def _section_title_max_height(setup: _ImageSetup, label: str) -> float:
    """Rendered height of a section title label (e.g. ``"MACROS"``).

    Used as the ``max_height`` cap for the footer in the standalone solo
    images so the copyright never reads taller than the section title
    above the body. Measured with ``getbbox()`` for the same font and
    size :class:`SectionStripe` actually paints with.
    """
    pil_font = Font.FINGER_KEY.load(int(round(max(setup.geom.title_font_size, 1.0))))
    left, top, right, bottom = pil_font.getbbox(label)
    del left, right
    return float(bottom - top)


def _footer_max_height(setup: _ImageSetup, *, section_title: str | None) -> float | None:
    """Pick the ``max_height`` cap for the footer based on the host image.

    The standalone solo images (macros / tap-dances) cap the footer at
    the rendered height of their section title so the copyright doesn't
    dwarf the legend it sits below. The combined ``special-keys`` image
    (and any image without a single dominant section title) leaves the
    footer at its natural size by passing ``None``.
    """
    if section_title is None:
        return None
    return _section_title_max_height(setup, section_title)


# ---------------------------------------------------------------------------
# Composable image scaffolding
# ---------------------------------------------------------------------------


@Composable
def _CanvasFrame(
    *,
    content: Component,
    setup: _ImageSetup,
):
    """Outer chrome: rounded background border around ``content``.

    The natural size matches ``content`` exactly — the border is
    painted INSIDE that extent, inset by ``setup.margin``, mirroring
    the historical positional layout (where the border surrounded the
    canvas minus margin and the content sat at offset ``padding`` from
    the canvas edge). The content's :meth:`draw_at` runs at the same
    origin so its top-left aligns with the canvas top-left.
    """
    size = content.size
    border = setup.config.output.style.border
    palette = setup.palette
    margin = setup.margin

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
    setup: _ImageSetup,
    title: str,
    color: str,
    count: int,
    width: float,
    body: Component,
) -> BaseComponent:
    """One section as a Column: ``SectionStripe`` + spacer + body.

    The same shape both standalone images and the combined image use —
    the combined image places two of these side-by-side in a Row.
    """
    geom = setup.geom
    return Column(
        [
            SectionStripe(title=title, count=count, width=width, accent_line=color),
            Spacer(height=2 * geom.title_baseline_offset),
            body,
        ],
        align="start",
    )


def _render_image(
    setup: _ImageSetup,
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
    geom = setup.geom

    header = Header(
        title=setup.title_text,
        gap=2 * setup.padding,
        max_width=content_w,
    )

    children: list[Component] = [
        header,
        Spacer(height=geom.title_rule_offset * 0.5),
        body,
    ]

    footer_text = setup.config.output.copyright or ""
    if footer_text:
        footer = Footer(
            text=footer_text,
            max_height=_footer_max_height(setup, section_title=footer_section_title),
        )
        children.extend(
            [
                Spacer(height=setup.bottom_inset),
                Align(footer, width=content_w, horizontal="end"),
            ]
        )

    column = Column(children, align="start")
    padded = Padding(
        column,
        top=setup.padding,
        right=setup.padding,
        left=setup.padding,
        bottom=setup.bottom_inset,
    )
    image = _CanvasFrame(content=padded, setup=setup)
    return _make_drawing(setup, image)


def _make_drawing(setup: _ImageSetup, content: Component) -> draw.Drawing:
    """Create the SVG ``Drawing`` for ``content`` and paint it.

    Sets the displayed width to ``setup.display_w`` and exposes the
    natural canvas via ``viewBox`` so the requested ``--width`` is
    honoured while content scales proportionally.
    """
    canvas_w = content.size.width
    canvas_h = content.size.height
    display_w = setup.display_w
    display_h = canvas_h * (display_w / canvas_w) if canvas_w else canvas_h

    d = draw.Drawing(display_w, display_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

    if not setup.use_system_fonts:
        for font in Font:
            d.append_css(font.css_style)

    content.draw_at(d, Point(0, 0))
    return d


def _render_section_image(
    setup: _ImageSetup,
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
        setup=setup,
        title=section_title,
        color=section_color,
        count=section_count,
        width=content_w,
        body=body,
    )
    return _render_image(
        setup,
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


@Composable
def _MacrosBody(
    *,
    macros: list,
    accent_fill: str,
    accent_line: str,
    text_color: str,
    geom: _LegendGeometry,
    use_system_fonts: bool,
    content_width: float,
    doc_width: float,
):
    """Stacked macro rows with the legend's natural row-gap spacing.

    Wraps the existing :func:`build_macro_row` helper so the rendered
    pills and chips match what the overview's macro section paints.
    Per-row height respects ``content_width`` (pills wrap to additional
    lines when they don't fit).
    """
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
    setup = _build_setup(config, keymap)
    with using_render_context(RenderContext.build(config, keymap, scale=_SCALE)):
        macros = all_macros(keymap.macros)
        palette = setup.palette
        geom = setup.geom
        macro_line = derive_accent_line(palette.macro_color)

        initial_content_w = setup.initial_canvas_w - 2 * setup.padding

        # Lay out using the *initial* content width so wrap detection matches
        # what the user-requested canvas would normally produce. If the longest
        # natural row fits within ``initial_content_w`` no row wraps and we can
        # shrink the canvas; otherwise we keep the canvas at ``--width`` and let
        # the existing pill-wrap logic handle the overflow.
        natural_widths = _macro_natural_widths(macros, geom)
        longest_natural = max(natural_widths) if natural_widths else 0.0
        no_wrapping = longest_natural <= initial_content_w
        content_w = longest_natural if (no_wrapping and longest_natural > 0) else initial_content_w

        body: Component = (
            _MacrosBody(
                macros=macros,
                accent_fill=palette.macro_color,
                accent_line=macro_line,
                text_color=palette.text_color,
                geom=geom,
                use_system_fonts=setup.use_system_fonts,
                content_width=content_w,
                doc_width=setup.initial_canvas_w,
            )
            if macros
            else Spacer()
        )

        return _render_section_image(
            setup,
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
    setup = _build_setup(config, keymap)
    with using_render_context(RenderContext.build(config, keymap, scale=_SCALE)):
        tap_dances = all_tap_dances(keymap.tap_dances)
        palette = setup.palette
        geom = setup.geom
        td_line = derive_accent_line(palette.tap_dance_color)

        initial_content_w = setup.initial_canvas_w - 2 * setup.padding

        # Build the table component first so we can shrink the canvas to
        # match it. ``max_width`` caps the table at the canvas budget;
        # when names would overflow the cap they're auto-truncated.
        table = TapDanceTable(
            tap_dances=tap_dances,
            accent_fill=palette.tap_dance_color,
            accent_line=td_line,
            text_color=palette.text_color,
            geom=geom,
            use_system_fonts=setup.use_system_fonts,
            max_width=initial_content_w,
        )
        content_w = min(initial_content_w, table.size.width) if tap_dances else initial_content_w
        body: Component = table if tap_dances else Spacer()

        return _render_section_image(
            setup,
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
    setup = _build_setup(config, keymap)
    with using_render_context(RenderContext.build(config, keymap, scale=_SCALE)):
        macros = all_macros(keymap.macros)
        tap_dances = all_tap_dances(keymap.tap_dances)
        palette = setup.palette
        geom = setup.geom
        macro_line = derive_accent_line(palette.macro_color)
        td_line = derive_accent_line(palette.tap_dance_color)

        target_content_w = setup.initial_canvas_w - 2 * setup.padding
        col_gap = geom.column_gap
        col_w = (target_content_w - col_gap) / 2 if macros and tap_dances else target_content_w

        sections: list[Component] = []
        if macros:
            sections.append(
                _section_block(
                    setup=setup,
                    title="MACROS",
                    color=macro_line,
                    count=len(macros),
                    width=col_w,
                    body=_MacrosBody(
                        macros=macros,
                        accent_fill=palette.macro_color,
                        accent_line=macro_line,
                        text_color=palette.text_color,
                        geom=geom,
                        use_system_fonts=setup.use_system_fonts,
                        content_width=col_w,
                        doc_width=setup.initial_canvas_w,
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
                geom=geom,
                use_system_fonts=setup.use_system_fonts,
                name_column_width=_td_name_column_width(geom, tap_dances),
            )
            sections.append(
                _section_block(
                    setup=setup,
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
            setup,
            body=body,
            content_w=target_content_w,
            # Combined image has no single dominant section title, so the
            # footer keeps its natural size (matches the per-layer/overview).
            footer_section_title=None,
        )
