# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reusable header component for keymap images.

The header places the keymap title on the left and the Svalboard logo
on the right. The logo's height matches the title's rendered glyph
bounding box, so the two elements paint at the same visible vertical
extent. When the natural title-plus-gap-plus-logo extent overflows the
available width, both elements shrink together by the same factor so
the header fits.

This module exposes the rendering pipeline both as composables —
:func:`TitleText`, :func:`Logo`, :func:`Header` — and as legacy
imperative helpers (:func:`append_header` and
:func:`header_layout_height`) for call sites that haven't yet been
ported to the composable API.
"""

from dataclasses import dataclass

import drawsvg as draw

from skim.assets import ASSETS

from .composable import (
    Composable,
    Point,
    Row,
    Size,
    Spacer,
)
from .geometry import AspectRatio
from .render_context import TextStyle
from .text import Font

# The Svalboard logo SVG asset's intrinsic aspect ratio. Logo width is
# derived from height via this ratio so the logo stays in proportion
# regardless of which size the title drives it to.
_LOGO_ASPECT_RATIO = AspectRatio.from_dimensions(width=2333.333, height=458.333, precision=2)

# Floor on the title font size when shrinking so a tight canvas still
# renders something legible (and never produces a degenerate ``0``).
_MIN_TITLE_FONT_SIZE = 6.0

# Default minimum gap between the title's right edge and the logo's
# left edge, expressed as a multiple of the surrounding image padding.
# Used by :func:`append_header` only — composable callers pass ``gap``
# explicitly and choose their own multiplier.
_MIN_GAP_PADDING_MULTIPLIER = 2.0


# ---------------------------------------------------------------------------
# Backward-compatible result type — kept so existing callers and tests
# that import ``HeaderRenderResult`` continue to work.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HeaderRenderResult:
    """Outcome of an :func:`append_header` render."""

    height: float
    """Vertical extent of the header (= the matched logo / title height)."""

    title_font_size: float
    """Final title font size after any fit-to-canvas shrinking."""

    logo_width: float
    """Logo width actually used."""

    logo_height: float
    """Logo height actually used (matches the title's rendered bbox)."""


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------


def _title_rendered_size(text: str, font_size: float) -> Size:
    """Return the actual rendered size of ``text`` at ``font_size``.

    Uses PIL's ``getbbox()`` which reports the tight bounding box of
    the rendered glyphs — this matches what an SVG renderer paints for
    the same text and font, so the logo can be sized to read at the
    same visual height as the title regardless of which font glyphs
    the text actually exercises.
    """
    if not text:
        return Size(0.0, 0.0)
    pil_font = Font.TITLE.load(int(round(max(font_size, 1.0))))
    left, top, right, bottom = pil_font.getbbox(text)
    return Size(width=float(right - left), height=float(bottom - top))


def _resolve_title_font_size(
    title: str,
    font_max_size: float,
    gap: float,
    max_width: float | None,
) -> float:
    """Pick the title font size that fits inside ``max_width``.

    Returns ``font_max_size`` when the natural ``title + gap + logo``
    extent already fits (or when ``max_width`` is ``None``); otherwise
    returns the largest size that — applied to both title and logo
    proportionally — keeps the gap and the bounds intact.
    """
    if not title or max_width is None:
        return font_max_size
    natural = _title_rendered_size(title, font_max_size)
    natural_logo_w = _LOGO_ASPECT_RATIO.width_from_height(natural.height)
    if natural.width + natural_logo_w + gap <= max_width:
        return font_max_size
    denom = natural.width + natural_logo_w
    if denom <= 0:
        return font_max_size
    scale = (max_width - gap) / denom
    return max(_MIN_TITLE_FONT_SIZE, font_max_size * scale)


# ---------------------------------------------------------------------------
# Composables
# ---------------------------------------------------------------------------


@Composable
def TitleText(
    text: str,
    font_size: float,
    color: str = "black",
    use_system_fonts: bool = False,
):
    """The keymap title rendered at ``font_size``.

    The element's size matches the rendered glyph bbox so the logo can
    be sized to match it.
    """
    size = _title_rendered_size(text, font_size)
    family = Font.TITLE.get_system_font_family() if use_system_fonts else Font.TITLE.value

    def draw_at(d, origin):
        if not text:
            return
        d.append(
            draw.Text(
                text,
                font_size=font_size,
                x=origin.x,
                y=origin.y + size.height / 2.0,
                text_anchor="start",
                dominant_baseline="central",
                font_family=family,
                fill=color,
            )
        )

    return size, draw_at


@Composable
def Logo(height: float):
    """The Svalboard logo at ``height`` (width follows the asset's aspect)."""
    width = _LOGO_ASPECT_RATIO.width_from_height(height)
    size = Size(width, height)

    def draw_at(d, origin):
        d.append(
            draw.Image(
                x=origin.x,
                y=origin.y,
                width=width,
                height=height,
                path=ASSETS.logo_svalboard,
                embed=True,
            )
        )

    return size, draw_at


def _build_header(
    *,
    title: str,
    title_font_max_size: float,
    gap: float,
    max_width: float | None,
    color: str,
    use_system_fonts: bool,
):
    """Pure helper used by both the ctx-aware composable and ``append_header``.

    Resolves the title font size against ``max_width``, builds the
    title + spacer + logo Row, and returns the resulting Component.
    Shared so the ctx-aware :func:`Header` and the legacy imperative
    :func:`append_header` produce pixel-identical output.
    """
    font_size = _resolve_title_font_size(title, title_font_max_size, gap, max_width)
    title_el = TitleText(title, font_size=font_size, color=color, use_system_fonts=use_system_fonts)
    logo_el = Logo(height=title_el.size.height)

    if max_width is None:
        return Row([title_el, logo_el], gap=gap, align="center")

    children_w = title_el.size.width + logo_el.size.width
    spacer_w = max(gap, max_width - children_w)
    return Row([title_el, Spacer(width=spacer_w), logo_el], gap=0.0, align="center")


@Composable(use_context=True)
def Header(
    ctx,
    *,
    title: str,
    gap: float,
    max_width: float | None = None,
):
    """A keymap title + Svalboard logo header.

    Reads typography (font, size, color) from ``ctx.theme.title`` and
    the ``use_system_fonts`` flag from
    ``ctx.config.output.style``.

    The logo's natural height matches the title's rendered glyph
    bbox. When ``max_width`` is given:

      * if the natural ``title + gap + logo`` extent already fits, the
        header keeps its natural size and a flexible spacer between
        title and logo grows so the header occupies ``max_width``;
      * otherwise both title and logo shrink by the same factor so the
        header width equals ``max_width`` while preserving ``gap``.

    When ``max_width`` is ``None`` the header is its natural extent —
    title, fixed ``gap``, logo, no flex spacer.
    """
    typo: TextStyle = ctx.theme.typography.title
    inner = _build_header(
        title=title,
        title_font_max_size=typo.size,
        gap=gap,
        max_width=max_width,
        color=typo.color,
        use_system_fonts=ctx.config.output.style.use_system_fonts,
    )
    return inner.size, inner.draw_at


# ---------------------------------------------------------------------------
# Backward-compatible imperative helpers
# ---------------------------------------------------------------------------


def header_layout_height(title_text: str, title_font_max_size: float) -> float:
    """Upper-bound header height for body layout.

    Hosts call this before rendering to reserve space below the header.
    Since the logo's height matches the title's rendered height and
    both only ever shrink (never grow) past their natural sizes, the
    natural rendered title height at ``title_font_max_size`` is the
    safe upper bound.
    """
    return _title_rendered_size(title_text, title_font_max_size).height


def append_header(
    d: draw.Drawing,
    *,
    canvas_w: float,
    padding: float,
    title_text: str,
    title_color: str,
    title_font_max_size: float,
    use_system_fonts: bool,
    top_y: float | None = None,
) -> HeaderRenderResult:
    """Imperative wrapper that builds and paints a header without a context.

    Used by call sites (per-layer / overview images) that haven't yet
    been migrated to a :class:`RenderContext`-aware pipeline. Goes
    through the same :func:`_build_header` helper as the ctx-aware
    :func:`Header` composable so output stays pixel-identical.
    """
    if top_y is None:
        top_y = padding
    gap = _MIN_GAP_PADDING_MULTIPLIER * padding
    max_width = canvas_w - 2 * padding

    header = _build_header(
        title=title_text,
        title_font_max_size=title_font_max_size,
        gap=gap,
        max_width=max_width,
        color=title_color,
        use_system_fonts=use_system_fonts,
    )
    header.draw_at(d, Point(padding, top_y))

    # Recover the per-element values for the legacy result type.
    final_font_size = _resolve_title_font_size(title_text, title_font_max_size, gap, max_width)
    final_title_size = _title_rendered_size(title_text, final_font_size)
    final_logo_h = final_title_size.height
    final_logo_w = _LOGO_ASPECT_RATIO.width_from_height(final_logo_h)
    return HeaderRenderResult(
        height=header.size.height,
        title_font_size=final_font_size,
        logo_width=final_logo_w,
        logo_height=final_logo_h,
    )


__all__ = [
    "Header",
    "HeaderRenderResult",
    "Logo",
    "TitleText",
    "append_header",
    "header_layout_height",
]
