# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reusable header component for keymap images.

The header places the keymap title on the left and the Svalboard logo on
the right. The logo's height is matched to the title's total visual
height (ascent + descent at the chosen font size), so the two elements
read as a balanced pair regardless of canvas width.

When the natural title-plus-logo extent (with a ``2 × padding`` gap
between them) overflows the available canvas, both elements shrink
together by the same factor so the canvas accommodates them while
preserving the minimum gap. This keeps the title and the logo
proportional to each other on every canvas size.
"""

from dataclasses import dataclass

import drawsvg as draw

from skim.assets import ASSETS

from .geometry import AspectRatio
from .text import Font

# The Svalboard logo SVG asset's intrinsic aspect ratio. Logo width is
# derived from height via this ratio so the logo stays in proportion.
_LOGO_ASPECT_RATIO = AspectRatio.from_dimensions(width=2333.333, height=458.333, precision=2)

# Minimum horizontal gap between the title's right edge and the logo's
# left edge, expressed as a multiple of the image padding.
_MIN_GAP_PADDING_MULTIPLIER = 2.0

# Floor on the title font size when shrinking so a tight canvas still
# renders something legible (and never produces a degenerate ``0``).
_MIN_TITLE_FONT_SIZE = 6.0


@dataclass(frozen=True, slots=True)
class HeaderRenderResult:
    """Outcome of a header render — useful for laying out content below it."""

    height: float
    """Vertical extent of the header (= the matched logo / title height)."""

    title_font_size: float
    """Final title font size after any fit-to-canvas shrinking."""

    logo_width: float
    """Logo width actually used."""

    logo_height: float
    """Logo height actually used (matches the title's full visual height)."""


def _title_rendered_size(text: str, font_size: float) -> tuple[float, float]:
    """Return the actual rendered ``(width, height)`` of ``text`` at ``font_size``.

    Uses PIL's ``getbbox()`` which reports the tight bounding box of the
    rendered glyphs — this matches what an SVG renderer paints for the
    same text and font, so the logo can be sized to read as the same
    visual height as the title regardless of which font glyphs the text
    actually exercises (e.g., descenders push the box down).
    """
    if not text:
        return 0.0, 0.0
    pil_font = Font.TITLE.load(int(round(max(font_size, 1.0))))
    left, top, right, bottom = pil_font.getbbox(text)
    return float(right - left), float(bottom - top)


def header_layout_height(title_text: str, title_font_max_size: float) -> float:
    """Upper-bound header height for body layout.

    Hosts call this before rendering to reserve space below the header.
    Since the logo's height matches the title's rendered height and both
    only ever shrink (never grow) past their natural sizes, the natural
    rendered title height at ``title_font_max_size`` is the safe upper
    bound.
    """
    _, height = _title_rendered_size(title_text, title_font_max_size)
    return height


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
    """Append the title + logo header to ``d`` and return its computed extents.

    Args:
        d: The drawing to append to.
        canvas_w: Total canvas width the header must fit inside.
        padding: Outer padding used by the host image (the same value the
            host uses on its left/right edges).
        title_text: Keymap title to render on the left.
        title_color: Fill color for the title text.
        title_font_max_size: Upper bound for the title font size; the
            actual size shrinks toward this max but never exceeds it. The
            logo's natural height matches the title's full visual height
            at this size.
        use_system_fonts: When ``True`` the title uses the system font
            family instead of the embedded ``TITLE`` font.
        top_y: Vertical anchor for the top of the header. Defaults to
            ``padding`` (the canonical inset from the canvas edge).

    Returns:
        A :class:`HeaderRenderResult` describing the final header
        dimensions; the host renderer uses ``height`` to position the
        body content below the header.
    """
    if top_y is None:
        top_y = padding

    # Natural sizes — title at the requested max font, logo height matched
    # to the title's actual rendered height so the two elements paint at
    # the same visible vertical extent in the final SVG.
    natural_font_size = title_font_max_size
    natural_title_w, natural_title_h = _title_rendered_size(title_text, natural_font_size)
    natural_logo_h = natural_title_h
    natural_logo_w = _LOGO_ASPECT_RATIO.width_from_height(natural_logo_h)

    # Available horizontal space between the canvas's left and right
    # padding insets.
    available = canvas_w - 2 * padding
    min_gap = _MIN_GAP_PADDING_MULTIPLIER * padding

    needed_with_min_gap = natural_title_w + natural_logo_w + min_gap
    if not title_text or needed_with_min_gap <= available:
        font_size = natural_font_size
        logo_w = natural_logo_w
        logo_h = natural_logo_h
    else:
        # Shrink the title and the logo by the same factor so their visual
        # proportions stay locked together. Solve for the largest factor
        # that keeps the minimum 2× padding gap intact:
        #   (title_w + logo_w) × scale + min_gap = available
        denom = natural_title_w + natural_logo_w
        scale = (available - min_gap) / denom if denom > 0 else 1.0
        # Floor the title font size so it remains legible on tight
        # canvases — accept a smaller gap rather than an unreadable title.
        scale = max(scale, _MIN_TITLE_FONT_SIZE / natural_font_size)
        font_size = natural_font_size * scale
        logo_w = natural_logo_w * scale
        logo_h = natural_logo_h * scale

    # Logo on the right.
    logo_x = canvas_w - padding - logo_w
    d.append(
        draw.Image(
            x=logo_x,
            y=top_y,
            width=logo_w,
            height=logo_h,
            path=ASSETS.logo_svalboard,
            embed=True,
        )
    )

    # Title on the left, vertically centered against the logo. Title and
    # logo share a vertical centre so they line up regardless of which
    # element is taller after shrinking.
    title_font_family = (
        Font.TITLE.get_system_font_family() if use_system_fonts else Font.TITLE.value
    )
    if title_text:
        d.append(
            draw.Text(
                title_text,
                font_size=font_size,
                x=padding,
                y=top_y + logo_h / 2.0,
                text_anchor="start",
                dominant_baseline="central",
                font_family=title_font_family,
                fill=title_color,
            )
        )

    return HeaderRenderResult(
        height=logo_h,
        title_font_size=font_size,
        logo_width=logo_w,
        logo_height=logo_h,
    )
