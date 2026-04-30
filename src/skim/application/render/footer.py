# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reusable footer component for keymap images.

The footer renders a right-aligned text line (typically the copyright
notice). Hosts can pass an optional ``max_height`` that caps the
rendered text height — used by the standalone special-keys images so
the copyright never reads taller than the ``MACROS`` / ``TAP-DANCE``
section title above the body.

This module exposes the rendering pipeline both as a composable
(:func:`Footer`) and as legacy imperative helpers
(:func:`append_footer` and :func:`footer_layout_height`) for call
sites that haven't yet been ported to the composable API.
"""

from dataclasses import dataclass

import drawsvg as draw

from .composable import Composable, Point, Size
from .text import Font

# Floor on the footer font size when shrinking under ``max_height`` so
# tight ceilings still produce something legible (and never produce a
# degenerate ``0``).
_MIN_FONT_SIZE = 6.0

# Opacity used when stamping the copyright string — matches the
# previous inline rendering in the per-layer / overview images.
_FOOTER_OPACITY = 0.6


# ---------------------------------------------------------------------------
# Backward-compatible result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FooterRenderResult:
    """Outcome of an :func:`append_footer` render."""

    height: float
    """Rendered glyph bbox height (``0`` when no text was supplied)."""

    font_size: float
    """Final font size used (``0`` when no text was supplied)."""


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------


def _measure_text_size(text: str, font_size: float) -> Size:
    """Rendered glyph-bbox of ``text`` at ``font_size`` (in SVG units).

    Mirrors :func:`header._title_rendered_size` so footer and header
    use the same metric — ``getbbox()`` returns the tight bounding box
    that the SVG renderer paints, regardless of font ascent / descent
    slack.
    """
    if not text:
        return Size(0.0, 0.0)
    pil_font = Font.FINGER_KEY.load(int(round(max(font_size, 1.0))))
    left, top, right, bottom = pil_font.getbbox(text)
    return Size(width=float(right - left), height=float(bottom - top))


def _resolve_font_size(
    text: str,
    font_max_size: float,
    max_height: float | None,
) -> float:
    """Return the font size that fits ``text`` within ``max_height``.

    When ``max_height`` is ``None`` or the natural rendered text
    already fits below it, ``font_max_size`` is returned as-is.
    """
    if not text:
        return 0.0
    if max_height is None:
        return font_max_size
    natural_h = _measure_text_size(text, font_max_size).height
    if natural_h <= max_height or natural_h <= 0:
        return font_max_size
    scaled = font_max_size * (max_height / natural_h)
    return max(_MIN_FONT_SIZE, scaled)


# ---------------------------------------------------------------------------
# Composable
# ---------------------------------------------------------------------------


@Composable
def Footer(
    *,
    text: str,
    font_max_size: float,
    color: str = "black",
    max_height: float | None = None,
    use_system_fonts: bool = False,
):
    """A right-aligned line of footer text (typically a copyright notice).

    The element's size matches the rendered glyph bbox of ``text`` at
    the resolved font size — origin passed to :meth:`draw_at` is the
    top-left of that bbox. Returns a zero-sized, no-op element when
    ``text`` is empty so hosts don't need to special-case "no
    copyright".

    ``max_height`` caps the rendered text height; when supplied and
    the natural text would be taller, the font size shrinks
    proportionally so the bbox matches the cap.
    """
    if not text:
        size = Size(0.0, 0.0)

        def draw_at(d, origin):
            del d, origin

        return size, draw_at

    font_size = _resolve_font_size(text, font_max_size, max_height)
    size = _measure_text_size(text, font_size)
    family = Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value

    def draw_at(d, origin):
        # Origin is the top-left of the bbox; ``end`` + ``after-edge``
        # then pin the rendered text to the bbox's right-bottom corner
        # so the visible glyphs land inside ``size``.
        d.append(
            draw.Text(
                text,
                font_size=font_size,
                x=origin.x + size.width,
                y=origin.y + size.height,
                text_anchor="end",
                dominant_baseline="text-after-edge",
                font_family=family,
                fill=color,
                opacity=_FOOTER_OPACITY,
            )
        )

    return size, draw_at


# ---------------------------------------------------------------------------
# Backward-compatible imperative helpers
# ---------------------------------------------------------------------------


def footer_layout_height(
    text: str,
    font_max_size: float,
    max_height: float | None = None,
) -> float:
    """Predicted footer height for use in canvas-height calculations."""
    if not text:
        return 0.0
    return Footer(text=text, font_max_size=font_max_size, max_height=max_height).size.height


def append_footer(
    d: draw.Drawing,
    *,
    canvas_w: float,
    canvas_h: float,
    padding: float,
    bottom_inset: float,
    text: str,
    text_color: str,
    font_max_size: float,
    use_system_fonts: bool,
    max_height: float | None = None,
) -> FooterRenderResult:
    """Imperative wrapper around the :func:`Footer` composable.

    Builds the footer element, anchors its bottom-right corner at
    ``(canvas_w - padding, canvas_h - bottom_inset)``, and returns the
    rendered extents.
    """
    if not text:
        return FooterRenderResult(height=0.0, font_size=0.0)

    footer = Footer(
        text=text,
        font_max_size=font_max_size,
        color=text_color,
        max_height=max_height,
        use_system_fonts=use_system_fonts,
    )
    origin = Point(
        canvas_w - padding - footer.size.width,
        canvas_h - bottom_inset - footer.size.height,
    )
    footer.draw_at(d, origin)

    final_font_size = _resolve_font_size(text, font_max_size, max_height)
    return FooterRenderResult(height=footer.size.height, font_size=final_font_size)


__all__ = [
    "Footer",
    "FooterRenderResult",
    "append_footer",
    "footer_layout_height",
]
