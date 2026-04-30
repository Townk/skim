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

from .footer import append_footer, footer_layout_height
from .header import HeaderRenderResult, append_header, header_layout_height
from .legend import (
    _LegendGeometry,
    _draw_section_title,
    _flatten_macro_pills,
    _layout_pill_lines,
    _td_name_column_width,
    all_macros,
    all_tap_dances,
    build_macro_row,
    build_tap_dance_column_header,
    build_tap_dance_row,
    macro_row_height,
)
from .layout import KeymapLayoutMetrics
from .overview import HeaderDims, compute_header_dims
from .overview_layout import _outer_padding
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


def _stripe_height(geom: _LegendGeometry) -> float:
    """Vertical extent reserved for one section title stripe (text + rule)."""
    return geom.title_rule_offset + geom.title_baseline_offset


def _header_layout_height(setup: _ImageSetup) -> float:
    """Upper-bound height of the header strip used for body layout.

    The header component matches the logo's height to the title's rendered
    bounding box at ``title_font_size``; both shrink together when the
    canvas can't accommodate them with a ``2 × padding`` gap. The natural
    rendered height at the maximum font size is therefore a safe upper
    bound for body positioning.
    """
    return header_layout_height(setup.title_text, setup.header_dims.title_font_size)


# ---------------------------------------------------------------------------
# SVG construction helpers
# ---------------------------------------------------------------------------


def _build_drawing(
    setup: _ImageSetup,
    canvas_w: float,
    canvas_h: float,
) -> draw.Drawing:
    """Create the base ``Drawing`` with viewBox so ``--width`` is honoured.

    The internal coordinate system uses the natural (possibly shrunken)
    canvas; the SVG itself displays at the user-requested ``--width``.
    """
    display_w = setup.display_w
    display_h = canvas_h * (display_w / canvas_w) if canvas_w else canvas_h
    d = draw.Drawing(display_w, display_h, viewBox=f"0 0 {canvas_w} {canvas_h}")

    if not setup.use_system_fonts:
        for font in Font:
            d.append_css(font.css_style)

    border = setup.config.output.style.border
    palette = setup.palette
    d.append(
        draw.Rectangle(
            x=setup.margin,
            y=setup.margin,
            width=canvas_w - setup.margin * 2.0,
            height=canvas_h - setup.margin * 2.0,
            rx=border.radius if border else None,
            ry=border.radius if border else None,
            fill=palette.background_color,
            stroke=palette.border_color if border else None,
            stroke_width=border.width if border else None,
        )
    )
    return d


def _append_header(d: draw.Drawing, setup: _ImageSetup, canvas_w: float) -> HeaderRenderResult:
    """Stamp the keymap title (left) and Svalboard logo (right) header.

    Delegates to the shared :mod:`header` component so the logo's height
    matches the title's full visual height; the two shrink together when
    the canvas can't accommodate them with the minimum ``2 × padding``
    gap between title and logo.
    """
    return append_header(
        d,
        canvas_w=canvas_w,
        padding=setup.padding,
        title_text=setup.title_text,
        title_color=setup.palette.text_color,
        title_font_max_size=setup.header_dims.title_font_size,
        use_system_fonts=setup.use_system_fonts,
    )


def _section_title_max_height(setup: _ImageSetup, label: str) -> float:
    """Rendered height of a section title label (e.g. ``"MACROS"``).

    Used as the ``max_height`` cap for the footer in the standalone solo
    images so the copyright never reads taller than the section title
    above the body. Measured with ``getbbox()`` for the same font and
    size :func:`_draw_section_title` actually paints with.
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


def _append_copyright(
    d: draw.Drawing,
    setup: _ImageSetup,
    canvas_w: float,
    canvas_h: float,
    *,
    section_title: str | None,
) -> None:
    """Stamp the copyright string at the bottom-right corner (no-op when unset).

    ``section_title`` enables the per-image footer height cap — see
    :func:`_footer_max_height`.
    """
    if not setup.config.output.copyright:
        return
    append_footer(
        d,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        padding=setup.padding,
        bottom_inset=setup.bottom_inset,
        text=setup.config.output.copyright,
        text_color=setup.palette.text_color,
        font_max_size=setup.header_dims.copyright_font_size,
        use_system_fonts=setup.use_system_fonts,
        max_height=_footer_max_height(setup, section_title=section_title),
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


def draw_macros_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the standalone macros image."""
    setup = _build_setup(config, keymap)
    macros = all_macros(keymap.macros)
    palette = setup.palette
    geom = setup.geom
    macro_line = derive_accent_line(palette.macro_color)

    initial_canvas_w = setup.initial_canvas_w
    initial_content_w = initial_canvas_w - 2 * setup.padding

    natural_widths = _macro_natural_widths(macros, geom)
    longest_natural = max(natural_widths) if natural_widths else 0.0

    # Lay out using the *initial* content width so wrap detection matches
    # what the user-requested canvas would normally produce. If the longest
    # natural row fits within ``initial_content_w`` no row wraps and we can
    # shrink the canvas; otherwise we keep the canvas at ``--width`` and let
    # the existing pill-wrap logic handle the overflow.
    no_wrapping = longest_natural <= initial_content_w
    if no_wrapping and longest_natural > 0:
        content_w = longest_natural
        canvas_w = content_w + 2 * setup.padding
    else:
        canvas_w = initial_canvas_w
        content_w = initial_content_w

    stripe_y = setup.padding + _header_layout_height(setup) + geom.title_rule_offset * 0.5
    body_y = stripe_y + _stripe_height(geom) + geom.title_baseline_offset

    if macros:
        rows_h = sum(
            macro_row_height(m, content_w, doc_width=setup.initial_canvas_w) for m in macros
        )
        rows_h += max(0, len(macros) - 1) * geom.row_gap
    else:
        rows_h = 0.0

    macros_section_title = "MACROS"
    footer_h = footer_layout_height(
        setup.config.output.copyright or "",
        setup.header_dims.copyright_font_size,
        max_height=_footer_max_height(setup, section_title=macros_section_title),
    )
    canvas_h = body_y + rows_h + setup.bottom_inset
    if footer_h > 0:
        canvas_h += footer_h + setup.bottom_inset

    d = _build_drawing(setup, canvas_w, canvas_h)
    _append_header(d, setup, canvas_w)

    _draw_section_title(
        d,
        macros_section_title,
        setup.padding,
        stripe_y,
        content_w,
        macro_line,
        count=len(macros),
        geom=geom,
    )

    cursor = body_y
    for i, macro in enumerate(macros):
        if i > 0:
            cursor += geom.row_gap
        d.append(
            build_macro_row(
                macro,
                x=setup.padding,
                y=cursor,
                content_width=content_w,
                accent_fill=palette.macro_color,
                accent_line=macro_line,
                text_color=palette.text_color,
                use_system_fonts=setup.use_system_fonts,
                doc_width=setup.initial_canvas_w,
            )
        )
        cursor += macro_row_height(macro, content_w, doc_width=setup.initial_canvas_w)

    _append_copyright(d, setup, canvas_w, canvas_h, section_title=macros_section_title)
    return d


# ---------------------------------------------------------------------------
# Tap-dances image
# ---------------------------------------------------------------------------


def draw_tap_dances_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the standalone tap-dances image.

    The table renders at its natural 1.5× width and the canvas shrinks
    horizontally to wrap it — variant cells are NOT stretched.
    """
    setup = _build_setup(config, keymap)
    tap_dances = all_tap_dances(keymap.tap_dances)
    palette = setup.palette
    geom = setup.geom
    td_line = derive_accent_line(palette.tap_dance_color)

    name_col_w = _td_name_column_width(geom, tap_dances)
    table_w = geom.tag_w + name_col_w + geom.row_content_indent_gap + 4 * geom.td_cell_w

    initial_content_w = setup.initial_canvas_w - 2 * setup.padding
    # Shrink the canvas to wrap the table when there's slack; never grow
    # past the user-requested width.
    content_w = min(initial_content_w, table_w)
    canvas_w = content_w + 2 * setup.padding

    stripe_y = setup.padding + _header_layout_height(setup) + geom.title_rule_offset * 0.5
    body_top = stripe_y + _stripe_height(geom) + geom.title_baseline_offset

    rows_h = len(tap_dances) * (geom.td_row_height + geom.td_row_gap) if tap_dances else 0.0
    body_h = (geom.td_header_height + rows_h) if tap_dances else 0.0

    td_section_title = "TAP-DANCE"
    footer_h = footer_layout_height(
        setup.config.output.copyright or "",
        setup.header_dims.copyright_font_size,
        max_height=_footer_max_height(setup, section_title=td_section_title),
    )
    canvas_h = body_top + body_h + setup.bottom_inset
    if footer_h > 0:
        canvas_h += footer_h + setup.bottom_inset

    d = _build_drawing(setup, canvas_w, canvas_h)
    _append_header(d, setup, canvas_w)

    _draw_section_title(
        d,
        td_section_title,
        setup.padding,
        stripe_y,
        content_w,
        td_line,
        count=len(tap_dances),
        geom=geom,
    )

    if tap_dances:
        d.append(
            build_tap_dance_column_header(
                x=setup.padding,
                y=body_top + geom.title_baseline_offset,
                text_color=palette.text_color,
                name_column_width=name_col_w,
                doc_width=setup.initial_canvas_w,
            )
        )
        cursor = body_top + geom.td_header_height
        for td in tap_dances:
            d.append(
                build_tap_dance_row(
                    td,
                    x=setup.padding,
                    y=cursor + geom.td_row_height / 2,
                    column_width=content_w,
                    accent_fill=palette.tap_dance_color,
                    accent_line=td_line,
                    text_color=palette.text_color,
                    use_system_fonts=setup.use_system_fonts,
                    name_column_width=name_col_w,
                    doc_width=setup.initial_canvas_w,
                )
            )
            cursor += geom.td_row_height + geom.td_row_gap

    _append_copyright(d, setup, canvas_w, canvas_h, section_title=td_section_title)
    return d


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
    macros = all_macros(keymap.macros)
    tap_dances = all_tap_dances(keymap.tap_dances)
    palette = setup.palette
    geom = setup.geom
    macro_line = derive_accent_line(palette.macro_color)
    td_line = derive_accent_line(palette.tap_dance_color)

    canvas_w = setup.initial_canvas_w
    target_content_w = canvas_w - 2 * setup.padding
    col_gap = geom.column_gap

    if macros and tap_dances:
        col_w = (target_content_w - col_gap) / 2
    else:
        col_w = target_content_w

    name_col_w = _td_name_column_width(geom, tap_dances)

    stripe_y = setup.padding + _header_layout_height(setup) + geom.title_rule_offset * 0.5
    body_top = stripe_y + _stripe_height(geom) + geom.title_baseline_offset

    if macros:
        macro_rows_h = sum(
            macro_row_height(m, col_w, doc_width=setup.initial_canvas_w) for m in macros
        )
        macro_rows_h += max(0, len(macros) - 1) * geom.row_gap
    else:
        macro_rows_h = 0.0

    td_rows_h = (
        geom.td_header_height + len(tap_dances) * (geom.td_row_height + geom.td_row_gap)
        if tap_dances
        else 0.0
    )

    body_h = max(macro_rows_h, td_rows_h)
    # Combined image — no per-section title constraint, so the footer
    # renders at its natural size (matches the per-layer / overview).
    footer_h = footer_layout_height(
        setup.config.output.copyright or "",
        setup.header_dims.copyright_font_size,
        max_height=None,
    )
    canvas_h = body_top + body_h + setup.bottom_inset
    if footer_h > 0:
        canvas_h += footer_h + setup.bottom_inset

    d = _build_drawing(setup, canvas_w, canvas_h)
    _append_header(d, setup, canvas_w)

    macro_x = setup.padding
    td_x = setup.padding + (col_w + col_gap if macros and tap_dances else 0)

    if macros:
        _draw_section_title(
            d,
            "MACROS",
            macro_x,
            stripe_y,
            col_w,
            macro_line,
            count=len(macros),
            geom=geom,
        )
        cursor = body_top
        for i, macro in enumerate(macros):
            if i > 0:
                cursor += geom.row_gap
            d.append(
                build_macro_row(
                    macro,
                    x=macro_x,
                    y=cursor,
                    content_width=col_w,
                    accent_fill=palette.macro_color,
                    accent_line=macro_line,
                    text_color=palette.text_color,
                    use_system_fonts=setup.use_system_fonts,
                    doc_width=setup.initial_canvas_w,
                )
            )
            cursor += macro_row_height(macro, col_w, doc_width=setup.initial_canvas_w)

    if tap_dances:
        _draw_section_title(
            d,
            "TAP-DANCE",
            td_x,
            stripe_y,
            col_w,
            td_line,
            count=len(tap_dances),
            geom=geom,
        )
        d.append(
            build_tap_dance_column_header(
                x=td_x,
                y=body_top + geom.title_baseline_offset,
                text_color=palette.text_color,
                name_column_width=name_col_w,
                doc_width=setup.initial_canvas_w,
            )
        )
        cursor = body_top + geom.td_header_height
        for td in tap_dances:
            d.append(
                build_tap_dance_row(
                    td,
                    x=td_x,
                    y=cursor + geom.td_row_height / 2,
                    column_width=col_w,
                    accent_fill=palette.tap_dance_color,
                    accent_line=td_line,
                    text_color=palette.text_color,
                    use_system_fonts=setup.use_system_fonts,
                    name_column_width=name_col_w,
                    doc_width=setup.initial_canvas_w,
                )
            )
            cursor += geom.td_row_height + geom.td_row_gap

    _append_copyright(d, setup, canvas_w, canvas_h, section_title=None)
    return d
