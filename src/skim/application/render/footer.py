# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reusable footer component for keymap images.

The footer renders a right-aligned text line (typically the copyright
notice) at the bottom of the canvas. Hosts can pass an optional
``max_height`` that caps the rendered text height — used by the
standalone special-keys images so the copyright never reads taller than
the ``MACROS`` / ``TAP-DANCE`` section title above the body.

When a ``max_height`` ceiling is reached, the font size shrinks
proportionally so the rendered glyph bounding box matches the cap.
"""

from dataclasses import dataclass

import drawsvg as draw

from .text import Font

# Floor on the footer font size when shrinking under ``max_height`` so
# tight ceilings still produce something legible (and never produce a
# degenerate ``0``).
_MIN_FONT_SIZE = 6.0

# Opacity used when stamping the copyright string — matches the previous
# inline rendering in the per-layer / overview images.
_FOOTER_OPACITY = 0.6


@dataclass(frozen=True, slots=True)
class FooterRenderResult:
    """Outcome of a footer render — useful when the host needs the actual height."""

    height: float
    """Rendered glyph bounding box height (``0`` when no text was supplied)."""

    font_size: float
    """Final font size used (``0`` when no text was supplied)."""


def _measure_text_height(text: str, font_size: float) -> float:
    """Rendered glyph-bbox height of ``text`` at ``font_size`` (in SVG units).

    Mirrors :func:`header._title_rendered_size` so footer and header use
    the same metric — ``getbbox()`` returns the tight bounding box that
    the SVG renderer paints, regardless of font ascent / descent slack.
    """
    if not text:
        return 0.0
    pil_font = Font.FINGER_KEY.load(int(round(max(font_size, 1.0))))
    left, top, right, bottom = pil_font.getbbox(text)
    del left, right
    return float(bottom - top)


def _resolve_font_size(text: str, font_max_size: float, max_height: float | None) -> float:
    """Return the font size that fits ``text`` within ``max_height``.

    When ``max_height`` is ``None`` or the natural rendered text already
    fits below it, ``font_max_size`` is returned as-is.
    """
    if not text:
        return 0.0
    if max_height is None:
        return font_max_size
    natural_h = _measure_text_height(text, font_max_size)
    if natural_h <= max_height or natural_h <= 0:
        return font_max_size
    scaled = font_max_size * (max_height / natural_h)
    return max(_MIN_FONT_SIZE, scaled)


def footer_layout_height(
    text: str,
    font_max_size: float,
    max_height: float | None = None,
) -> float:
    """Predicted footer height for use in canvas-height calculations.

    Returns ``0`` when ``text`` is empty (no footer to reserve space for).
    """
    if not text:
        return 0.0
    font_size = _resolve_font_size(text, font_max_size, max_height)
    return _measure_text_height(text, font_size)


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
    """Append the footer to ``d`` and return its computed extents.

    Args:
        d: The drawing to append to.
        canvas_w: Total canvas width (used to right-align the text).
        canvas_h: Total canvas height (used to anchor the text to the
            bottom edge).
        padding: Outer padding used by the host image — the text's right
            edge sits ``padding`` inside the canvas's right edge.
        bottom_inset: Bottom inset used by the host image — the text's
            after-edge baseline sits ``bottom_inset`` above the canvas's
            bottom edge.
        text: Text to render (typically a copyright notice). When empty
            or ``None``, the footer is a no-op.
        text_color: Fill color for the text.
        font_max_size: Maximum font size; the actual size shrinks under
            this max only if needed to honour ``max_height``.
        use_system_fonts: When ``True`` the footer uses the system font
            family instead of the embedded ``FINGER_KEY`` font.
        max_height: Optional ceiling for the rendered glyph height. When
            the natural rendered text exceeds this value, the font
            shrinks proportionally so the bounding box matches the cap.

    Returns:
        A :class:`FooterRenderResult` describing the rendered extents.
    """
    if not text:
        return FooterRenderResult(height=0.0, font_size=0.0)

    font_size = _resolve_font_size(text, font_max_size, max_height)
    rendered_h = _measure_text_height(text, font_size)

    label_font = (
        Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value
    )
    d.append(
        draw.Text(
            text,
            font_size=font_size,
            x=canvas_w - padding,
            y=canvas_h - bottom_inset,
            text_anchor="end",
            dominant_baseline="text-after-edge",
            font_family=label_font,
            fill=text_color,
            opacity=_FOOTER_OPACITY,
        )
    )

    return FooterRenderResult(height=rendered_h, font_size=font_size)
