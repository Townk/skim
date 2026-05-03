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

Three composables: :func:`TitleText`, :func:`Logo`, :func:`Header`
(the assembled title + spacer + logo Row).
"""

import drawsvg as draw

from skim.assets import ASSETS

from .composable import Composable
from .primitives import Row, Size, Spacer
from .render_context import TextStyle
from .text import Font

# The Svalboard logo SVG asset's intrinsic aspect ratio
# (width / height), rounded to 2 dp so derived widths stay stable
# under float rounding. Logo width is derived from height via this
# ratio so the logo stays in proportion regardless of which size the
# title drives it to.
_LOGO_WIDTH_PER_UNIT_HEIGHT = round(2333.333 / 458.333, 2)


def _logo_width_for_height(height: float) -> float:
    """Return the Svalboard logo's width at the given rendered height."""
    return height * _LOGO_WIDTH_PER_UNIT_HEIGHT


# Floor on the title font size when shrinking so a tight canvas still
# renders something legible (and never produces a degenerate ``0``).
_MIN_TITLE_FONT_SIZE = 6.0


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
    pil_font = Font.TITLE.load(font_size)
    left, top, right, bottom = pil_font.getbbox(text)
    return Size(width=float(right - left), height=float(bottom - top))


def _resolve_title_font_size(
    title: str,
    font_max_size: float,
    min_gap: float,
    max_width: float | None,
) -> float:
    """Pick the title font size that fits inside ``max_width``.

    Returns ``font_max_size`` when the natural ``title + min_gap +
    logo`` extent already fits (or when ``max_width`` is ``None``);
    otherwise returns the largest size that — applied to both title
    and logo proportionally — keeps the gap floor and the bounds
    intact.
    """
    if not title or max_width is None:
        return font_max_size
    natural = _title_rendered_size(title, font_max_size)
    natural_logo_w = _logo_width_for_height(natural.height)
    if natural.width + natural_logo_w + min_gap <= max_width:
        return font_max_size
    denom = natural.width + natural_logo_w
    if denom <= 0:
        return font_max_size
    scale = (max_width - min_gap) / denom
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
    width = _logo_width_for_height(height)
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


@Composable(use_context=True)
def Header(
    ctx,
    *,
    title: str,
    min_gap: float,
    max_width: float | None = None,
):
    """A keymap title + Svalboard logo header.

    Reads typography (font, size, color) from ``ctx.theme.title`` and
    the ``use_system_fonts`` flag from
    ``ctx.config.output.style``.

    The logo's natural height matches the title's rendered glyph
    bbox. ``min_gap`` is a floor on the space between title and logo
    — the actual gap can grow when there's extra room, but never
    drops below ``min_gap``. When ``max_width`` is given:

      * if the natural ``title + min_gap + logo`` extent already
        fits, the header keeps its natural size and a flexible
        spacer between title and logo grows so the header occupies
        ``max_width``;
      * otherwise both title and logo shrink by the same factor so
        the header width equals ``max_width`` while preserving
        ``min_gap``.

    When ``max_width`` is ``None`` the header is its natural extent —
    title, ``min_gap`` between, logo (no flex spacer to grow into).
    """
    typo: TextStyle = ctx.theme.typography.title
    use_system_fonts = ctx.config.output.style.use_system_fonts

    font_size = _resolve_title_font_size(title, typo.size, min_gap, max_width)
    title_el = TitleText(
        title, font_size=font_size, color=typo.color, use_system_fonts=use_system_fonts
    )
    logo_el = Logo(height=title_el.size.height)

    if max_width is None:
        return Row([title_el, logo_el], gap=min_gap, align="center")

    children_w = title_el.size.width + logo_el.size.width
    spacer_w = max(min_gap, max_width - children_w)
    return Row([title_el, Spacer(width=spacer_w), logo_el], gap=0.0, align="center")


__all__ = ["Header", "Logo", "TitleText"]
